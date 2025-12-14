# neurosym/rules/regex_rule.py
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from .base import Violation


class RegexRule:  # implements Rule
    """
    Validate text against one or more regex patterns.

    Default behavior matches your original rule:
      - 'pattern' may be a str or list[str]
      - by default the rule is a "must_not_match" guard (deny on any match)

    Extras:
      - mode: "any" | "all"
        * With must_not_match=True:
            - "any": violation if ANY pattern matches (default; same as before)
            - "all": violation if ALL patterns match
        * With must_not_match=False (i.e., must match):
            - "any": violation if NONE of the patterns match
            - "all": violation if ANY pattern does NOT match
      - normalize_ws: collapse whitespace before matching
      - max_examples: limit number of example matches reported in meta
    """

    def __init__(
        self,
        id: str,
        pattern: str | Iterable[str],
        must_not_match: bool = True,
        flags: int = 0,
        *,
        mode: str = "any",
        normalize_ws: bool = False,
        max_examples: int = 3,
    ) -> None:
        self.id = id
        self.must_not_match = must_not_match
        self.mode = mode.lower()
        if self.mode not in {"any", "all"}:
            raise ValueError("mode must be 'any' or 'all'")
        self.normalize_ws = normalize_ws
        self.max_examples = max(0, int(max_examples))

        # compile patterns
        if isinstance(pattern, str):
            patterns = [pattern]
        else:
            patterns = list(pattern)
            if not patterns:
                raise ValueError("pattern list must not be empty")
        self._compiled: list[tuple[str, re.Pattern[str]]] = [
            (p, re.compile(p, flags)) for p in patterns
        ]
        self._flags = flags

    # ---- Rule API ----
    def evaluate(self, output: Any) -> list[Violation]:
        text = output if isinstance(output, str) else str(output)
        if self.normalize_ws:
            text = " ".join(text.split())

        # collect matches for each pattern
        per_pattern = []
        for p_str, p_re in self._compiled:
            matches = list(p_re.finditer(text))
            per_pattern.append((p_str, matches))

        # decide pass/fail based on must_not_match + mode
        if self.must_not_match:
            # Violate when we detect matches (depending on mode)
            violates = (
                any(len(m) > 0 for _, m in per_pattern)
                if self.mode == "any"
                else all(len(m) > 0 for _, m in per_pattern)
            )
            message = "Regex matched but it must NOT match"
        else:
            # Must match => violate when missing matches (depending on mode)
            violates = (
                all(len(m) == 0 for _, m in per_pattern)
                if self.mode == "any"
                else any(len(m) == 0 for _, m in per_pattern)
            )
            message = "Regex did NOT match but it MUST match"

        if not violates:
            return []

        meta = {
            "must_not_match": self.must_not_match,
            "mode": self.mode,
            "flags": self._flags,
            "patterns": [
                {
                    "pattern": p,
                    "match_count": len(ms),
                    "examples": [
                        {
                            "text": _safe_group_text(m),
                            "span": m.span(),
                        }
                        for m in ms[: self.max_examples]
                    ],
                }
                for (p, ms) in per_pattern
            ],
            "text_length": len(text),
        }
        return [Violation(rule_id=self.id, message=message, meta=meta)]


def _safe_group_text(m: re.Match) -> str:
    """
    Return a small, printable snippet for a match object without exploding logs.
    """
    s = m.group(0)
    # Cap length to keep traces compact (you can tweak if needed).
    if len(s) > 160:
        s = s[:160] + "…"
    return s
