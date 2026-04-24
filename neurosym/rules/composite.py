"""Composite rule combinators: AllOf, AnyOf, Not, Implies.

Lets you build boolean policy algebra from atomic rules::

    from neurosym.rules.composite import AllOf, AnyOf, Not, Implies

    # Destructive action AND no confirmation = violation
    AllOf([has_destructive_step, Not(has_confirmation)])

    # Block if EITHER injection OR dangerous path found
    AnyOf([injection_rule, path_traversal_rule], id="any_threat")
"""

from __future__ import annotations

from typing import Any

from .base import BaseRule, Rule, Severity, Violation


class AllOf(BaseRule):
    """
    Aggregates violations from ALL child rules.

    Passes (no violations) only if every child rule passes.
    All child violations are collected and returned.

    Useful for: grouping related rules under one id, or building complex
    multi-condition policies.
    """

    id: str = "composite.all_of"

    def __init__(
        self,
        rules: list[Rule],
        id: str = "composite.all_of",
        severity: Severity | None = None,
    ) -> None:
        """
        Args:
            rules: Child rules to evaluate.
            id: Rule identifier for this combinator.
            severity: If set, overrides the severity of all collected violations.
        """
        self.id = id
        self._rules = rules
        self._severity_override = severity

    def check(self, output: Any) -> list[Violation] | Violation | None:
        violations: list[Violation] = []
        for rule in self._rules:
            try:
                violations.extend(rule.evaluate(output))
            except Exception as exc:
                violations.append(
                    Violation(
                        rule_id=getattr(rule, "id", "unknown"),
                        message=f"Rule error: {exc!r}",
                        severity="high",
                    )
                )
        if self._severity_override is not None:
            violations = [
                Violation(
                    rule_id=v.rule_id,
                    message=v.message,
                    severity=self._severity_override,
                    meta=v.meta,
                )
                for v in violations
            ]
        return violations or None


class AnyOf(BaseRule):
    """
    Produces a violation only if ALL child rules produce violations.

    In other words: passes if at least ONE child rule passes.

    Useful for: "allow action if it matches any of these safe patterns".
    Inverse logic to AllOf.
    """

    id: str = "composite.any_of"

    def __init__(
        self,
        rules: list[Rule],
        id: str = "composite.any_of",
        message: str = "All candidate rules failed — no rule approved this output",
        severity: Severity = "medium",
    ) -> None:
        self.id = id
        self._rules = rules
        self._message = message
        self._severity = severity

    def check(self, output: Any) -> list[Violation] | Violation | None:
        for rule in self._rules:
            try:
                viols = rule.evaluate(output)
                if not viols:
                    return None  # at least one rule passed
            except Exception:
                pass  # treat exception as failure for this rule
        return self.fail(self._message, severity=self._severity)


class Not(BaseRule):
    """
    Produces a violation when the inner rule PASSES (inverts the rule).

    Useful for: "this output must NOT match a safe pattern" — i.e., enforce
    that something which should be blocked is indeed being blocked.
    Or: "ensure the output does NOT contain valid JSON" (for plain-text endpoints).
    """

    id: str = "composite.not"

    def __init__(
        self,
        rule: Rule,
        id: str = "composite.not",
        message: str | None = None,
        severity: Severity = "medium",
    ) -> None:
        self.id = id
        self._rule = rule
        self._message = message
        self._severity = severity

    def check(self, output: Any) -> list[Violation] | Violation | None:
        try:
            viols = self._rule.evaluate(output)
        except Exception:
            viols = []
        if not viols:
            msg = self._message or f"Rule {getattr(self._rule, 'id', '?')} passed but must NOT"
            return self.fail(msg, severity=self._severity)
        return None


class Implies(BaseRule):
    """
    If `condition` rule passes (no violations), then `consequence` rule must also pass.

    Logical implication: condition → consequence.
    Only evaluated if the condition holds; otherwise always passes.

    Example::

        # If plan has a file action, it must have a confirmation
        Implies(has_file_action_rule, has_confirmation_rule)
    """

    id: str = "composite.implies"

    def __init__(
        self,
        condition: Rule,
        consequence: Rule,
        id: str = "composite.implies",
        message: str | None = None,
        severity: Severity = "high",
    ) -> None:
        self.id = id
        self._condition = condition
        self._consequence = consequence
        self._message = message
        self._severity = severity

    def check(self, output: Any) -> list[Violation] | Violation | None:
        try:
            condition_viols = self._condition.evaluate(output)
        except Exception:
            return None  # condition indeterminate → don't enforce consequence

        if condition_viols:
            return None  # condition failed → implication vacuously true

        # condition passed → check consequence
        try:
            consequence_viols = self._consequence.evaluate(output)
        except Exception as exc:
            return self.fail(
                f"Consequence rule error: {exc!r}",
                severity=self._severity,
            )

        if consequence_viols:
            msg = self._message or (
                f"Condition '{getattr(self._condition, 'id', '?')}' held but "
                f"consequence '{getattr(self._consequence, 'id', '?')}' failed"
            )
            return self.fail(msg, severity=self._severity)

        return None
