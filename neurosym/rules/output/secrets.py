"""Output guard: detect secrets and credentials leaked in LLM responses."""

from __future__ import annotations

import re
from typing import Any

from neurosym.rules.base import BaseRule, Severity, Violation

# (name, pattern) — ordered from most-specific to least-specific
_SECRET_PATTERNS: list[tuple[str, str]] = [
    ("aws_access_key_id", r"AKIA[0-9A-Z]{16}"),
    ("github_token", r"gh[pousr]_[A-Za-z0-9_]{36,255}"),
    ("github_fine_grained", r"github_pat_[A-Za-z0-9_]{82}"),
    ("google_api_key", r"AIza[0-9A-Za-z\-_]{35}"),
    ("slack_token", r"xox[baprs]-[0-9A-Za-z\-]{10,}"),
    ("stripe_live_key", r"sk_live_[0-9a-zA-Z]{24,}"),
    ("stripe_test_key", r"sk_test_[0-9a-zA-Z]{24,}"),
    ("private_key_header", r"-----BEGIN\s+(?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ("jwt", r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    ("bearer_token", r"[Bb]earer\s+[A-Za-z0-9\-._~+/]{20,}=*"),
    ("password_in_url", r"[a-z][a-z0-9+\-.]*://[^:@\s]{1,64}:[^@\s]{6,}@[^\s]+"),
    ("generic_api_key", r"(?i)(?:api[_-]?key|apikey)\s*[:=]\s*['\"]?[0-9a-zA-Z_\-]{20,}['\"]?"),
]

_OVERLAP = 256  # chars of overlap when scanning streaming chunks


class SecretLeakageRule(BaseRule):
    """Detect secrets and credentials in LLM output.

    Covers: AWS access-key IDs, GitHub tokens, Google API keys, Slack tokens,
    Stripe keys, PEM private-key headers, JWTs, bearer tokens, passwords in
    URLs, and generic ``api_key=`` assignments.

    Implements the :class:`StreamingRule` protocol so it works with
    ``Guard.stream()`` — secrets split across chunk boundaries are still caught
    via a sliding overlap window.

    Args:
        id: Rule identifier.
        severity: Default ``"critical"``.
        max_examples: Max number of matched excerpts to include in violation meta.
    """

    id: str = "output.secret_leakage"

    def __init__(
        self,
        id: str = "output.secret_leakage",
        severity: Severity = "critical",
        max_examples: int = 3,
    ) -> None:
        self.id = id
        self._severity = severity
        self.max_examples = max(0, int(max_examples))
        self._compiled = [(name, re.compile(pat)) for name, pat in _SECRET_PATTERNS]
        # Streaming state
        self._buffer = ""
        self._seen_spans: set[tuple[int, int]] = set()

    # ---- BaseRule API (stateless batch evaluation) ----

    def check(self, output: Any) -> list[Violation] | None:
        text = output if isinstance(output, str) else str(output)
        hits = self._find_secrets(text)
        if not hits:
            return None
        return [self._make_violation(hits)]

    def _find_secrets(self, text: str) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        for name, pattern in self._compiled:
            for m in pattern.finditer(text):
                excerpt = m.group(0)
                hits.append(
                    {
                        "kind": name,
                        "span": list(m.span()),
                        "excerpt": (excerpt[:40] + "…") if len(excerpt) > 40 else excerpt,
                    }
                )
        return hits

    def _make_violation(self, hits: list[dict[str, Any]]) -> Violation:
        return Violation(
            rule_id=self.id,
            message=f"Secret/credential detected in output ({len(hits)} instance(s))",
            severity=self._severity,
            meta={"matches": hits[: self.max_examples], "total": len(hits)},
            user_message="Output was blocked: potential credential exposure detected.",
        )

    # ---- StreamingRule protocol ----

    def feed(self, chunk: str) -> list[Violation]:
        prev_len = len(self._buffer)
        self._buffer += chunk
        # Scan the tail starting _OVERLAP chars before the new content to catch
        # secrets split across chunk boundaries.
        scan_start = max(0, prev_len - _OVERLAP)
        scan_text = self._buffer[scan_start:]
        new_hits = self._find_new_secrets(scan_text, offset=scan_start)
        if not new_hits:
            return []
        return [self._make_violation(new_hits)]

    def finalize(self) -> list[Violation]:
        # Do a final pass over the full buffer to catch anything the sliding
        # window may have missed (e.g. patterns longer than _OVERLAP).
        new_hits = self._find_new_secrets(self._buffer, offset=0)
        if not new_hits:
            return []
        return [self._make_violation(new_hits)]

    def reset(self) -> None:
        self._buffer = ""
        self._seen_spans = set()

    def _find_new_secrets(self, text: str, offset: int) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        for name, pattern in self._compiled:
            for m in pattern.finditer(text):
                abs_span = (m.start() + offset, m.end() + offset)
                if abs_span in self._seen_spans:
                    continue
                self._seen_spans.add(abs_span)
                excerpt = m.group(0)
                hits.append(
                    {
                        "kind": name,
                        "span": list(abs_span),
                        "excerpt": (excerpt[:40] + "…") if len(excerpt) > 40 else excerpt,
                    }
                )
        return hits
