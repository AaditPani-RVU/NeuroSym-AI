import re
from typing import Any, List
from .base import Rule, Violation

class RegexRule:
    def __init__(self, id: str, pattern: str, must_not_match: bool = True, flags: int = 0):
        self.id = id
        self.pattern = re.compile(pattern, flags)
        self.must_not_match = must_not_match

    def evaluate(self, output: Any) -> List[Violation]:
        text = output if isinstance(output, str) else str(output)
        m = self.pattern.search(text)
        bad = (m is not None) if self.must_not_match else (m is None)
        return [Violation(self.id, "Regex rule failed")] if bad else []
