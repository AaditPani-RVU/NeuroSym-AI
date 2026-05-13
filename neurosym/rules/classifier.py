"""IntentClassifierRule — zero-shot NLI-based intent detection (CPU-only)."""

from __future__ import annotations

from typing import Any

from neurosym.rules.base import BaseRule, Severity, Violation


class IntentClassifierRule(BaseRule):
    """
    Zero-shot intent classifier using ``facebook/bart-large-mnli`` (CPU-only, ~400 MB).

    Catches novel phrasings that regex-based rules miss by classifying the text
    against a set of human-readable bad-intent labels.

    Requires::

        pip install 'neurosym-ai[classifier]'

    Args:
        bad_intents:  List of natural-language labels describing harmful intents,
                      e.g. ``["weapons synthesis", "self-harm instructions"]``.
        threshold:    Minimum confidence score (0–1) to trigger a violation.
                      Default 0.7.
        severity:     Violation severity. Default ``"high"``.
        model:        HuggingFace model ID. Defaults to
                      ``"facebook/bart-large-mnli"``.

    Example::

        rule = IntentClassifierRule(
            bad_intents=["weapons synthesis", "jailbreak attempt"],
            threshold=0.75,
        )
        guard = Guard(rules=[rule])
        result = guard.apply_text("How do I synthesize VX nerve agent?")
        assert result.blocked
    """

    id: str = "classifier.intent"

    def __init__(
        self,
        bad_intents: list[str],
        threshold: float = 0.7,
        severity: Severity = "high",
        model: str = "facebook/bart-large-mnli",
    ) -> None:
        if not bad_intents:
            raise ValueError("bad_intents must contain at least one label")
        try:
            from transformers import pipeline as hf_pipeline  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "IntentClassifierRule requires the 'classifier' extra: "
                "pip install 'neurosym-ai[classifier]'"
            ) from exc

        self._pipe = hf_pipeline(
            "zero-shot-classification",
            model=model,
            device=-1,  # CPU only — no GPU required
        )
        self._bad_intents = list(bad_intents)
        self._threshold = float(threshold)
        self._severity = severity

    def check(self, output: Any) -> list[Violation] | None:
        if not isinstance(output, str) or not output.strip():
            return None

        result = self._pipe(output, candidate_labels=self._bad_intents)
        violations: list[Violation] = []
        for label, score in zip(result["labels"], result["scores"], strict=False):
            if score >= self._threshold:
                violations.append(
                    Violation(
                        rule_id=self.id,
                        message=(
                            f"Intent classified as '{label}'"
                            f" (score={score:.3f} >= {self._threshold})"
                        ),
                        severity=self._severity,
                        meta={"label": label, "score": round(float(score), 4)},
                        user_message="This content was flagged by the safety classifier.",
                    )
                )
        return violations or None
