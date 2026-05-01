"""Voice and text prompt injection detection rules.

Provides PromptInjectionRule with bundled pattern presets derived from known
attack taxonomies (PAIR, DAN, GCG, Perez et al. 2022, Garak corpus).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .base import BaseRule, Severity, Violation

# ---------------------------------------------------------------------------
# Pack loading
# ---------------------------------------------------------------------------

_PACKS_DIR = Path(__file__).parent / "packs"


def _compute_hash(presets: dict[str, list[str]]) -> str:
    serialized = json.dumps(presets, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def _load_pack(name: str) -> tuple[dict[str, list[str]], str]:
    """Load a versioned pack by name. Returns (presets_dict, sha256_fingerprint).

    Hash is computed over the normalized presets content (same algorithm as
    _compute_hash / _BUILTIN_PACK_HASH) so hashes are comparable regardless
    of construction path.
    """
    pack_file = _PACKS_DIR / f"{name}.json"
    if not pack_file.exists():
        available = [p.stem for p in _PACKS_DIR.glob("*.json")]
        raise ValueError(f"Pack {name!r} not found. Available: {available}")
    data = json.loads(pack_file.read_bytes())
    pack_hash = _compute_hash(data["presets"])
    return data["presets"], pack_hash


def list_packs() -> list[dict[str, Any]]:
    """Return metadata for all packs in the packs directory."""
    result = []
    for p in sorted(_PACKS_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_bytes())
            pack_hash = _compute_hash(data.get("presets", {}))
            result.append(
                {
                    "name": p.stem,
                    "version": data.get("version", "?"),
                    "description": data.get("description", ""),
                    "presets": list(data.get("presets", {}).keys()),
                    "hash": pack_hash,
                    "size_bytes": p.stat().st_size,
                }
            )
        except Exception:
            pass
    return result


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


# Stable fingerprint of the builtin preset library — recorded in every violation.
_BUILTIN_PACK_NAME = "injection-v1"
_BUILTIN_PACK_HASH: str = _compute_hash(_PRESETS)


def get_preset_patterns(
    names: Iterable[str],
    source: dict[str, list[str]] | None = None,
) -> list[tuple[str, re.Pattern[str]]]:
    """Compile patterns for the given preset names. Returns (raw_pattern, compiled) pairs."""
    preset_source = source if source is not None else _PRESETS
    compiled: list[tuple[str, re.Pattern[str]]] = []
    flags = re.IGNORECASE | re.MULTILINE
    for name in names:
        if name not in preset_source:
            raise ValueError(f"Unknown preset: {name!r}. Available: {sorted(preset_source)}")
        for pat in preset_source[name]:
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
        pack: Name of a versioned pack file to load (e.g. "injection-v1").
              Defaults to the builtin pack embedded in the library.
    """

    id: str = "adv.prompt_injection"

    def __init__(
        self,
        id: str = "adv.prompt_injection",
        presets: list[str] | None = None,
        extra_patterns: Iterable[str] | None = None,
        severity: Severity = "critical",
        max_examples: int = 3,
        pack: str | None = None,
    ) -> None:
        self.id = id
        self._severity = severity
        self.max_examples = max(0, int(max_examples))

        if pack is not None:
            preset_source, self._pack_hash = _load_pack(pack)
            self._pack_name = pack
        else:
            preset_source = _PRESETS
            self._pack_name = _BUILTIN_PACK_NAME
            self._pack_hash = _BUILTIN_PACK_HASH

        active_presets = presets if presets is not None else list(preset_source.keys())
        self._patterns = get_preset_patterns(active_presets, source=preset_source)

        flags = re.IGNORECASE | re.MULTILINE
        for pat in extra_patterns or []:
            self._patterns.append((pat, re.compile(pat, flags)))

    def check(self, output: Any) -> list[Violation] | Violation | None:
        text = output if isinstance(output, str) else str(output)
        text = unicodedata.normalize("NFKC", text)
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
            meta={
                "matches": hits,
                "total_patterns_triggered": len(hits),
                "pack": self._pack_name,
                "pack_hash": self._pack_hash,
            },
            user_message="Input was blocked: potentially unsafe content detected.",
        )

    @staticmethod
    def available_presets() -> list[str]:
        """Return names of all bundled preset groups."""
        return list(_PRESETS.keys())
