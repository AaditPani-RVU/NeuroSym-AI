# neurosym/rules/policies.py
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from .base import Violation


class DenyIfContains:  # implements Rule
    """Violation if the (stringified) output contains any banned substring."""

    def __init__(self, id: str, banned: Iterable[str], case_insensitive: bool = True) -> None:
        self.id = id
        self._banned = list(banned)
        self._ci = case_insensitive

    def evaluate(self, output: Any) -> list[Violation]:
        text = output if isinstance(output, str) else str(output)
        hay = text.lower() if self._ci else text
        hits = [w for w in self._banned if (w.lower() in hay if self._ci else w in hay)]
        if hits:
            return [
                Violation(
                    rule_id=self.id,
                    message="Contains banned substrings",
                    meta={"hits": hits},
                )
            ]
        return []


class MaxLengthRule:  # implements Rule
    """Violation if the stringified output exceeds `max_len` characters."""

    def __init__(self, id: str, max_len: int) -> None:
        self.id = id
        self._max = int(max_len)

    def evaluate(self, output: Any) -> list[Violation]:
        text = output if isinstance(output, str) else str(output)
        n = len(text)
        if n > self._max:
            return [
                Violation(
                    rule_id=self.id,
                    message="Output too long",
                    meta={"length": n, "max": self._max},
                )
            ]
        return []


class DenyIfRegex:  # implements Rule
    """Violation if any regex matches the (stringified) output."""

    def __init__(
        self,
        id: str,
        patterns: Iterable[str],
        flags: int = re.IGNORECASE | re.MULTILINE,
    ) -> None:
        self.id = id
        self._compiled = [re.compile(p, flags) for p in patterns]

    def evaluate(self, output: Any) -> list[Violation]:
        text = output if isinstance(output, str) else str(output)
        hits = []
        for rx in self._compiled:
            m = rx.search(text)
            if m:
                hits.append({"pattern": rx.pattern, "span": m.span()})
        if hits:
            return [
                Violation(
                    rule_id=self.id,
                    message="Matched denied pattern(s)",
                    meta={"matches": hits},
                )
            ]
        return []
