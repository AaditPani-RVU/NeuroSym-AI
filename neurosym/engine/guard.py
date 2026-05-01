# neurosym/engine/guard.py
from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Generator, Iterable
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol, cast, runtime_checkable

from neurosym.rules.base import Rule, Severity, StreamingRule, Violation, severity_gte


@runtime_checkable
class _LLM(Protocol):
    """Minimal LLM interface expected by Guard."""

    def generate(self, prompt: str, **gen_kwargs: Any) -> str: ...


# ----------------------------
# Information-first primitives
# ----------------------------


@dataclass(frozen=True)
class Artifact:
    """
    Universal container for "any information".

    kind:
      - "text": content is str
      - "json": content is dict/list/primitive JSON value
    meta: optional source context (trace_id, origin, timestamps, etc.)
    """

    kind: str
    content: Any
    meta: dict[str, Any] | None = None


@dataclass(frozen=True)
class Repair:
    """
    A record of a deterministic change applied by the guard (non-LLM repair).
    """

    repair_id: str
    message: str
    meta: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TraceEntry:
    """One attempt’s full context for auditing (LLM attempts or offline passes)."""

    attempt: int
    prompt_used: str | None
    input: Any
    output: Any
    violations: list[dict[str, Any]]
    repairs: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class GuardResult:
    """
    Unified result for both:
      - apply_* (information-first)
      - generate   (LLM-first)

    ok:          True iff no violations — overall pass/fail.
    blocked:     Always == not ok. The final allow/deny decision.
    hard_denied: True iff a hard-deny policy (deny_above / deny_rule_ids) triggered.
                 A subset of blocked — blocked can be True while hard_denied is False
                 when violations exist but none match the configured hard-deny criteria.
    """

    output: Any
    trace: list[TraceEntry]

    # Information-first summary fields (useful for pipelines)
    ok: bool = True
    blocked: bool = False
    hard_denied: bool = False
    violations: list[dict[str, Any]] = field(default_factory=list)
    repairs: list[dict[str, Any]] = field(default_factory=list)
    artifact: Artifact | None = None

    def report(self) -> str:
        lines: list[str] = []
        for t in self.trace:
            ids = ", ".join(v.get("rule_id", "?") for v in t.violations) or "none"
            lines.append(f"attempt {t.attempt}: violations = {ids}")
        return "\n".join(lines)

    def user_summary(self) -> list[dict[str, Any]]:
        """Sanitized violations safe to surface to end users (no attack spans or matched text)."""
        return [
            {
                "rule_id": v["rule_id"],
                "severity": v["severity"],
                "message": v.get("user_message") or "Content was flagged by a safety rule.",
            }
            for v in self.violations
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "output": self.output,
            "ok": self.ok,
            "blocked": self.blocked,
            "hard_denied": self.hard_denied,
            "violations": self.violations,
            "repairs": self.repairs,
            "artifact": asdict(self.artifact) if self.artifact else None,
            "trace": [asdict(t) for t in self.trace],
        }


class Guard:
    """
    Two modes:

    1) Information-first (no LLM required):
         Guard(rules=[...]).apply_text(...), apply_json(...), apply(Artifact)

    2) LLM-first (existing behavior preserved):
         Guard(llm=..., rules=[...]).generate(prompt)
    """

    def __init__(
        self,
        rules: list[Rule],
        llm: _LLM | None = None,
        max_retries: int = 2,
        deny_rule_ids: Iterable[str] | None = None,
        enable_offline_repairs: bool = True,
        deny_above: Severity | None = None,
    ) -> None:
        self.llm = llm
        self.rules = rules
        self.max_retries = max(0, int(max_retries))
        self._deny_rule_ids = set(deny_rule_ids or ())
        self.enable_offline_repairs = enable_offline_repairs
        self.deny_above = deny_above

    # ---------- Internals ----------

    def _validate(self, output: Any) -> list[Violation]:
        violations: list[Violation] = []
        for rule in self.rules:
            try:
                violations.extend(rule.evaluate(output))
            except Exception as e:
                violations.append(
                    Violation(
                        rule_id=getattr(rule, "id", rule.__class__.__name__),
                        message=f"rule exception: {e}",
                        meta={"exception": repr(e)},
                    )
                )
        return violations

    @staticmethod
    def _v_to_dict(v: Violation) -> dict[str, Any]:
        return {
            "rule_id": getattr(v, "rule_id", "unknown_rule"),
            "message": getattr(v, "message", str(v)),
            "severity": getattr(v, "severity", "medium"),
            "meta": getattr(v, "meta", None),
            "user_message": getattr(v, "user_message", None),
        }

    def _has_hard_deny(self, violations: list[Violation]) -> bool:
        if self._deny_rule_ids and any(v.rule_id in self._deny_rule_ids for v in violations):
            return True
        if self.deny_above is not None:
            return any(severity_gte(v.severity, self.deny_above) for v in violations)
        return False

    def _compute_ok_blocked(self, violations: list[Violation]) -> tuple[bool, bool, bool]:
        """Return (ok, blocked, hard_denied).

        ok:          True iff no violations — always the overall pass/fail signal.
        blocked:     Always == not ok — the final allow/deny decision for callers.
        hard_denied: True iff a hard-deny policy triggers (deny_above / deny_rule_ids).
                     Callers that need to distinguish severity routing from pass/fail
                     should gate on hard_denied rather than blocked.
        """
        ok = len(violations) == 0
        blocked = not ok
        hard_denied = self._has_hard_deny(violations)
        return ok, blocked, hard_denied

    # ---------- Offline deterministic repairs ----------

    _FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE | re.MULTILINE)

    @classmethod
    def _strip_code_fences(cls, text: str) -> tuple[str, list[Repair]]:
        new = re.sub(cls._FENCE_RE, "", text).strip()
        if new != text.strip():
            return new, [Repair("repair.strip_code_fences", "Stripped Markdown code fences")]
        return text, []

    @staticmethod
    def _extract_first_json_block(text: str) -> tuple[str | None, list[Repair]]:
        """
        Best-effort: finds the first {...} or [...] block and returns it as a substring.
        This is intentionally conservative.
        """
        start_positions = [p for p in (text.find("{"), text.find("[")) if p != -1]
        if not start_positions:
            return None, []
        start = min(start_positions)
        # naive bracket matching
        stack: list[str] = []
        for i in range(start, len(text)):
            ch = text[i]
            if ch in "{[":
                stack.append(ch)
            elif ch in "}]":
                if not stack:
                    break
                top = stack.pop()
                if (top == "{" and ch != "}") or (top == "[" and ch != "]"):
                    # mismatched; abort
                    return None, []
                if not stack:
                    block = text[start : i + 1]
                    return block, [
                        Repair(
                            "repair.extract_json_block",
                            "Extracted JSON block from text",
                        )
                    ]
        return None, []

    @staticmethod
    def _try_parse_json(text: str) -> tuple[Any | None, list[Repair]]:
        try:
            return json.loads(text), [Repair("repair.parse_json", "Parsed JSON successfully")]
        except Exception:
            return None, []

    def _offline_repair(self, artifact: Artifact) -> tuple[Artifact, list[Repair]]:
        """
        Deterministic repairs that make the library useful without any LLM or keys.
        """
        if not self.enable_offline_repairs:
            return artifact, []

        repairs: list[Repair] = []

        if artifact.kind == "text" and isinstance(artifact.content, str):
            t = artifact.content

            # 1) Strip fences
            t2, r = self._strip_code_fences(t)
            repairs.extend(r)
            t = t2

            # 2) If it looks like JSON in text, extract+parse into json artifact
            block, r = self._extract_first_json_block(t)
            repairs.extend(r)
            if block is not None:
                parsed, r2 = self._try_parse_json(block)
                repairs.extend(r2)
                if parsed is not None:
                    return (
                        Artifact(kind="json", content=parsed, meta=artifact.meta),
                        repairs,
                    )

            return Artifact(kind="text", content=t, meta=artifact.meta), repairs

        return artifact, repairs

    # ---------- Information-first public API ----------

    def apply(self, artifact: Artifact) -> GuardResult:
        trace: list[TraceEntry] = []

        # offline repair pass (attempt 1)
        repaired_artifact, repairs = self._offline_repair(artifact)

        # validate on artifact content
        violations = self._validate(repaired_artifact.content)

        trace.append(
            TraceEntry(
                attempt=1,
                prompt_used=None,
                input=artifact.content,
                output=repaired_artifact.content,
                violations=[self._v_to_dict(v) for v in violations],
                repairs=[r.to_dict() for r in repairs],
            )
        )

        ok, blocked, hard_denied = self._compute_ok_blocked(violations)

        return GuardResult(
            output=repaired_artifact.content,
            trace=trace,
            ok=ok,
            blocked=blocked,
            hard_denied=hard_denied,
            violations=[self._v_to_dict(v) for v in violations],
            repairs=[r.to_dict() for r in repairs],
            artifact=repaired_artifact,
        )

    def apply_text(self, text: str, meta: dict[str, Any] | None = None) -> GuardResult:
        return self.apply(Artifact(kind="text", content=text, meta=meta))

    def apply_json(self, obj: Any, meta: dict[str, Any] | None = None) -> GuardResult:
        return self.apply(Artifact(kind="json", content=obj, meta=meta))

    # ---------- Async information-first API ----------

    async def _avalidate(self, output: Any) -> list[Violation]:
        """Evaluate all rules concurrently via asyncio.gather.

        Rules with a native coroutine aevaluate are awaited directly.
        All other rules run in a thread pool so sync code never blocks the event loop.
        """

        async def _eval_one(r: Rule) -> list[Violation]:
            try:
                aevaluate = getattr(r, "aevaluate", None)
                if asyncio.iscoroutinefunction(aevaluate):
                    return cast(list[Violation], await aevaluate(output))
                return await asyncio.to_thread(r.evaluate, output)
            except Exception as e:
                return [
                    Violation(
                        rule_id=getattr(r, "id", r.__class__.__name__),
                        message=f"rule exception: {e}",
                        meta={"exception": repr(e)},
                    )
                ]

        results = await asyncio.gather(*[_eval_one(r) for r in self.rules])
        return [v for batch in results for v in batch]

    async def aapply(self, artifact: Artifact) -> GuardResult:
        """Async version of apply()."""
        repaired_artifact, repairs = self._offline_repair(artifact)
        violations = await self._avalidate(repaired_artifact.content)
        trace = [
            TraceEntry(
                attempt=1,
                prompt_used=None,
                input=artifact.content,
                output=repaired_artifact.content,
                violations=[self._v_to_dict(v) for v in violations],
                repairs=[r.to_dict() for r in repairs],
            )
        ]
        ok, blocked, hard_denied = self._compute_ok_blocked(violations)
        return GuardResult(
            output=repaired_artifact.content,
            trace=trace,
            ok=ok,
            blocked=blocked,
            hard_denied=hard_denied,
            violations=[self._v_to_dict(v) for v in violations],
            repairs=[r.to_dict() for r in repairs],
            artifact=repaired_artifact,
        )

    async def aapply_text(self, text: str, meta: dict[str, Any] | None = None) -> GuardResult:
        return await self.aapply(Artifact(kind="text", content=text, meta=meta))

    async def aapply_json(self, obj: Any, meta: dict[str, Any] | None = None) -> GuardResult:
        return await self.aapply(Artifact(kind="json", content=obj, meta=meta))

    async def agenerate(self, prompt: str, **gen_kwargs: Any) -> GuardResult:
        """Async version of generate() — LLM calls run in executor, rules run concurrently."""
        loop = asyncio.get_event_loop()

        trace: list[TraceEntry] = []
        attempt = 1
        current_prompt = prompt

        text = await loop.run_in_executor(
            None, lambda: self._safe_llm_generate(current_prompt, **gen_kwargs)
        )
        violations = await self._avalidate(text)

        trace.append(
            TraceEntry(
                attempt=attempt,
                prompt_used=current_prompt,
                input=None,
                output=text,
                violations=[self._v_to_dict(v) for v in violations],
                repairs=[],
            )
        )

        if not violations or self._has_hard_deny(violations) or self.max_retries == 0:
            ok, blocked, hard_denied = self._compute_ok_blocked(violations)
            return GuardResult(
                output=text,
                trace=trace,
                ok=ok,
                blocked=blocked,
                hard_denied=hard_denied,
                violations=[self._v_to_dict(v) for v in violations],
                repairs=[],
                artifact=Artifact(kind="text", content=text),
            )

        while attempt < 1 + self.max_retries:
            attempt += 1
            repair_prompt = self._repair_prompt(prompt, text, violations)
            text = await loop.run_in_executor(
                None,
                lambda rp=repair_prompt: self._safe_llm_generate(rp, **gen_kwargs),  # type: ignore[misc]
            )
            violations = await self._avalidate(text)
            trace.append(
                TraceEntry(
                    attempt=attempt,
                    prompt_used=repair_prompt,
                    input=None,
                    output=text,
                    violations=[self._v_to_dict(v) for v in violations],
                    repairs=[],
                )
            )
            if not violations or self._has_hard_deny(violations):
                break

        ok, blocked, hard_denied = self._compute_ok_blocked(violations)
        return GuardResult(
            output=text,
            trace=trace,
            ok=ok,
            blocked=blocked,
            hard_denied=hard_denied,
            violations=[self._v_to_dict(v) for v in violations],
            repairs=[],
            artifact=Artifact(kind="text", content=text),
        )

    # ---------- LLM-first API (backwards compatible) ----------

    def _repair_prompt(
        self, original_prompt: str, last_output: Any, violations: list[Violation]
    ) -> str:
        bullets = "\n".join(f" - [{v.rule_id}] {v.message}" for v in violations)
        return (
            f"{original_prompt}\n\n"
            "Your previous answer violated the following rules. "
            "Return a corrected answer that satisfies **all** of them.\n"
            "Rules to fix:\n"
            f"{bullets}\n\n"
            "Previous answer to correct:\n"
            "<<<BEGIN_ANSWER>>>\n"
            f"{last_output}\n"
            "<<<END_ANSWER>>>"
        )

    def _safe_llm_generate(self, prompt: str, **gen_kwargs: Any) -> str:
        if self.llm is None:
            raise RuntimeError("Guard.generate() called but no llm was provided to Guard(llm=...)")
        try:
            return self.llm.generate(prompt, **gen_kwargs)
        except Exception as e:
            snippet = prompt if len(prompt) <= 200 else (prompt[:200] + "…")
            raise RuntimeError(f"LLM generate() failed on prompt: {snippet!r}") from e

    def generate(self, prompt: str, **gen_kwargs: Any) -> GuardResult:
        trace: list[TraceEntry] = []

        attempt = 1
        current_prompt = prompt

        text = self._safe_llm_generate(current_prompt, **gen_kwargs)
        violations = self._validate(text)

        trace.append(
            TraceEntry(
                attempt=attempt,
                prompt_used=current_prompt,
                input=None,
                output=text,
                violations=[self._v_to_dict(v) for v in violations],
                repairs=[],
            )
        )

        if not violations or self._has_hard_deny(violations) or self.max_retries == 0:
            ok, blocked, hard_denied = self._compute_ok_blocked(violations)
            return GuardResult(
                output=text,
                trace=trace,
                ok=ok,
                blocked=blocked,
                hard_denied=hard_denied,
                violations=[self._v_to_dict(v) for v in violations],
                repairs=[],
                artifact=Artifact(kind="text", content=text),
            )

        while attempt < 1 + self.max_retries:
            attempt += 1
            current_prompt = self._repair_prompt(prompt, text, violations)
            text = self._safe_llm_generate(current_prompt, **gen_kwargs)

            violations = self._validate(text)
            trace.append(
                TraceEntry(
                    attempt=attempt,
                    prompt_used=current_prompt,
                    input=None,
                    output=text,
                    violations=[self._v_to_dict(v) for v in violations],
                    repairs=[],
                )
            )

            if not violations or self._has_hard_deny(violations):
                break

        ok, blocked, hard_denied = self._compute_ok_blocked(violations)
        return GuardResult(
            output=text,
            trace=trace,
            ok=ok,
            blocked=blocked,
            hard_denied=hard_denied,
            violations=[self._v_to_dict(v) for v in violations],
            repairs=[],
            artifact=Artifact(kind="text", content=text),
        )

    def stream(self, prompt: str, **gen_kwargs: Any) -> Generator[str, None, GuardResult]:
        """Stream LLM output while evaluating rules incrementally.

        Yields ``str`` chunks as they arrive. Rules implementing the
        :class:`StreamingRule` protocol are fed each chunk via ``feed()`` and
        ``finalize()``; all other rules run on the complete buffered output
        after the stream ends. A hard-deny rule firing mid-stream stops
        further chunk emission early.

        Retrieve the final :class:`GuardResult` via ``StopIteration.value``::

            gen = guard.stream("prompt")
            try:
                while True:
                    chunk = next(gen)
                    print(chunk, end="", flush=True)
            except StopIteration as stop:
                result = stop.value
        """
        if self.llm is None:
            raise RuntimeError("Guard.stream() called but no llm was provided to Guard(llm=...)")

        buffer = ""
        streaming_violations: list[Violation] = []

        stream_rules = [r for r in self.rules if isinstance(r, StreamingRule)]
        batch_rules = [r for r in self.rules if not isinstance(r, StreamingRule)]

        for r in stream_rules:
            r.reset()

        _stream_fn = getattr(self.llm, "stream", None)
        if _stream_fn is not None and callable(_stream_fn):
            try:
                chunk_iter: Iterable[str] = _stream_fn(prompt, **gen_kwargs)
            except Exception as exc:
                raise RuntimeError(f"LLM stream() failed: {exc}") from exc
        else:
            chunk_iter = [self._safe_llm_generate(prompt, **gen_kwargs)]

        for chunk in chunk_iter:
            buffer += chunk

            for r in stream_rules:
                try:
                    vs = r.feed(chunk)
                except Exception as exc:
                    vs = [
                        Violation(
                            rule_id=getattr(r, "id", r.__class__.__name__),
                            message=f"streaming rule exception: {exc}",
                            meta={"exception": repr(exc)},
                        )
                    ]
                streaming_violations.extend(vs)

            yield chunk

            if stream_rules and self._has_hard_deny(streaming_violations):
                break

        for r in stream_rules:
            try:
                streaming_violations.extend(r.finalize())
            except Exception as exc:
                streaming_violations.append(
                    Violation(
                        rule_id=getattr(r, "id", r.__class__.__name__),
                        message=f"finalize exception: {exc}",
                        meta={"exception": repr(exc)},
                    )
                )

        batch_violations: list[Violation] = []
        for br in batch_rules:
            try:
                batch_violations.extend(br.evaluate(buffer))
            except Exception as exc:
                batch_violations.append(
                    Violation(
                        rule_id=getattr(br, "id", br.__class__.__name__),
                        message=f"rule exception: {exc}",
                        meta={"exception": repr(exc)},
                    )
                )

        all_violations = streaming_violations + batch_violations
        ok, blocked, hard_denied = self._compute_ok_blocked(all_violations)

        return GuardResult(
            output=buffer,
            trace=[
                TraceEntry(
                    attempt=1,
                    prompt_used=prompt,
                    input=None,
                    output=buffer,
                    violations=[self._v_to_dict(v) for v in all_violations],
                    repairs=[],
                )
            ],
            ok=ok,
            blocked=blocked,
            hard_denied=hard_denied,
            violations=[self._v_to_dict(v) for v in all_violations],
            repairs=[],
            artifact=Artifact(kind="text", content=buffer),
        )
