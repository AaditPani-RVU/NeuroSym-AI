# neurosym/engine/guard.py

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any, Protocol, runtime_checkable

from neurosym.rules.base import Rule, Violation


@runtime_checkable
class _LLM(Protocol):
    """Minimal LLM interface expected by Guard."""

    def generate(self, prompt: str, **gen_kwargs) -> str: ...


@dataclass(frozen=True)
class TraceEntry:
    """One attempt’s full context for auditing."""

    attempt: int
    prompt_used: str
    output: Any
    violations: list[
        dict[str, Any]
    ]  # [{"rule_id": "...", "message": "...", "meta": {...}}]


@dataclass
class GuardResult:
    output: Any
    trace: list[TraceEntry]

    def report(self) -> str:
        lines: list[str] = []
        for t in self.trace:
            ids = ", ".join(v.get("rule_id", "?") for v in t.violations) or "none"
            lines.append(f"attempt {t.attempt}: violations = {ids}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {"output": self.output, "trace": [asdict(t) for t in self.trace]}


class Guard:
    """
    Orchestrates: prompt -> LLM -> validate -> (optional) repair -> return.

    - Works with your Rule/Violation protocol (no severity required).
    - Optional `deny_rule_ids` lets you mark certain rule IDs as hard-stops.
    - Returns a structured, serializable trace for audits.
    """

    def __init__(
        self,
        llm: _LLM,
        rules: list[Rule],
        max_retries: int = 2,
        deny_rule_ids: Iterable[str] | None = None,
    ) -> None:
        self.llm = llm
        self.rules = rules
        self.max_retries = max(0, int(max_retries))
        self._deny_rule_ids = set(deny_rule_ids or ())

    # ---------- Internals ----------

    def _validate(self, output: Any) -> list[Violation]:
        violations: list[Violation] = []
        for rule in self.rules:
            try:
                violations.extend(rule.evaluate(output))
            except Exception as e:
                # Convert rule failure into a synthetic violation so the run remains auditable.
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

    def _safe_llm_generate(self, prompt: str, **gen_kwargs) -> str:
        try:
            return self.llm.generate(prompt, **gen_kwargs)
        except Exception as e:
            # Include prompt context to make failures diagnosable.
            snippet = prompt if len(prompt) <= 200 else (prompt[:200] + "…")
            raise RuntimeError(f"LLM generate() failed on prompt: {snippet!r}") from e

    # ---------- Public API ----------

    def generate(self, prompt: str, **gen_kwargs) -> GuardResult:
        trace: list[TraceEntry] = []

        # Attempt counter starts at 1 (human-friendly)
        attempt = 1
        current_prompt = prompt

        # First pass
        text = self._safe_llm_generate(current_prompt, **gen_kwargs)
        violations = self._validate(text)
        trace.append(
            TraceEntry(
                attempt=attempt,
                prompt_used=current_prompt,
                output=text,
                violations=[self._v_to_dict(v) for v in violations],
            )
        )

        # Early exits
        if not violations or self._has_hard_deny(violations) or self.max_retries == 0:
            return GuardResult(output=text, trace=trace)

        # Repair loop
        while attempt < 1 + self.max_retries:
            attempt += 1
            current_prompt = self._repair_prompt(prompt, text, violations)
            text = self._safe_llm_generate(current_prompt, **gen_kwargs)

            violations = self._validate(text)
            trace.append(
                TraceEntry(
                    attempt=attempt,
                    prompt_used=current_prompt,
                    output=text,
                    violations=[self._v_to_dict(v) for v in violations],
                )
            )

            if not violations or self._has_hard_deny(violations):
                break

        return GuardResult(output=text, trace=trace)
