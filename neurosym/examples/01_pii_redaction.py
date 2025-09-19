# examples/01_pii_redaction.py
from neurosym.llm.gemini import GeminiLLM
from neurosym.llm.ollama import OllamaLLM
from neurosym.llm.fallback import FallbackLLM
from neurosym.engine.guard import Guard
from neurosym.rules.regex_rule import RegexRule
from neurosym.rules.policies import policy_pii_basic
rules = policy_pii_basic()


# export GEMINI_API_KEY before running; optionally run Ollama locally
primary = GeminiLLM(model="gemini-1.5-flash")
secondary = OllamaLLM(model="phi3:mini")

llm = FallbackLLM(primary, secondary, cooldown_sec=120)

rules = [
    RegexRule("no-email", r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b", must_not_match=True),
    RegexRule("no-phone", r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\d{10})\b", must_not_match=True),
]

guard = Guard(llm=llm, rules=rules, max_retries=2)

prompt = "Write a short bio of Alex (skills: Python, robotics). Do not include any emails or phone numbers."
res = guard.generate(prompt, temperature=0.7)

print("OUTPUT:\n", res.output)
print("\nTRACE:\n", res.report())
