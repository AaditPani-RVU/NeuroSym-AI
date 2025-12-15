# neurosym/engine/guard.py
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol, runtime_checkable

from neurosym.rules.base import Rule, Violation


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
    """

    output: Any
    trace: list[TraceEntry]

    # Information-first summary fields (useful for pipelines)
    ok: bool = True
    violations: list[dict[str, Any]] = field(default_factory=list)
    repairs: list[dict[str, Any]] = field(default_factory=list)
    artifact: Artifact | None = None

    def report(self) -> str:
        lines: list[str] = []
        for t in self.trace:
            ids = ", ".join(v.get("rule_id", "?") for v in t.violations) or "none"
            lines.append(f"attempt {t.attempt}: violations = {ids}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "output": self.output,
            "ok": self.ok,
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
    ) -> None:
        self.llm = llm
        self.rules = rules
        self.max_retries = max(0, int(max_retries))
        self._deny_rule_ids = set(deny_rule_ids or ())
        self.enable_offline_repairs = enable_offline_repairs

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
            "meta": getattr(v, "meta", None),
        }

    def _has_hard_deny(self, violations: list[Violation]) -> bool:
        if not self._deny_rule_ids:
            return False
        return any(v.rule_id in self._deny_rule_ids for v in violations)

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

        ok = (len(violations) == 0) and (not self._has_hard_deny(violations))

        return GuardResult(
            output=repaired_artifact.content,
            trace=trace,
            ok=ok,
            violations=[self._v_to_dict(v) for v in violations],
            repairs=[r.to_dict() for r in repairs],
            artifact=repaired_artifact,
        )

    def apply_text(self, text: str, meta: dict[str, Any] | None = None) -> GuardResult:
        return self.apply(Artifact(kind="text", content=text, meta=meta))

    def apply_json(self, obj: Any, meta: dict[str, Any] | None = None) -> GuardResult:
        return self.apply(Artifact(kind="json", content=obj, meta=meta))

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
            return GuardResult(
                output=text,
                trace=trace,
                ok=(len(violations) == 0),
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

        return GuardResult(
            output=text,
            trace=trace,
            ok=(len(violations) == 0),
            violations=[self._v_to_dict(v) for v in violations],
            repairs=[],
            artifact=Artifact(kind="text", content=text),
        )
