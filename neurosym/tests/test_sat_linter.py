"""Regression tests for the SAT/Z3 policy linter."""

import pytest

pytest.importorskip("z3", reason="z3-solver not installed")

from neurosym.policy.sat import lint
from neurosym.rules.base import rule
from neurosym.rules.composite import AllOf, Not
from neurosym.rules.policies import DenyIfContains


def _make_rule(rule_id: str, banned: list[str]) -> DenyIfContains:
    return DenyIfContains(id=rule_id, banned=banned)


@rule(id="decorated.alpha")
def _decorated_alpha_rule(output: object):
    yield "alpha violation"


@rule(id="decorated.beta")
def _decorated_beta_rule(output: object):
    yield "beta violation"


def _shared_decorated_function(output: object):
    yield "shared violation"


def test_equivalent_separate_instances_detected_as_unsatisfiable():
    # Regression: two separately constructed rules with identical class + config
    # must share a Z3 variable so contradictions between them are still detected.
    r1 = _make_rule("check.a", ["foo"])
    r2 = _make_rule("check.b", ["foo"])  # same config, different object/id
    assert r1 is not r2
    issues = lint(AllOf([r1, Not(r2)]))
    assert any(i.kind == "unsatisfiable" for i in issues), (
        "AllOf([r, Not(r_equivalent)]) must be reported as unsatisfiable: " + str(issues)
    )
    unsatisfiable = [i for i in issues if i.kind == "unsatisfiable"]
    assert unsatisfiable[0].rules_involved == ["check.a", "check.b"]


def test_different_config_with_different_ids_not_unsatisfiable():
    # Different semantic config must keep independent Z3 variables, even when
    # the formula shape would be contradictory for equivalent rules.
    r1 = _make_rule("check.a", ["foo"])
    r2 = _make_rule("check.b", ["bar"])
    issues = lint(AllOf([r1, Not(r2)]))
    assert not any(i.kind == "unsatisfiable" for i in issues), (
        "AllOf([r, Not(r_different)]) must not be reported as unsatisfiable: " + str(issues)
    )


def test_different_rule_decorated_functions_not_unsatisfiable():
    # Regression: @rule instances all use the same inner _FunctionRule class.
    # Different wrapped functions must still produce independent SAT variables.
    issues = lint(AllOf([_decorated_alpha_rule, Not(_decorated_beta_rule)]))
    assert not any(i.kind == "unsatisfiable" for i in issues), (
        "Different @rule-decorated functions must not share a SAT variable: " + str(issues)
    )


def test_same_rule_decorated_function_is_unsatisfiable():
    # Wrapping the same function twice should share one SAT variable despite
    # different display ids, so AllOf([r, Not(r_equivalent)]) is contradictory.
    r1 = rule(id="decorated.same.a")(_shared_decorated_function)
    r2 = rule(id="decorated.same.b")(_shared_decorated_function)
    assert r1.__sat_key__ == r2.__sat_key__
    issues = lint(AllOf([r1, Not(r2)]))
    assert any(i.kind == "unsatisfiable" for i in issues), (
        "Same @rule-decorated function must share a SAT variable: " + str(issues)
    )


def test_same_id_different_config_not_subsumed():
    # Regression: two rules sharing the same rule.id but different banned lists
    # must NOT be reported as equivalent/subsumed — they cover different inputs.
    r1 = _make_rule("check.forbidden", ["foo"])
    r2 = _make_rule("check.forbidden", ["bar"])
    issues = lint(AllOf([r1, r2]))
    subsumed = [i for i in issues if i.kind == "subsumed"]
    assert subsumed == [], (
        "Rules with the same id but different configs must not be reported as subsumed: "
        + str(subsumed)
    )


def test_same_instance_is_subsumed():
    # A rule combined with itself IS logically equivalent — linter must still catch this.
    r = _make_rule("check.forbidden", ["foo"])
    issues = lint(AllOf([r, r]))
    assert any(i.kind == "subsumed" for i in issues)


def test_truly_unsatisfiable_policy():
    # AllOf([r, Not(r)]) is always unsatisfiable (r fires AND r must not fire).
    r = _make_rule("check.forbidden", ["foo"])
    issues = lint(AllOf([r, Not(r)]))
    assert any(i.kind == "unsatisfiable" for i in issues)


def test_clean_policy_has_no_issues():
    r1 = _make_rule("check.a", ["foo"])
    r2 = _make_rule("check.b", ["bar"])
    issues = lint(AllOf([r1, r2]))
    assert issues == []
