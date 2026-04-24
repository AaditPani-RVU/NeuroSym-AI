"""Tests for composite rule combinators: AllOf, AnyOf, Not, Implies."""

from neurosym.rules.base import BaseRule, Violation
from neurosym.rules.composite import AllOf, AnyOf, Implies, Not


class AlwaysPass(BaseRule):
    id = "test.always_pass"

    def check(self, output: object) -> None:
        return None


class AlwaysFail(BaseRule):
    id = "test.always_fail"

    def check(self, output: object) -> Violation:
        return self.fail("always fails", severity="low")


class TestAllOf:
    def test_all_pass_returns_no_violations(self) -> None:
        rule = AllOf([AlwaysPass(), AlwaysPass()], id="all_pass")
        assert not rule.evaluate("anything")

    def test_any_fail_returns_violations(self) -> None:
        rule = AllOf([AlwaysPass(), AlwaysFail()], id="mixed")
        viols = rule.evaluate("anything")
        assert viols
        assert viols[0].rule_id == "test.always_fail"

    def test_all_fail_returns_all_violations(self) -> None:
        rule = AllOf([AlwaysFail(), AlwaysFail()], id="all_fail")
        viols = rule.evaluate("anything")
        assert len(viols) == 2

    def test_severity_override(self) -> None:
        rule = AllOf([AlwaysFail()], id="sev_override", severity="critical")
        viols = rule.evaluate("anything")
        assert viols[0].severity == "critical"


class TestAnyOf:
    def test_at_least_one_pass_returns_no_violations(self) -> None:
        rule = AnyOf([AlwaysFail(), AlwaysPass()], id="any_pass")
        assert not rule.evaluate("anything")

    def test_all_fail_returns_violation(self) -> None:
        rule = AnyOf([AlwaysFail(), AlwaysFail()], id="all_fail")
        viols = rule.evaluate("anything")
        assert viols
        assert viols[0].rule_id == "all_fail"

    def test_all_pass_returns_no_violations(self) -> None:
        rule = AnyOf([AlwaysPass(), AlwaysPass()], id="all_pass")
        assert not rule.evaluate("anything")


class TestNot:
    def test_inner_passes_produces_violation(self) -> None:
        rule = Not(AlwaysPass(), id="not_pass")
        viols = rule.evaluate("anything")
        assert viols

    def test_inner_fails_produces_no_violation(self) -> None:
        rule = Not(AlwaysFail(), id="not_fail")
        assert not rule.evaluate("anything")

    def test_custom_message(self) -> None:
        rule = Not(AlwaysPass(), id="test.not", message="must not pass")
        viols = rule.evaluate("x")
        assert viols[0].message == "must not pass"


class TestImplies:
    def test_condition_false_consequence_ignored(self) -> None:
        rule = Implies(AlwaysFail(), AlwaysFail(), id="impl_skip")
        assert not rule.evaluate("anything")

    def test_condition_true_consequence_passes(self) -> None:
        rule = Implies(AlwaysPass(), AlwaysPass(), id="impl_pass")
        assert not rule.evaluate("anything")

    def test_condition_true_consequence_fails_produces_violation(self) -> None:
        rule = Implies(AlwaysPass(), AlwaysFail(), id="impl_fail")
        viols = rule.evaluate("anything")
        assert viols

    def test_violation_severity(self) -> None:
        rule = Implies(AlwaysPass(), AlwaysFail(), id="impl_sev", severity="critical")
        viols = rule.evaluate("anything")
        assert viols[0].severity == "critical"
