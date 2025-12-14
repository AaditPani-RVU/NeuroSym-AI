from neurosym.engine.guard import Guard
from neurosym.rules.regex_rule import RegexRule


class DummyLLM:
    def __init__(self, outputs):
        self.outputs = outputs
        self.i = 0

    def generate(self, prompt: str, **kwargs) -> str:
        out = self.outputs[min(self.i, len(self.outputs) - 1)]
        self.i += 1
        return out

    def stream(self, prompt: str, **kwargs):
        yield self.generate(prompt, **kwargs)


def test_guard_repair_loop():
    llm = DummyLLM(["email me a@b.com", "no contact info here"])
    rules = [RegexRule("no-email", r"\S+@\S+", must_not_match=True)]
    guard = Guard(llm=llm, rules=rules, max_retries=2)
    res = guard.generate("test")
    assert "a@b.com" not in res.output
    assert len(res.trace) >= 2
