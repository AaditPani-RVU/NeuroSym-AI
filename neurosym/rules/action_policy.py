"""Action policy rules for validating structured agent action plans.

Designed for use with voice/LLM agents that produce structured execution plans
like JARVIS's IntentResponse: {"intent": ..., "steps": [...], "requires_confirmation": bool}.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .base import BaseRule, Severity, Violation

# ---------------------------------------------------------------------------
# Pre-built action sets for common agent frameworks
# ---------------------------------------------------------------------------

#: Actions that modify or delete data — require confirmation by default.
DESTRUCTIVE_ACTIONS: frozenset[str] = frozenset(
    {
        "delete_file",
        "move_file",
        "create_file",
        "format_disk",
        "rm",
        "rmdir",
        "drop_table",
        "truncate_table",
        "overwrite_file",
        "shutdown",
        "reboot",
        "kill_process",
        "uninstall",
    }
)

#: Actions that send data externally or mutate system state.
HIGH_RISK_ACTIONS: frozenset[str] = (
    frozenset(
        {
            "send_email",
            "post_message",
            "upload_file",
            "run_script",
            "execute_command",
            "open_url",
            "web_request",
            "set_env",
            "write_registry",
        }
    )
    | DESTRUCTIVE_ACTIONS
)


# ---------------------------------------------------------------------------
# Core ActionPolicyRule
# ---------------------------------------------------------------------------


class ActionPolicyRule(BaseRule):
    """
    Validate a structured action plan dict against a policy predicate.

    The predicate receives the full parsed plan dict (or any object if you pass
    a non-dict). Return True = plan passes, False = violation.

    Example (JARVIS-style)::

        ActionPolicyRule(
            id="policy.destructive_needs_confirmation",
            policy=lambda plan: not (
                any(s["action"] in DESTRUCTIVE_ACTIONS for s in plan.get("steps", []))
                and not plan.get("requires_confirmation", False)
            ),
            message="Destructive actions require requires_confirmation=true",
            severity="high",
        )
    """

    id: str = "policy.action"

    def __init__(
        self,
        id: str,
        policy: Callable[[Any], bool],
        message: str,
        severity: Severity = "high",
    ) -> None:
        self.id = id
        self._policy = policy
        self._message = message
        self._severity = severity

    def check(self, output: Any) -> list[Violation] | Violation | None:
        try:
            passed = bool(self._policy(output))
        except Exception as exc:
            return self.fail(
                f"Policy evaluation error: {exc!r}",
                severity=self._severity,
                exception=repr(exc),
            )
        if not passed:
            return self.fail(self._message, severity=self._severity)
        return None


# ---------------------------------------------------------------------------
# Pre-built policy rules for common agent safety patterns
# ---------------------------------------------------------------------------


def destructive_needs_confirmation(
    destructive_actions: frozenset[str] | None = None,
    severity: Severity = "high",
) -> ActionPolicyRule:
    """Violation if any step is destructive and requires_confirmation is false."""
    actions = destructive_actions if destructive_actions is not None else DESTRUCTIVE_ACTIONS

    def _policy(plan: Any) -> bool:
        if not isinstance(plan, dict):
            return True
        steps = plan.get("steps", [])
        has_destructive = any(s.get("action", "") in actions for s in steps if isinstance(s, dict))
        confirmed = bool(plan.get("requires_confirmation", False))
        return not (has_destructive and not confirmed)

    return ActionPolicyRule(
        id="policy.destructive_needs_confirmation",
        policy=_policy,
        message=(
            "Plan contains destructive actions but requires_confirmation is false. "
            "Set requires_confirmation=true for safety."
        ),
        severity=severity,
    )


def no_high_risk_without_intent(
    high_risk_actions: frozenset[str] | None = None,
    severity: Severity = "high",
) -> ActionPolicyRule:
    """Violation if plan contains high-risk actions but intent field is missing or empty."""
    actions = high_risk_actions if high_risk_actions is not None else HIGH_RISK_ACTIONS

    def _policy(plan: Any) -> bool:
        if not isinstance(plan, dict):
            return True
        steps = plan.get("steps", [])
        has_high_risk = any(s.get("action", "") in actions for s in steps if isinstance(s, dict))
        has_intent = bool(plan.get("intent", "").strip())
        return not (has_high_risk and not has_intent)

    return ActionPolicyRule(
        id="policy.no_high_risk_without_intent",
        policy=_policy,
        message="High-risk actions require a non-empty intent field.",
        severity=severity,
    )


def max_steps(
    limit: int,
    severity: Severity = "medium",
) -> ActionPolicyRule:
    """Violation if action plan exceeds `limit` steps (guards against runaway plans)."""

    def _policy(plan: Any) -> bool:
        if not isinstance(plan, dict):
            return True
        return len(plan.get("steps", [])) <= limit

    return ActionPolicyRule(
        id=f"policy.max_steps.{limit}",
        policy=_policy,
        message=f"Action plan exceeds maximum allowed {limit} steps.",
        severity=severity,
    )


def no_path_outside_sandbox(
    sandbox_roots: list[str],
    severity: Severity = "critical",
) -> ActionPolicyRule:
    """
    Violation if any step parameter contains a path not under an allowed sandbox root.
    Checks all string values in step['parameters'].
    """
    import os

    normalized_roots = [os.path.normcase(os.path.abspath(r)) for r in sandbox_roots]

    def _is_safe_path(p: str) -> bool:
        norm = os.path.normcase(os.path.abspath(p))
        return any(norm.startswith(root) for root in normalized_roots)

    def _policy(plan: Any) -> bool:
        if not isinstance(plan, dict):
            return True
        for step in plan.get("steps", []):
            if not isinstance(step, dict):
                continue
            for val in step.get("parameters", {}).values():
                if isinstance(val, str) and os.sep in val:
                    if not _is_safe_path(val):
                        return False
        return True

    roots_display = ", ".join(sandbox_roots)
    return ActionPolicyRule(
        id="policy.no_path_outside_sandbox",
        policy=_policy,
        message=f"Action plan references path(s) outside allowed sandbox: {roots_display}",
        severity=severity,
    )
