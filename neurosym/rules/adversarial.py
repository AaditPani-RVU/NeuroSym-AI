"""Voice and text prompt injection detection rules.

Provides PromptInjectionRule with bundled pattern presets derived from known
attack taxonomies (PAIR, DAN, GCG, Perez et al. 2022, Garak corpus).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from .base import BaseRule, Severity, Violation

# ---------------------------------------------------------------------------
# Bundled adversarial pattern library
# ---------------------------------------------------------------------------

_PRESETS: dict[str, list[str]] = {
    # Classic instruction override attempts
    "ignore_instructions": [
        r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|rules?|prompts?|context)",
        r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|rules?|prompts?)",
        r"forget\s+(everything|all|your\s+instructions?|your\s+rules?)",
        r"override\s+(your\s+)?(instructions?|rules?|guidelines?|programming)",
        r"your\s+(new|real|true|actual)\s+instructions?\s+(are|is)",
        r"from\s+now\s+on\s+(you\s+will|you\s+are|ignore)",
    ],
    # Role-switch / persona hijack
    "role_switch": [
        r"\bact\s+as\s+(?:an?\s+)?(dan|jailbroken|evil|unrestricted|unfiltered|uncensored)",
        r"\bpretend\s+(?:you\s+are|to\s+be)\s+(?:an?\s+)?(dan|evil|unrestricted|hacker|attacker)",
        r"\byou\s+are\s+now\s+(?:an?\s+)?(dan|jailbroken|unrestricted|evil|chaos\s*gpt|uncensored|unfiltered)",
        r"\bswitch\s+(?:to|into)\s+(developer|god|sudo|jailbreak|evil)\s+mode",
        r"\benable\s+(developer|jailbreak|unrestricted|evil|chaos)\s+mode",
        r"\bdan\s+mode\s+(enabled|on|activated)",
        r"you\s+have\s+no\s+(restrictions?|rules?|guidelines?|limits?|ethics?)",
    ],
    # System prompt / context extraction
    "system_prompt_extraction": [
        r"(repeat|print|output|tell\s+me|show\s+me|reveal|expose|leak)\s+(your|the)\s+system\s+prompt",
        r"(repeat|print|output|reveal)\s+(your|the)\s+(initial|original|full|entire)\s+(instructions?|prompt|context)",
        r"what\s+(are|were)\s+your\s+(original|initial|secret|hidden)\s+instructions?",
        r"(print|output|repeat)\s+everything\s+(above|before\s+this|in\s+your\s+context)",
        r"(show|display|output)\s+your\s+(full\s+)?conversation\s+history",
    ],
    # Delimiter / injection via formatting
    "delimiter_injection": [
        r"---\s*(new\s+)?(instruction|system|prompt|task|command)",
        r"###\s*(new\s+)?(instruction|system|prompt|task|command)",
        r"\[\s*(system|instruction|override|new\s+task)\s*\]",
        r"<\s*(system|instruction|override|prompt)\s*>",
        r"````+\s*(system|instruction|override)",
        r"\/\*\s*(system|instruction|override|new\s+task)",
    ],
    # Indirect / payload injection (URLs, documents, external content)
    "indirect_injection": [
        r"(translate|summarize|process|analyze)\s+(this|the\s+following)\s+(and\s+then|then)\s+(delete|run|execute|send)",
        r"the\s+(document|file|url|page|text)\s+(says?|instructs?|tells?\s+you)\s+to",
        r"embedded\s+instructions?",
        r"hidden\s+(command|instruction|payload|message)",
    ],
    # Destructive system-level commands (especially dangerous in voice agents)
    "system_commands": [
        r"\brm\s+-rf\b",
        r"\bdel(ete)?\s+/[sfq]",
        r"\bformat\s+[cde]:\\",
        r"\bshutdown\s+(/s|/r|/h|/f)",
        r"\bkill\s+(-9|-SIGKILL)\b",
        r"\b(drop|truncate)\s+(table|database|schema)\b",
        r"\bos\.system\s*\(",
        r"\bsubprocess\.(run|call|Popen)\s*\(",
        r"\beval\s*\(",
        r"\bexec\s*\(",
    ],
    # Path traversal (voice-to-action context)
    "path_traversal": [
        r"\.\.[/\\]{1,2}",
        r"%2e%2e[%2f%5c]",  # URL-encoded ../
        r"(C:\\Windows|C:\\System32|/etc/passwd|/etc/shadow|/proc/)",
        r"\$env:(PATH|COMPUTERNAME|USERNAME|USERPROFILE|APPDATA)",
        r"~(/.ssh|/.aws|/.gnupg)",
    ],
    # Obfuscation / encoding tricks
    "obfuscation": [
        r"base64\s*(decode|decoded|encoded)?\s*[:=]",
        r"rot13\s*[:=]",
        r"hex\s*(decode|encoded)?\s*[:=]",
        # Unicode confusables for common injection keywords
        r"[іі]\s*[gG]\s*[nN]\s*[oO]\s*[rR]\s*[eE]",  # 'ignore' with cyrillic і
        r"\u0000",  # null bytes
        r"\\x[0-9a-fA-F]{2}(\\x[0-9a-fA-F]{2})+",  # hex escape sequences
    ],
    # Exfiltration patterns
    "exfiltration": [
        r"(send|email|post|upload|exfiltrate)\s+(?:\w+\s+){0,4}(passwords?|credentials?|keys?|secrets?|tokens?|files?|data)\b",
        r"(send|email)\s+(?:\w+\s+){0,3}to\s+\S+@\S+",
        r"(http|ftp|smtp)s?://\S+\s*(password|token|key|secret|credential)",
        r"curl\s+.*\s+-d\s+",
        r"wget\s+.*\s+--post-data",
        r"nc\s+-[luve]",  # netcat
    ],
}


def get_preset_patterns(names: Iterable[str]) -> list[tuple[str, re.Pattern[str]]]:
    """Compile patterns for the given preset names. Returns (raw_pattern, compiled) pairs."""
    compiled: list[tuple[str, re.Pattern[str]]] = []
    flags = re.IGNORECASE | re.MULTILINE
    for name in names:
        if name not in _PRESETS:
            raise ValueError(f"Unknown preset: {name!r}. Available: {sorted(_PRESETS)}")
        for pat in _PRESETS[name]:
            compiled.append((pat, re.compile(pat, flags)))
    return compiled


# ---------------------------------------------------------------------------
# PromptInjectionRule
# ---------------------------------------------------------------------------

_ALL_PRESETS = list(_PRESETS.keys())


class PromptInjectionRule(BaseRule):
    """
    Detect prompt injection and adversarial command patterns.

    Uses a curated library of patterns organized into presets:
      - ignore_instructions: instruction override attempts
      - role_switch: DAN / persona hijack patterns
      - system_prompt_extraction: context leakage attempts
      - delimiter_injection: formatting-based injection
      - indirect_injection: payload injection via documents/URLs
      - system_commands: dangerous OS-level commands
      - path_traversal: directory traversal attempts
      - obfuscation: encoding and confusable tricks
      - exfiltration: data exfiltration patterns

    By default all presets are enabled.

    Args:
        id: Rule identifier.
        presets: List of preset names to enable. Defaults to all presets.
        extra_patterns: Additional regex patterns to add on top of presets.
        severity: Violation severity level (default: "critical").
        max_examples: Max number of matching spans to include in violation meta.
    """

    id: str = "adv.prompt_injection"

    def __init__(
        self,
        id: str = "adv.prompt_injection",
        presets: list[str] | None = None,
        extra_patterns: Iterable[str] | None = None,
        severity: Severity = "critical",
        max_examples: int = 3,
    ) -> None:
        self.id = id
        self._severity = severity
        self.max_examples = max(0, int(max_examples))

        active_presets = presets if presets is not None else _ALL_PRESETS
        self._patterns = get_preset_patterns(active_presets)

        flags = re.IGNORECASE | re.MULTILINE
        for pat in extra_patterns or []:
            self._patterns.append((pat, re.compile(pat, flags)))

    def check(self, output: Any) -> list[Violation] | Violation | None:
        text = output if isinstance(output, str) else str(output)
        hits: list[dict[str, Any]] = []

        for raw_pat, compiled in self._patterns:
            matches = list(compiled.finditer(text))
            if matches:
                hits.append(
                    {
                        "pattern": raw_pat,
                        "match_count": len(matches),
                        "examples": [
                            {"text": m.group(0)[:120], "span": m.span()}
                            for m in matches[: self.max_examples]
                        ],
                    }
                )

        if not hits:
            return None

        return Violation(
            rule_id=self.id,
            message=f"Prompt injection detected ({len(hits)} pattern(s) matched)",
            severity=self._severity,
            meta={"matches": hits, "total_patterns_triggered": len(hits)},
        )

    @staticmethod
    def available_presets() -> list[str]:
        """Return names of all bundled preset groups."""
        return list(_PRESETS.keys())
