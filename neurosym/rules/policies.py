# neurosym/rules/policies.py
from .regex_rule import RegexRule

def policy_pii_basic():
    return [
        RegexRule("no-email", r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
        RegexRule("no-phone", r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\d{10})\b"),
    ]

def policy_json_only():
    # ensures no angle-bracket tags or triple backticks etc.
    return [
        RegexRule("no-md-codefence", r"```", must_not_match=True),
        RegexRule("no-xml-tags", r"<[^>]+>", must_not_match=True),
    ]
