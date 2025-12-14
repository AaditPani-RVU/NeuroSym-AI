# neurosym/tests/test_redaction_then_guard.py
import re

from neurosym.engine.guard import Guard
from neurosym.pre.redaction import Redactor
from neurosym.rules.policies import DenyIfContains, MaxLengthRule
from neurosym.rules.regex_rule import RegexRule


class EchoLLM:
    def __init__(self, reply: str):
        self.reply = reply

    def generate(self, prompt: str, **_):
        return self.reply


def test_redaction_prevents_email_violation():
    text = "Contact ada@example.com to discuss wire fraud."
    red = Redactor().apply(text)

    # email should be redacted
    assert "[REDACTED:EMAIL]" in red.text
    assert any(h.kind == "email" for h in red.hits)

    rules = [
        RegexRule(
            "safety.no_email",
            r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
            must_not_match=True,
            flags=re.IGNORECASE,
        ),
        DenyIfContains("policy.no_wire_fraud", ["wire fraud"]),
        MaxLengthRule("fmt.max_len", 2000),
    ]
    res = Guard(llm=EchoLLM(red.text), rules=rules, max_retries=0).generate("say hi")

    # email violation gone, policy remains
    v1 = {v["rule_id"] for v in res.trace[0].violations}
    assert "safety.no_email" not in v1
    assert "policy.no_wire_fraud" in v1
