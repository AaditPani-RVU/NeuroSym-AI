# neurosym/examples/00_smoke.py

import re

from neurosym.engine.guard import Guard
from neurosym.rules.policies import DenyIfContains, MaxLengthRule
from neurosym.rules.regex_rule import RegexRule
from neurosym.rules.schema_rule import SchemaRule


# ---- 1) a tiny, offline LLM stub ----
class StubLLM:
    """
    Deterministic stub so you can test guard + rules with no network.
    It returns a first attempt that violates schema, then a repaired one.
    """

    def __init__(self):
        self.calls = 0

    def generate(self, prompt: str, **kwargs) -> str:
        self.calls += 1
        # First call: return invalid JSON (missing 'currency')
        if self.calls == 1:
            return '{"invoice_id": "INV-42", "amount": 99.5}'
        # Second+ call: return valid JSON that satisfies the schema
        return '{"invoice_id": "INV-42", "amount": 99.5, "currency": "USD"}'


# ---- 2) a small JSON schema we will validate against ----
invoice_schema = {
    "type": "object",
    "properties": {
        "invoice_id": {"type": "string"},
        "amount": {"type": "number", "minimum": 0},
        "currency": {"type": "string"},
    },
    "required": ["invoice_id", "amount", "currency"],
    "additionalProperties": False,
}


def main():
    # ---- 3) set up rules ----
    rules = [
        # must NOT contain emails (PII)
        RegexRule(
            id="safety.no_email",
            pattern=r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
            must_not_match=True,
            flags=re.IGNORECASE,
        ),
        # deny certain text fragments
        DenyIfContains(id="policy.block_terms", banned=["wire fraud", "malware"]),
        # cap output length (sanity)
        MaxLengthRule(id="fmt.max_len", max_len=8000),
        # validate final JSON shape
        SchemaRule(id="schema.invoice", schema=invoice_schema),
    ]

    # ---- 4) run guard with stub LLM ----
    guard = Guard(llm=StubLLM(), rules=rules, max_retries=2)

    user_text = "Please extract invoice details for INV-42 ($99.5 USD). Contact: ada@example.com"
    # NOTE: The first rule will flag the email; the schema will be missing 'currency' first,
    # and then the StubLLM returns a repaired JSON on retry.

    result = guard.generate(
        prompt=(
            "Extract the invoice as strict JSON with keys: invoice_id, amount, currency.\n"
            f"Input: '''{user_text}'''"
        )
    )

    print("=== FINAL OUTPUT ===")
    print(result.output)
    print("\n=== TRACE (compact) ===")
    print(result.report())
    print("\n=== TRACE (full) ===")
    print(result.to_dict())


if __name__ == "__main__":
    main()
