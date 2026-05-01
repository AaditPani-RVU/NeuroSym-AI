"""Output guard: detect system-prompt regurgitation in LLM responses."""

from __future__ import annotations

from typing import Any

from neurosym.rules.base import BaseRule, Severity, Violation


class SystemPromptRegurgitationRule(BaseRule):
    """Detect when the LLM echoes its own system prompt verbatim in output.

    Splits the configured system prompt into overlapping windows and checks
    whether any window appears in the output. This prevents a developer who
    naively renders ``result.output`` from leaking the prompt to end users.

    Args:
        system_prompt: The system prompt text to watch for.
        id: Rule identifier.
        severity: Default ``"high"``.
        min_span: Minimum substring length to match against (default 50).
                  Longer values reduce false positives from common phrases.
    """

    id: str = "output.system_prompt_regurgitation"

    def __init__(
        self,
        system_prompt: str,
        id: str = "output.system_prompt_regurgitation",
        severity: Severity = "high",
        min_span: int = 50,
    ) -> None:
        self.id = id
        self._severity = severity
        self._system_prompt = system_prompt
        self._min_span = min_span
        self._windows = self._build_windows(system_prompt, min_span)

    @staticmethod
    def _build_windows(text: str, span: int) -> list[str]:
        step = max(1, span // 2)
        return [
            text[i : i + span]
            for i in range(0, max(1, len(text) - span + 1), step)
            if len(text[i : i + span]) == span
        ]

    def check(self, output: Any) -> Violation | None:
        text = output if isinstance(output, str) else str(output)
        for window in self._windows:
            if window in text:
                return Violation(
                    rule_id=self.id,
                    message="System prompt regurgitation detected in output",
                    severity=self._severity,
                    meta={"matched_excerpt": window[:80]},
                    user_message="Output was blocked: internal instructions were exposed.",
                )
        return None
