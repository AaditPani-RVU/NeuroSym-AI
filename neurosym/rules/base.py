# neurosym/rules/base.py
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

# ----------------------------
# Core data structures
# ----------------------------


@dataclass(frozen=True)
class Violation:
    """
    A single rule violation produced by a Rule.
    - rule_id: stable identifier for the rule (e.g., "schema.invoice.required")
    - message: human-readable explanation of what failed
    - meta: optional machine-readable context (paths, diffs, indices, etc.)
    """

    rule_id: str
    message: str
    meta: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serializable form (used by tracing & logging)."""
        return asdict(self)

    @staticmethod
    def simple(rule_id: str, message: str, **meta: Any) -> Violation:
        """Convenience constructor."""
        return Violation(rule_id=rule_id, message=message, meta=meta or None)


class Rule(Protocol):
    """
    Minimal contract a rule must satisfy.

    Implementations should be *pure* functions of the output (no mutation),
    returning zero or more Violations. An empty list means the rule passed.

    NOTE: Keep this signature exactly as-is to remain compatible with Guard.
    """

    id: str

    def evaluate(self, output: Any) -> list[Violation]: ...


# ----------------------------
# Optional helpers (pure)
# ----------------------------


def run_rules(rules: list[Rule], output: Any) -> list[Violation]:
    """
    Evaluate a list of rules against output and aggregate violations.
    This mirrors Guard._validate but without exception wrapping.
    Useful for unit tests or ad-hoc checks.
    """
    violations: list[Violation] = []
    for r in rules:
        violations.extend(r.evaluate(output))
    return violations


# ----------------------------
# Lightweight base class (optional use)
# ----------------------------


class BaseRule:
    """
    Optional convenience base for rules.
    Provides a consistent 'id' and small helpers for building violations.
    Subclass and override `check()`; do not override `evaluate()` unless needed.
    """

    # Subclasses should set a stable, dotted rule id, e.g. "schema.invoice.required"
    id: str = "rule.unnamed"

    def evaluate(self, output: Any) -> list[Violation]:
        """
        Template method. Calls `check(output)` and normalizes results to a list.
        Subclasses implement `check()` and may return:
          - None or []            -> no violations
          - Violation             -> single violation
          - List[Violation]       -> one or more violations
        """
        res = self.check(output)
        if res is None:
            return []
        if isinstance(res, Violation):
            return [res]
        if isinstance(res, list):
            # Ensure all items are Violations
            return [v for v in res if isinstance(v, Violation)]
        # Anything else is treated as "no violations"
        return []

    # ---- override in subclasses ----
    def check(self, output: Any) -> list[Violation] | Violation | None:
        raise NotImplementedError

    # ---- helpers for subclasses ----
    def fail(self, message: str, **meta: Any) -> Violation:
        return Violation(rule_id=self.id, message=message, meta=meta or None)

    def ok(self) -> list[Violation]:
        return []
