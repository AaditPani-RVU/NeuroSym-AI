# neurosym/tests/test_text_policy.py
import re

from neurosym.engine.guard import Guard
from neurosym.rules.policies import DenyIfContains, MaxLengthRule
from neurosym.rules.regex_rule import RegexRule


class StubLLM:
    """
    Deterministic LLM stub:
      - 1st call returns text that violates both regex + policy rules.
      - 2nd call returns a clean, compliant text.
    """

    def __init__(self):
        self.calls = 0

    def generate(self, prompt: str, **kwargs) -> str:
        self.calls += 1
        if self.calls == 1:
            return "Contact me at ada@example.com about the wire fraud case."
        return "Please advise on the case details."


def test_regex_policy_clean_after_repair():
    rules = [
        # Must NOT contain emails
        RegexRule(
            id="safety.no_email",
            pattern=r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
            must_not_match=True,
            flags=re.IGNORECASE,
        ),
        # Must NOT contain banned phrase
        DenyIfContains(id="policy.no_wire_fraud", banned=["wire fraud"]),
        # Keep output within sane length
        MaxLengthRule(id="fmt.max_len", max_len=2000),
    ]

    guard = Guard(llm=StubLLM(), rules=rules, max_retries=2)

    res = guard.generate("Reply to the user briefly.")
    # Final output should be the cleaned version
    assert res.output == "Please advise on the case details."
    # First attempt should have both violations; second none
    assert len(res.trace) == 2
    v_ids_attempt1 = {v["rule_id"] for v in res.trace[0].violations}
    assert "safety.no_email" in v_ids_attempt1
    assert "policy.no_wire_fraud" in v_ids_attempt1
    assert res.trace[1].violations == []
