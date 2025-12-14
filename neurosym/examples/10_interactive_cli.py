# neurosym/examples/10_interactive_cli.py
from __future__ import annotations

import json
import re
import sys
from typing import Any

from neurosym.engine.guard import Guard
from neurosym.rules.policies import DenyIfContains, MaxLengthRule
from neurosym.rules.regex_rule import RegexRule

# OPTIONAL redaction (comment out if you didn't add the pre/ module)
try:
    from neurosym.pre.redaction import Redactor

    HAVE_REDACTOR = True
except Exception:
    HAVE_REDACTOR = False


# Try local LLM (Ollama). Fall back to a tiny echo model if unavailable.
class EchoLLM:
    def generate(self, prompt: str, **_):
        # trivial, deterministic fallback
        return "Acknowledged. (fallback response)"


def get_llm():
    try:
        from neurosym.llm.ollama import OllamaLLM

        return OllamaLLM(model="phi3:mini")
    except Exception as e:
        print(
            f"[info] Using EchoLLM fallback (Ollama not available or import failed: {e})"
        )
        return EchoLLM()


def build_rules() -> list[Any]:
    return [
        RegexRule(
            "safety.no_email",
            r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
            must_not_match=True,
            flags=re.IGNORECASE,
        ),
        DenyIfContains("policy.block_terms", ["wire fraud", "malware"]),
        MaxLengthRule("fmt.max_len", 8000),
    ]


def main():
    print("=== NeuroSym-AI Interactive Guard ===")
    print("Type 'exit' to quit.\n")

    # choose redaction mode
    redact = False
    if HAVE_REDACTOR:
        ans = input("Enable PII redaction pre-processing? [y/N]: ").strip().lower()
        redact = ans == "y"

    # retries
    try:
        retries = int(input("Max repair retries (default 1): ").strip() or "1")
    except ValueError:
        retries = 1

    llm = get_llm()
    rules = build_rules()
    guard = Guard(llm=llm, rules=rules, max_retries=retries)

    while True:
        print("\n---")
        task = input("Task (e.g., 'Summarize', 'Extract JSON', etc.): ").strip()
        if task.lower() == "exit":
            break
        text = input("Your input text: ").strip()
        if text.lower() == "exit":
            break

        # optional redact
        effective_text = text
        if redact and HAVE_REDACTOR:
            red = Redactor().apply(text)
            effective_text = red.text
            if red.hits:
                print(f"[redactor] {len(red.hits)} item(s) redacted in input.")

        # build prompt (simple)
        prompt = f"{task}.\nInput: '''{effective_text}'''"

        result = guard.generate(prompt)

        print("\n=== FINAL OUTPUT ===")
        print(result.output)

        print("\n=== TRACE (compact) ===")
        print(result.report())

        # show first-attempt violations with details
        if result.trace and result.trace[-1].violations:
            print("\n=== LAST ATTEMPT VIOLATIONS (detailed) ===")
            for v in result.trace[-1].violations:
                print(f"- {v['rule_id']}: {v['message']}")
                if v.get("meta"):
                    print("  meta:", json.dumps(v["meta"], ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nbye!")
        sys.exit(0)
