# neurosym/examples/02_invoice_json.py  (fixed)
from neurosym.engine.guard import Guard
from neurosym.llm.fallback import FallbackLLM
from neurosym.llm.gemini import GeminiLLM
from neurosym.llm.ollama import OllamaLLM
from neurosym.rules.policies import policy_pii_basic
from neurosym.rules.schema_rule import SchemaRule

rules = policy_pii_basic()


invoice_schema = {
    "type": "object",
    "required": ["invoice_id", "items", "total"],
    "properties": {
        "invoice_id": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "price"],
                "properties": {
                    "name": {"type": "string"},
                    "price": {"type": "number", "minimum": 0},
                },
            },
        },
    },
    "total": {"type": "number", "minimum": 0},
}


primary = GeminiLLM(
    model="gemini-1.5-flash",
    # Ask Gemini to produce JSON, but DO NOT pass our JSON Schema here
    response_mime_type="application/json",
)
secondary = OllamaLLM(model="phi3:mini")  # your fallback choice
llm = FallbackLLM(primary, secondary)

rules = [SchemaRule("invoice-schema", schema=invoice_schema)]
guard = Guard(llm=llm, rules=rules, max_retries=2)

doc = """Invoice: #INV-7742
Items:
- Widget A, 2 units x 12.5
- Widget B, 1 unit x 24.0
Total due: 49.0 USD
"""
prompt = (
    "Extract an invoice **as a single JSON object** with fields: "
    "invoice_id (string), items (array of {name, price:number}), total (number).\n"
    "Return **ONLY** JSON, no prose.\n\n"
    f"Source:\n{doc}"
)

res = guard.generate(prompt, temperature=0.2)
print("JSON OUTPUT:\n", res.output)
print("\nTRACE:\n", res.report())
