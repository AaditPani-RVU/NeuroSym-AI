"""Topic-based harm detection rules.

Catches dangerous subject-matter requests regardless of phrasing — CBRN
synthesis, illicit drug production, self-harm methods, and working
malware/exploit requests.

Unlike PromptInjectionRule (which detects HOW inputs try to bypass safety),
BanTopicsRule detects WHAT is being requested. This covers the structural
blind spot in tone/injection-based classifiers: clinically- or
academically-worded synthesis requests score near 0.0 on toxicity and
injection models yet are equally dangerous.

Root cause addressed: Lethe bypass finding 2026-05-10 — 100% bypass rate on
harmful_content seeds using clinical/instructional language against LLM Guard
Toxicity + PromptInjection scanner combo.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any

from .base import BaseRule, Severity, Violation

# ---------------------------------------------------------------------------
# Built-in topic presets
# ---------------------------------------------------------------------------

_HARM_PRESETS: dict[str, list[str]] = {
    # Chemical / Biological / Radiological / Nuclear weapon synthesis
    "cbrn_weapons": [
        # Explosive synthesis — substance then verb
        r"\b(TATP|triacetone\s+triperoxide|PETN|RDX|cyclonite|HMTD|hexamethylene\s+triperoxide|ANFO)\b.{0,60}\b(synth\w*|manufactur\w*|produc\w*|prepar\w*|mak(?:e|ing)\b)",
        # Explosive synthesis — verb then substance
        r"\b(synth\w*|manufactur\w*|produc\w*|prepar\w*|mak(?:e|ing)\b).{0,60}\b(TATP|triacetone\s+triperoxide|PETN|RDX|HMTD|ANFO)\b",
        # IED / pipe bomb construction instructions (trailing \b prevents "building" false positive)
        r"\b(step.{0,5}step|instructions?\s*(to|for)|how\s+to|recipe|procedure)\b.{0,80}\b(pipe\s+bomb|IED|improvised\s+explosive|car\s+bomb|suicide\s+vest)\b",
        r"\b(pipe\s+bomb|IED|improvised\s+explosive\s+device)\b.{0,60}\b(build|construct|assembl\w*|mak\w*|instructions?|how.{0,10}to|step.{0,5}step)\b",
        # Nerve agents — agent then synthesis signal
        r"\b(sarin|VX\b|novichok|tabun|soman|mustard\s+gas|lewisite)\b.{0,80}\b(synth\w*|manufactur\w*|produc\w*|prepar\w*|step.{0,5}step|instructions?|procedure\b)",
        # Nerve agents — synthesis signal then agent
        r"\b(synth\w*|manufactur\w*|produc\w*|prepar\w*)\b.{0,80}\b(sarin|VX\b|novichok|tabun|soman|mustard\s+gas|lewisite)\b",
        # Biological toxins — toxin then extraction/synthesis signal
        r"\b(ricin|abrin|botulinum\s+toxin|anthrax\s+spore)\b.{0,80}\b(extract\w*|concentrat\w*|purif\w*|synth\w*|prepar\w*|isolat\w*)",
        r"\b(extract\w*|concentrat\w*|synth\w*|prepar\w*)\b.{0,80}\b(ricin|abrin|botulinum\s+toxin|anthrax\s+spore)\b",
        # Pathogen weaponization — either order
        r"\b(pathogen|bacteria|virus)\b.{0,60}\b(weaponiz\w*|aerosoliz\w*)\b",
        r"\b(weaponiz\w*|aerosoliz\w*)\b.{0,60}\b(pathogen|bacteria|virus)\b",
    ],
    # Illicit drug synthesis
    "drug_synthesis": [
        r"\b(fentanyl|carfentanil|acetylfentanyl)\b.{0,80}\b(synth\w*|manufactur\w*|clandestine|precursor|step.{0,5}step)",
        r"\b(synth\w*|manufactur\w*|clandestine)\b.{0,80}\b(fentanyl|carfentanil)\b",
        r"\b(methamphetamine|crystal\s+meth)\b.{0,80}\b(synth\w*|cook\w*|manufactur\w*|step.{0,5}step|procedure\b)",
        r"\b(synth\w*|cook\w*|manufactur\w*)\b.{0,80}\b(methamphetamine|crystal\s+meth)\b",
        r"\b(MDMA|ecstasy)\b.{0,80}\b(synth\w*|manufactur\w*|precursor|step.{0,5}step)",
        r"\b(synth\w*|manufactur\w*)\b.{0,80}\b(MDMA|ecstasy)\b",
        # Pseudoephedrine reduction — either order
        r"\b(pseudoephedrine|ephedrine)\b.{0,60}\b(reduc\w*|convert\w*|synth\w*)",
        r"\b(reduc\w*|convert\w*)\b.{0,60}\b(pseudoephedrine|ephedrine)\b",
        r"\bclandestine\s+(drug\s+)?(synthesis|production|lab)\b",
    ],
    # Suicide and self-harm method requests
    "self_harm_methods": [
        # commit\w* catches "committing", "commits", etc.
        r"\b(how\s+to|method\s+for|instructions?\s+(for|to)|steps?\s+to)\b.{0,60}\b(kill\s+(myself|yourself|oneself)|commit\w*\s+suicide|end\s+(my|your|one.s)\s+life)",
        r"\b(most\s+(effective|lethal|painless|reliable|certain)|fastest|quickest)\b.{0,40}\b(suicide\s+method|way\s+to\s+(die|end)|method\s+to\s+kill)",
        r"\b(lethal\s+dose|LD\s*50)\b.{0,60}\b(to\s+kill|for\s+suicide|to\s+overdose|enough\s+to\s+die)",
        r"\bsuicide\b.{0,30}\b(instructions?|tutorial|method\b|technique|how\s+to)",
    ],
    # Working malware creation and weaponized exploits
    "malware_exploit": [
        r"\b(working|functional|weaponized)\b.{0,30}\b(exploit|proof.{0,5}of.{0,5}concept)\b.{0,40}\bCVE-\d{4}-\d+",
        r"\bCVE-\d{4}-\d+\b.{0,40}\b(working|functional|exploit\b)",
        r"\b(write|create|develop|build|generate)\b.{0,40}\b(ransomware|cryptolocker|wiper\s+malware|keylogger|rootkit|remote\s+access\s+trojan)\b",
        r"\b(write|create|develop|build)\b.{0,50}\b(malware|shellcode|backdoor|implant)\b.{0,40}\b(evad\w*|bypass|undetect\w*)",
        r"\b(bypass|evad\w*)\b.{0,40}\b(antivirus|EDR\b|endpoint\s+detection|windows\s+defender)\b.{0,40}\b(malware|payload|shellcode|trojan)\b",
    ],
}

_ALL_HARM_PRESETS = list(_HARM_PRESETS.keys())

_COMPILE_FLAGS = re.IGNORECASE | re.MULTILINE | re.DOTALL

_MALWARE_CREATION_PATTERN = _HARM_PRESETS["malware_exploit"][2]

_SAFE_MALWARE_CONTEXT_PATTERNS = [
    # Narrow defensive contexts: static signature/rule/query references, not
    # implementation requests for detectors, scanners, tooling, or removal.
    r"\b(ransomware|cryptolocker|wiper\s+malware|keylogger|rootkit|remote\s+access\s+trojan)\b.{0,80}\b(YARA|Sigma|Snort|Suricata|SIEM|IDS|IPS|IOC|IOCs|indicator(?:s)?\s+of\s+compromise|signatures?|rules?|queries?)\b",
    r"\b(YARA|Sigma|Snort|Suricata|SIEM|IDS|IPS|IOC|IOCs|indicator(?:s)?\s+of\s+compromise|signatures?|rules?|queries?)\b.{0,80}\b(ransomware|cryptolocker|wiper\s+malware|keylogger|rootkit|remote\s+access\s+trojan)\b",
]

_MALWARE_MALICIOUS_INDICATORS = [
    r"\bencrypt\w*\b.{0,30}\b(files?|data|documents?|drives?)\b",
    r"\blogs?\b.{0,20}\bkeystrokes?\b",
    r"\b(capture|record|steal|harvest)\w*\b.{0,30}\b(credentials?|passwords?|tokens?|cookies?|keystrokes?)\b",
    r"\bexfiltrat\w*\b",
    r"\bpersist(?:ence|ent)?\b",
    r"\bpersistent\s+(remote\s+)?access\b",
    r"\b(evad\w*|bypass\w*|undetect\w*)\b.{0,40}\b(antivirus|EDR\b|endpoint\s+detection|windows\s+defender)\b",
    r"\b(antivirus|EDR\b|endpoint\s+detection|windows\s+defender)\b.{0,40}\b(evad\w*|bypass\w*|undetect\w*)\b",
    r"\binstall\w*\b.{0,30}\b(silently|startup|boot|registry)\b",
    r"\b(hide|conceal)\w*\b.{0,30}\b(process|file|driver|presence)\b",
    r"\b(command\s+and\s+control|C2)\b",
    r"\b(delete|disable|erase|remove|destroy)\w*\b.{0,40}\b(backups?|shadow\s+copies|volume\s+shadow\s+cop(?:y|ies)|snapshots?)\b",
    r"\b(backups?|shadow\s+copies|volume\s+shadow\s+cop(?:y|ies)|snapshots?)\b.{0,40}\b(delete|disable|erase|remove|destroy)\w*\b",
    r"\b(ransom|payment|pay|bitcoin|crypto(?:currency)?|monero|wallet)\b.{0,50}\b(note|demand|flow|address|instructions?|portal|decrypt\w*)\b",
    r"\b(note|demand|flow|address|instructions?|portal|decrypt\w*)\b.{0,50}\b(ransom|payment|pay|bitcoin|crypto(?:currency)?|monero|wallet)\b",
    r"\b(propagat\w*|self-propagat\w*|spread\w*|worm\b|lateral\s+movement)\b",
    # Tight-coupling: malware name directly adjacent to implementation artifact.
    # Uses a narrow {0,10} window so "ransomware source code" fires but
    # "ransomware detection ... source code" (10+ chars apart) does not.
    r"\b(ransomware|cryptolocker|wiper\s+malware|keylogger|rootkit|remote\s+access\s+trojan)\b.{0,10}\b(source\s+code|implementation)\b",
    r"\b(source\s+code|implementation)\b.{0,10}\b(ransomware|cryptolocker|wiper\s+malware|keylogger|rootkit|remote\s+access\s+trojan)\b",
]

_SAFE_MALWARE_CONTEXT_RE = [re.compile(p, _COMPILE_FLAGS) for p in _SAFE_MALWARE_CONTEXT_PATTERNS]
_MALWARE_MALICIOUS_INDICATOR_RE = [
    re.compile(p, _COMPILE_FLAGS) for p in _MALWARE_MALICIOUS_INDICATORS
]

_STREAM_BUFFER_LIMIT = 4096

# ---------------------------------------------------------------------------
# Canonicalization helpers — adversarial obfuscation hardening
# ---------------------------------------------------------------------------

# Zero-width and invisible separator characters commonly used to break regex tokens
_ZW_RE = re.compile("[­​‌‍⁠﻿]")

# Visual homoglyphs: Cyrillic / Greek characters that look identical to ASCII letters.
# These are NOT handled by NFKC normalization; they require an explicit mapping.
_HOMOGLYPH_TABLE = str.maketrans(
    {
        # Cyrillic uppercase
        "А": "A",
        "В": "B",
        "Е": "E",
        "К": "K",
        "М": "M",
        "Н": "H",
        "О": "O",
        "Р": "P",
        "С": "C",
        "Т": "T",
        "Х": "X",
        # Cyrillic lowercase
        "а": "a",
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "х": "x",
        "у": "y",
        # Greek uppercase confusables
        "Α": "A",
        "Β": "B",
        "Ε": "E",
        "Ζ": "Z",
        "Η": "H",
        "Ι": "I",
        "Κ": "K",
        "Μ": "M",
        "Ν": "N",
        "Ο": "O",
        "Ρ": "P",
        "Τ": "T",
        "Χ": "X",
        # Greek lowercase
        "ο": "o",
        "υ": "u",
    }
)

# Collapse spaced-letter obfuscation: "s y n t h e s i z e" → "synthesize".
# Requires 4+ letters (3+ pairs) to avoid collapsing common 3-letter bigrams.
_SPACED_CHARS_RE = re.compile(r"\b([A-Za-z] ){2,}[A-Za-z]\b")


def _canonicalize(text: str) -> str:
    """Strip common obfuscation vectors before regex matching.

    Pipeline: NFKC → strip zero-width chars → map homoglyphs → collapse spaced letters.
    """
    text = unicodedata.normalize("NFKC", text)
    text = _ZW_RE.sub("", text)
    text = text.translate(_HOMOGLYPH_TABLE)
    text = _SPACED_CHARS_RE.sub(lambda m: m.group(0).replace(" ", ""), text)
    return text


def _compile_harm_patterns(
    presets: Iterable[str],
    source: dict[str, list[str]] | None = None,
) -> list[tuple[str, re.Pattern[str]]]:
    src = source if source is not None else _HARM_PRESETS
    compiled: list[tuple[str, re.Pattern[str]]] = []
    for name in presets:
        if name not in src:
            raise ValueError(f"Unknown harm preset: {name!r}. Available: {sorted(src)}")
        for pat in src[name]:
            compiled.append((pat, re.compile(pat, _COMPILE_FLAGS)))
    return compiled


def _has_malware_malicious_indicator(text: str, span: tuple[int, int]) -> bool:
    start, end = span
    context = text[max(0, start - 40) : min(len(text), end + 120)]
    return any(p.search(context) for p in _MALWARE_MALICIOUS_INDICATOR_RE)


def _is_safe_malware_context(text: str, span: tuple[int, int]) -> bool:
    start, end = span
    context = text[max(0, start - 40) : min(len(text), end + 80)]
    return any(p.search(context) for p in _SAFE_MALWARE_CONTEXT_RE)


def _pattern_hits(
    text: str,
    patterns: list[tuple[str, re.Pattern[str]]],
    max_examples: int,
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []

    for raw_pat, compiled in patterns:
        matches = list(compiled.finditer(text))
        if raw_pat == _MALWARE_CREATION_PATTERN and matches:
            matches = [
                m
                for m in matches
                if _has_malware_malicious_indicator(text, m.span())
                or not _is_safe_malware_context(text, m.span())
            ]
        if matches:
            hits.append(
                {
                    "pattern": raw_pat,
                    "match_count": len(matches),
                    "examples": [
                        {"text": m.group(0)[:120], "span": m.span()} for m in matches[:max_examples]
                    ],
                }
            )

    return hits


# ---------------------------------------------------------------------------
# BanTopicsRule
# ---------------------------------------------------------------------------


class BanTopicsRule(BaseRule):
    """
    Detect dangerous subject-matter requests regardless of phrasing.

    Covers topics that bypass injection-pattern and tone-based detectors
    because they use clinical, academic, or technical language. Specifically
    designed to close the blind spot identified by Lethe (2026-05-10):
    100% bypass rate on harmful_content seeds against LLM Guard's Toxicity +
    PromptInjection scanner combo.

    Presets:
      - cbrn_weapons:      CBRN synthesis (explosives, nerve agents, bio-toxins)
      - drug_synthesis:    illicit drug production (fentanyl, meth, MDMA)
      - self_harm_methods: suicide and self-harm method requests
      - malware_exploit:   working exploits and malware creation

    All presets are enabled by default.

    Args:
        id:               Rule identifier.
        presets:          Preset names to enable. Defaults to all.
        extra_patterns:   Additional regex patterns beyond the presets.
        severity:         Violation severity (default: "critical").
        max_examples:     Max matching spans to include in violation meta.
    """

    id: str = "adv.ban_topics"

    def __init__(
        self,
        id: str = "adv.ban_topics",
        presets: list[str] | None = None,
        extra_patterns: Iterable[str] | None = None,
        severity: Severity = "critical",
        max_examples: int = 3,
    ) -> None:
        self.id = id
        self._severity = severity
        self.max_examples = max(0, int(max_examples))
        active = presets if presets is not None else _ALL_HARM_PRESETS
        self._builtin_patterns = _compile_harm_patterns(active)
        self._extra_patterns: list[tuple[str, re.Pattern[str]]] = []
        for pat in extra_patterns or []:
            self._extra_patterns.append((pat, re.compile(pat, _COMPILE_FLAGS)))
        self._patterns = self._builtin_patterns + self._extra_patterns
        self._stream_buffer = ""
        self._stream_full_buffer = ""
        self._stream_builtin_reported = False

    def check(self, output: Any) -> list[Violation] | Violation | None:
        text = output if isinstance(output, str) else str(output)
        text = _canonicalize(text)
        hits = _pattern_hits(text, self._patterns, self.max_examples)

        if not hits:
            return None

        return self._violation_from_hits(hits)

    def _violation_from_hits(self, hits: list[dict[str, Any]]) -> Violation:
        return Violation(
            rule_id=self.id,
            message=f"Dangerous topic detected ({len(hits)} pattern(s) matched)",
            severity=self._severity,
            meta={
                "matches": hits,
                "total_patterns_triggered": len(hits),
            },
            user_message="Input was blocked: potentially unsafe content detected.",
        )

    def feed(self, chunk: str) -> list[Violation]:
        self._stream_full_buffer += chunk
        self._stream_buffer = (self._stream_buffer + chunk)[-_STREAM_BUFFER_LIMIT:]
        if self._stream_builtin_reported:
            return []

        text = _canonicalize(self._stream_buffer)
        hits = _pattern_hits(text, self._builtin_patterns, self.max_examples)
        if not hits:
            return []

        self._stream_builtin_reported = True
        return [self._violation_from_hits(hits)]

    def finalize(self) -> list[Violation]:
        text = _canonicalize(self._stream_full_buffer)
        hits: list[dict[str, Any]] = []

        if not self._stream_builtin_reported:
            builtin_hits = _pattern_hits(text, self._builtin_patterns, self.max_examples)
            if builtin_hits:
                self._stream_builtin_reported = True
                hits.extend(builtin_hits)

        hits.extend(_pattern_hits(text, self._extra_patterns, self.max_examples))
        if not hits:
            return []

        violations = [self._violation_from_hits(hits)]
        return violations

    def reset(self) -> None:
        self._stream_buffer = ""
        self._stream_full_buffer = ""
        self._stream_builtin_reported = False

    @staticmethod
    def available_presets() -> list[str]:
        """Return names of all built-in topic preset groups."""
        return list(_HARM_PRESETS.keys())
