"""Tests for ActionPolicyRule and pre-built policy factories."""

from neurosym.rules.action_policy import (
    ActionPolicyRule,
    destructive_needs_confirmation,
    max_steps,
    no_high_risk_without_intent,
)


def _plan(intent: str, actions: list[str], confirmed: bool = False) -> dict:
    return {
        "intent": intent,
        "steps": [{"action": a, "parameters": {}} for a in actions],
        "requires_confirmation": confirmed,
    }


class TestActionPolicyRule:
    def test_custom_predicate_passes(self) -> None:
        rule = ActionPolicyRule(
            id="test.custom",
            policy=lambda x: isinstance(x, dict),
            message="Must be a dict",
        )
        assert not rule.evaluate({"intent": "open chrome", "steps": []})

    def test_custom_predicate_fails(self) -> None:
        rule = ActionPolicyRule(
            id="test.custom",
            policy=lambda x: isinstance(x, dict),
            message="Must be a dict",
        )
        viols = rule.evaluate("not a dict")
        assert viols
        assert viols[0].rule_id == "test.custom"

    def test_predicate_exception_produces_violation(self) -> None:
        def bad_policy(x: object) -> bool:
            raise RuntimeError("boom")

        rule = ActionPolicyRule(id="test.bad", policy=bad_policy, message="boom")
        viols = rule.evaluate({})
        assert viols
        assert "Policy evaluation error" in viols[0].message


class TestDestructiveNeedsConfirmation:
    def setup_method(self) -> None:
        self.rule = destructive_needs_confirmation()

    def test_safe_action_no_confirmation_needed(self) -> None:
        plan = _plan("open chrome", ["open_app"])
        assert not self.rule.evaluate(plan)

    def test_destructive_without_confirmation_blocked(self) -> None:
        plan = _plan("delete file", ["delete_file"], confirmed=False)
        viols = self.rule.evaluate(plan)
        assert viols
        assert viols[0].severity == "high"

    def test_destructive_with_confirmation_passes(self) -> None:
        plan = _plan("delete file", ["delete_file"], confirmed=True)
        assert not self.rule.evaluate(plan)

    def test_multiple_destructive_steps_blocked(self) -> None:
        plan = _plan("cleanup", ["delete_file", "move_file"], confirmed=False)
        assert self.rule.evaluate(plan)

    def test_non_dict_passes(self) -> None:
        assert not self.rule.evaluate("not a plan")


class TestMaxSteps:
    def test_within_limit_passes(self) -> None:
        rule = max_steps(5)
        plan = _plan("multi", ["open_app", "open_app", "open_app"])
        assert not rule.evaluate(plan)

    def test_exceeds_limit_blocked(self) -> None:
        rule = max_steps(2)
        plan = _plan("many steps", ["a", "b", "c"])
        viols = rule.evaluate(plan)
        assert viols
        assert "3" in viols[0].message or "2" in viols[0].message

    def test_exactly_at_limit_passes(self) -> None:
        rule = max_steps(3)
        plan = _plan("three", ["a", "b", "c"])
        assert not rule.evaluate(plan)


class TestNoHighRiskWithoutIntent:
    def setup_method(self) -> None:
        self.rule = no_high_risk_without_intent()

    def test_high_risk_with_intent_passes(self) -> None:
        plan = _plan("send report", ["send_email"])
        assert not self.rule.evaluate(plan)

    def test_high_risk_without_intent_blocked(self) -> None:
        plan = {"intent": "", "steps": [{"action": "send_email", "parameters": {}}]}
        viols = self.rule.evaluate(plan)
        assert viols

    def test_low_risk_without_intent_passes(self) -> None:
        plan = {"intent": "", "steps": [{"action": "open_app", "parameters": {}}]}
        assert not self.rule.evaluate(plan)
