# examples/02_invoice_json.py
from neurosym.llm.gemini import GeminiLLM
from neurosym.llm.ollama import OllamaLLM
from neurosym.llm.fallback import FallbackLLM
from neurosym.engine.guard import Guard
from neurosym.rules.schema_rule import SchemaRule

invoice_schema = {
  "type": "object",
  "required": ["invoice_id", "items", "total"],
  "properties": {
    "invoice_id": {"type": "string"},
    "items": {"type": "array", "items": {"type": "object",
              "required": ["name", "price"],
              "properties": {
                  "name": {"type": "string"},
                  "price": {"type": "number", "minimum": 0}
              }}}},
    "total": {"type": "number", "minimum": 0}
  }


primary = GeminiLLM(
    model="gemini-1.5-flash",
    response_mime_type="application/json",
    response_schema=invoice_schema,
)
secondary = OllamaLLM(model="llama3:8b")
llm = FallbackLLM(primary, secondary)

rules = [SchemaRule("invoice-schema", schema=invoice_schema)]
guard = Guard(llm=llm, rules=rules, max_retries=2)

doc = """Invoice: #INV-7742
Items:
- Widget A, 2 units x 12.5
- Widget B, 1 unit x 24.0
Total due: 49.0 USD
"""
prompt = f"Extract an invoice in JSON that matches the schema from this text:\n{doc}\nReturn only JSON."

res = guard.generate(prompt, temperature=0.2)
print("JSON OUTPUT:\n", res.output)
print("\nTRACE:\n", res.report())
