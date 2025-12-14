from neurosym.rules.regex_rule import RegexRule
from neurosym.rules.schema_rule import SchemaRule


def test_regex_rule_blocks_email():
    r = RegexRule(
        "no-email", r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b", must_not_match=True
    )
    assert r.evaluate("contact me at a@b.com")
    assert not r.evaluate("no emails here")


def test_schema_ok_and_fail():
    r = SchemaRule(
        "schema",
        {"type": "object", "required": ["a"], "properties": {"a": {"type": "number"}}},
    )
    assert not r.evaluate('{"a": 3}')
    assert r.evaluate('{"a": "x"}')
