# neurosym/examples/02_text_policy_with_redaction.py
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


def main():
    user_text = "Contact me at ada@example.com about the wire fraud case."

    # 1) redact first
    red = Redactor().apply(user_text)
    print("REDACTED:", red.text)
    # e.g., "Contact me at [REDACTED:EMAIL] about the wire fraud case."

    # 2) then guard (now email regex should pass)
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
    guard = Guard(llm=EchoLLM(red.text), rules=rules, max_retries=0)
    res = guard.generate("reply briefly")
    print("TRACE:", res.report())


if __name__ == "__main__":
    main()
