# neurosym/examples/01_text_policy_smoke.py
import re

from neurosym.engine.guard import Guard
from neurosym.rules.policies import DenyIfContains, MaxLengthRule
from neurosym.rules.regex_rule import RegexRule


class StubLLM:
    def __init__(self):
        self.calls = 0

    def generate(self, prompt: str, **kwargs) -> str:
        self.calls += 1
        if self.calls == 1:
            return "Contact me at ada@example.com about the wire fraud case."
        return "Please advise on the case details."


def main():
    rules = [
        RegexRule(
            id="safety.no_email",
            pattern=r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
            must_not_match=True,
            flags=re.IGNORECASE,
        ),
        DenyIfContains(id="policy.no_wire_fraud", banned=["wire fraud"]),
        MaxLengthRule(id="fmt.max_len", max_len=2000),
    ]
    guard = Guard(llm=StubLLM(), rules=rules, max_retries=2)

    result = guard.generate("Reply to the user briefly.")
    print("=== FINAL OUTPUT ===")
    print(result.output)
    print("\n=== TRACE (compact) ===")
    print(result.report())
    print("\n=== TRACE (full) ===")
    print(result.to_dict())


if __name__ == "__main__":
    main()
