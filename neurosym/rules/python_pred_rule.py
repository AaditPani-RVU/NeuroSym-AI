from collections.abc import Callable
from typing import Any

from .base import Violation


class PythonPredicateRule:
    def __init__(self, id: str, predicate: Callable[[Any], bool], message: str):
        self.id = id
        self._pred = predicate
        self._msg = message

    def evaluate(self, output: Any) -> list[Violation]:
        try:
            ok = bool(self._pred(output))
        except Exception as e:
            return [Violation(self.id, f"Predicate error: {e!r}")]
        return [] if ok else [Violation(self.id, self._msg)]
