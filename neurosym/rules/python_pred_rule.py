from typing import Any, Callable, List
from .base import Rule, Violation

class PythonPredicateRule:
    def __init__(self, id: str, predicate: Callable[[Any], bool], message: str):
        self.id = id
        self._pred = predicate
        self._msg = message

    def evaluate(self, output: Any) -> List[Violation]:
        try:
            ok = bool(self._pred(output))
        except Exception as e:
            return [Violation(self.id, f"Predicate error: {e!r}")]
        return [] if ok else [Violation(self.id, self._msg)]
