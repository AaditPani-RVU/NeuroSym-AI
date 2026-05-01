# neurosym/rules/base.py
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Literal, Protocol, runtime_checkable

Severity = Literal["info", "low", "medium", "high", "critical"]

_SEVERITY_ORDER: dict[str, int] = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def severity_gte(a: Severity, b: Severity) -> bool:
    """Return True if severity `a` is >= severity `b`."""
    return _SEVERITY_ORDER[a] >= _SEVERITY_ORDER[b]


# ----------------------------
# Core data structures
# ----------------------------


@dataclass(frozen=True)
class Violation:
    """
    A single rule violation produced by a Rule.
    - rule_id: stable identifier for the rule (e.g., "schema.invoice.required")
    - message: full audit message (may contain matched spans — never show to end users)
    - severity: how serious the violation is (info < low < medium < high < critical)
    - meta: optional machine-readable context (paths, diffs, indices, etc.)
    - user_message: sanitized message safe to surface to end users (no attack text)
    """

    rule_id: str
    message: str
    severity: Severity = "medium"
    meta: dict[str, Any] | None = None
    user_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serializable form (used by tracing & logging)."""
        return asdict(self)

    @staticmethod
    def simple(
        rule_id: str,
        message: str,
        severity: Severity = "medium",
        user_message: str | None = None,
        **meta: Any,
    ) -> Violation:
        """Convenience constructor."""
        return Violation(
            rule_id=rule_id,
            message=message,
            severity=severity,
            meta=meta or None,
            user_message=user_message,
        )


@runtime_checkable
class Rule(Protocol):
    """
    Minimal contract a rule must satisfy.

    Implementations should be *pure* functions of the output (no mutation),
    returning zero or more Violations. An empty list means the rule passed.

    NOTE: Keep this signature exactly as-is to remain compatible with Guard.
    """

    id: str

    def evaluate(self, output: Any) -> list[Violation]: ...


@runtime_checkable
class StreamingRule(Protocol):
    """Rule that evaluates output incrementally as it streams chunk by chunk.

    Implement this protocol alongside BaseRule to enable incremental evaluation
    in Guard.stream(). Rules that do not implement this protocol are evaluated
    on the complete buffered output after the stream ends.
    """

    id: str

    def feed(self, chunk: str) -> list[Violation]:
        """Process a new chunk. Return violations triggered by this chunk."""
        ...

    def finalize(self) -> list[Violation]:
        """Called once the stream ends. Return any remaining violations."""
        ...

    def reset(self) -> None:
        """Reset internal state before a new stream begins."""
        ...


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
    def fail(
        self,
        message: str,
        severity: Severity = "medium",
        user_message: str | None = None,
        **meta: Any,
    ) -> Violation:
        return Violation(
            rule_id=self.id,
            message=message,
            severity=severity,
            meta=meta or None,
            user_message=user_message,
        )

    def ok(self) -> list[Violation]:
        return []

    async def aevaluate(self, output: Any) -> list[Violation]:
        """Async evaluation. Runs sync evaluate in a thread pool to avoid blocking the event loop.
        Override with native async logic when I/O is involved."""
        return await asyncio.to_thread(self.evaluate, output)

    @classmethod
    def from_function(
        cls,
        id: str,
        fn: Callable[..., Any],
        severity: Severity = "medium",
        user_message: str | None = None,
    ) -> BaseRule:
        """Create a rule from a plain function or generator without subclassing."""
        return rule(id=id, severity=severity, user_message=user_message)(fn)


# ---------------------------------------------------------------------------
# @rule decorator — one-liner rule authoring
# ---------------------------------------------------------------------------


def rule(
    id: str,
    severity: Severity = "medium",
    user_message: str | None = None,
) -> Callable[[Callable[..., Any]], BaseRule]:
    """
    Decorator that turns a generator (or plain function) into a Rule instance.

    The decorated function receives the evaluated output and should yield
    violation message strings. Return nothing (or None) to indicate a pass.

    Example::

        @rule(id="biz.no_competitors", severity="medium")
        def no_competitor_mentions(text: str):
            for c in ["acme", "umbrella"]:
                if c.lower() in text.lower():
                    yield f"mentioned competitor: {c}"
    """

    def decorator(fn: Callable[..., Any]) -> BaseRule:
        _id = id
        _severity = severity
        _user_msg = user_message or "Content was flagged by a safety rule."

        class _FunctionRule(BaseRule):
            __sat_key__: str = ""

        _FunctionRule.id = _id

        def _check(self: BaseRule, output: Any) -> list[Violation] | Violation | None:
            result = fn(output)
            if result is None:
                return None
            violations: list[Violation] = []
            if hasattr(result, "__iter__") and not isinstance(result, (str, bytes)):
                for item in result:
                    if item is None:
                        continue
                    violations.append(
                        Violation(
                            rule_id=_id,
                            message=str(item),
                            severity=_severity,
                            user_message=_user_msg,
                        )
                    )
            elif isinstance(result, str):
                violations.append(
                    Violation(
                        rule_id=_id,
                        message=result,
                        severity=_severity,
                        user_message=_user_msg,
                    )
                )
            return violations or None

        _FunctionRule.check = _check  # type: ignore[method-assign]
        _FunctionRule.__name__ = fn.__name__
        instance = _FunctionRule()
        instance.__sat_key__ = f"{fn.__module__}.{fn.__qualname__}"
        return instance

    return decorator
