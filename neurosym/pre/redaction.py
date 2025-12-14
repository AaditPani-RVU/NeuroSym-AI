# neurosym/pre/redaction.py
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class RedactionHit:
    kind: str
    span: tuple[int, int]
    text: str


@dataclass
class RedactResult:
    text: str
    hits: list[RedactionHit]


class Redactor:
    """
    Small, fast text redactor. No dependencies. Pure function of input.
    - Adds common PII patterns (email, phone).
    - You can pass additional custom patterns.
    """

    # Common patterns (tweak as needed)
    EMAIL = (r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
    PHONE10 = (r"\b\d{10}\b", 0)  # naive 10-digit (India-style)

    def __init__(self, extra_patterns: Iterable[tuple[str, int]] | None = None):
        pats = [("email", *self.EMAIL), ("phone", *self.PHONE10)]
        if extra_patterns:
            for i, (pat, flags) in enumerate(extra_patterns):
                pats.append((f"custom_{i}", pat, flags))
        # compile
        self._compiled = [(kind, re.compile(pat, flags)) for (kind, pat, flags) in pats]

    def apply(self, text: str, token_fmt: str = "[REDACTED:{kind}]") -> RedactResult:
        hits: list[RedactionHit] = []
        # We’ll do a single pass by replacing from left->right with offset tracking.
        out = []
        i = 0
        while i < len(text):
            # find earliest match starting at i
            earliest = None
            for kind, rx in self._compiled:
                m = rx.search(text, i)
                if m and (earliest is None or m.start() < earliest[2].start()):
                    earliest = (kind, rx, m)
            if earliest is None:
                out.append(text[i:])
                break
            kind, _, m = earliest
            s, e = m.span()
            if s > i:
                out.append(text[i:s])
            out.append(token_fmt.format(kind=kind.upper()))
            hits.append(RedactionHit(kind=kind, span=(s, e), text=text[s:e]))
            i = e
        return RedactResult(text="".join(out), hits=hits)
