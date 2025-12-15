# neurosym/examples/03_local_phi3.py
import re

from neurosym.engine.guard import Guard
from neurosym.llm.ollama import OllamaLLM

# add:
from neurosym.pre.redaction import Redactor
from neurosym.rules.policies import DenyIfContains, MaxLengthRule
from neurosym.rules.regex_rule import RegexRule


def main():
    llm = OllamaLLM(model="phi3:mini")

    rules = [
        RegexRule(
            "safety.no_email",
            r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
            must_not_match=True,
            flags=re.IGNORECASE,
        ),
        DenyIfContains("policy.block_terms", ["wire fraud", "malware"]),
        MaxLengthRule("fmt.max_len", 2000),
    ]

    guard = Guard(llm=llm, rules=rules, max_retries=2, deny_rule_ids={"safety.no_email"})

    user_text = (
        "Summarize this: 'Contact ada@exampleinvoiceservice.com to finalize invoice "
        "INV-42 worth 99.5 USD. Do not leak any personal data.'"
    )

    # 1) redact INPUT
    red_in = Redactor().apply(user_text)
    prompt = f"Summarize the following without revealing PII. Input: '''{red_in.text}'''"

    # 2) Guarded generation (repairs will try; hard-stop on email rule)
    result = guard.generate(prompt, temperature=0.2, max_tokens=256)

    # 3) POST-REDACT OUTPUT (belt-and-suspenders)
    red_out = Redactor().apply(result.output)

    print("=== FINAL OUTPUT (redacted) ===")
    print(red_out.text)
    print("\n=== TRACE ===")
    print(result.report())


if __name__ == "__main__":
    main()
