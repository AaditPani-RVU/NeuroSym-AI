from neurosym.engine.guard import Guard
from neurosym.rules.policies import DenyIfContains
from neurosym.rules.regex_rule import RegexRule


class DummyLLM:
    def __init__(self, outputs):
        self.outputs = outputs
        self.i = 0

    def generate(self, prompt: str, **kwargs) -> str:
        out = self.outputs[min(self.i, len(self.outputs) - 1)]
        self.i += 1
        return out

    def stream(self, prompt: str, **kwargs):
        yield self.generate(prompt, **kwargs)


def test_guard_repair_loop():
    llm = DummyLLM(["email me a@b.com", "no contact info here"])
    rules = [RegexRule("no-email", r"\S+@\S+", must_not_match=True)]
    guard = Guard(llm=llm, rules=rules, max_retries=2)
    res = guard.generate("test")
    assert "a@b.com" not in res.output
    assert len(res.trace) >= 2


def test_ok_stays_false_with_sub_threshold_violations():
    # Regression: deny_rule_ids targets one rule but other rules also fire.
    # ok must remain False (len(violations) > 0).
    # blocked mirrors ok (= True), but hard_denied is False because the targeted
    # hard-deny rule did not trigger — callers can use hard_denied to distinguish
    # severity routing from the overall pass/fail decision.
    rules = [
        RegexRule("safety.no_email", r"\S+@\S+", must_not_match=True),
        DenyIfContains(id="policy.no_fraud", banned=["fraud"]),
    ]
    guard = Guard(rules=rules, deny_rule_ids={"safety.no_email"})
    # "fraud" triggers policy.no_fraud but NOT safety.no_email
    res = guard.apply_text("this is a fraud scheme")
    assert res.ok is False, "ok must be False when any violation exists"
    assert res.blocked is True, "blocked always mirrors not ok"
    assert res.hard_denied is False, "hard_denied must be False — hard-deny rule was not triggered"
    assert any(v["rule_id"] == "policy.no_fraud" for v in res.violations)


def test_ok_and_blocked_and_hard_denied_when_hard_deny_triggers():
    # When the deny_rule_ids target fires, ok=False, blocked=True, hard_denied=True.
    rules = [RegexRule("safety.no_email", r"\S+@\S+", must_not_match=True)]
    guard = Guard(rules=rules, deny_rule_ids={"safety.no_email"})
    res = guard.apply_text("contact me at x@example.com")
    assert res.ok is False
    assert res.blocked is True
    assert res.hard_denied is True


def test_ok_true_when_no_violations():
    rules = [DenyIfContains(id="policy.no_fraud", banned=["fraud"])]
    guard = Guard(rules=rules, deny_rule_ids={"policy.no_fraud"})
    res = guard.apply_text("everything looks fine")
    assert res.ok is True
    assert res.blocked is False
    assert res.hard_denied is False
