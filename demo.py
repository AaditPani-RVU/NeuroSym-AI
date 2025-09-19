# demo.py — run: python demo.py
from neurosym.llm.gemini import GeminiLLM
from neurosym.llm.ollama import OllamaLLM
from neurosym.llm.fallback import FallbackLLM
from neurosym.engine.guard import Guard
from neurosym.rules.regex_rule import RegexRule

llm = FallbackLLM(
    primary=GeminiLLM("gemini-1.5-flash"),
    secondary=OllamaLLM("phi3:mini"),  # your local fallback
    cooldown_sec=120
)

rules = [
    RegexRule("no-email", r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b", must_not_match=True),
    RegexRule("no-phone", r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\d{10})\b", must_not_match=True),
]

guard = Guard(llm, rules, max_retries=2)
res = guard.generate("Write a short professional bio for Alex. No contacts.", temperature=0.6)
print("OUTPUT:\n", res.output)
print("\nTRACE:\n", res.report())
