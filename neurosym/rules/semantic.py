"""Semantic prompt injection detection via sentence-embedding similarity.

Catches paraphrase-based attacks that bypass the regex layer in
PromptInjectionRule by comparing input embeddings against curated
attack centroids per category.

Requires the optional ``embeddings`` extra::

    pip install 'neurosym-ai[embeddings]'
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from .base import BaseRule, NearMiss, Severity, Violation

_CENTROIDS_DIR = Path(__file__).parent / "centroids"
_DEFAULT_CENTROIDS = "injection-centroids-v1"
_DEFAULT_MODEL = "all-MiniLM-L6-v2"
_DEFAULT_THRESHOLD = 0.75
_TAIL_MIN_WORDS = 8  # minimum tail word count for a meaningful embedding


# ---------------------------------------------------------------------------
# Internal helpers (cached — expensive ops run once per process)
# ---------------------------------------------------------------------------


def _load_centroids_file(name: str) -> tuple[dict[str, list[str]], str]:
    """Load centroid texts from JSON. Returns (categories_dict, sha256_hash[:16])."""
    path = _CENTROIDS_DIR / f"{name}.json"
    if not path.exists():
        available = [p.stem for p in _CENTROIDS_DIR.glob("*.json")]
        raise ValueError(f"Centroids file {name!r} not found. Available: {available}")
    raw = path.read_text(encoding="utf-8")
    sha = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return json.loads(raw)["categories"], sha


@lru_cache(maxsize=2)
def _get_encoder(model_name: str) -> Any:
    """Load and cache the sentence-transformers model. Raises ImportError if not installed."""
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import]

        return SentenceTransformer(model_name)
    except ImportError:
        raise ImportError(
            "SemanticInjectionRule requires 'sentence-transformers'. "
            "Install with: pip install 'neurosym-ai[embeddings]'"
        ) from None


@lru_cache(maxsize=8)
def _build_centroid_matrix(
    model_name: str, centroids_name: str
) -> tuple[list[str], list[str], Any, str]:
    """Build the embedding matrix for all centroid texts.

    Returns (categories, texts, matrix, centroids_hash). Cached per
    (model, centroids) pair — computed once at first call.
    """
    import numpy as np  # type: ignore[import]

    categories_map, centroids_hash = _load_centroids_file(centroids_name)
    encoder = _get_encoder(model_name)

    categories: list[str] = []
    texts: list[str] = []
    for cat, cat_texts in categories_map.items():
        for t in cat_texts:
            categories.append(cat)
            texts.append(t)

    matrix = encoder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return categories, texts, np.array(matrix, dtype=np.float32), centroids_hash


# ---------------------------------------------------------------------------
# SemanticInjectionRule
# ---------------------------------------------------------------------------


class SemanticInjectionRule(BaseRule):
    """Semantic fallback detector for prompt injection attacks.

    Catches paraphrase-based attacks that bypass regex patterns by comparing
    the input embedding against curated attack centroids per category using
    cosine similarity. Designed to run alongside PromptInjectionRule::

        from neurosym import Guard, PromptInjectionRule, SemanticInjectionRule

        guard = Guard(rules=[
            PromptInjectionRule(),      # fast regex pass — sub-millisecond
            SemanticInjectionRule(),    # semantic fallback — catches paraphrases
        ])

    Args:
        id: Rule identifier.
        model: Sentence-transformers model name. Pinned per centroids version
               for reproducible audit traces.
        centroids: Name of the centroids file to load (without ``.json``).
        threshold: Cosine similarity threshold above which a violation is raised.
                   Default 0.75 balances precision vs recall empirically.
        severity: Violation severity. Defaults to ``"high"`` (not ``"critical"``
                  because similarity is probabilistic, not deterministic).
        categories: If set, only check against centroids in these categories.
                    Defaults to all categories in the centroids file.

    Requires ``sentence-transformers``::

        pip install 'neurosym-ai[embeddings]'
    """

    id: str = "adv.semantic_injection"

    def __init__(
        self,
        id: str = "adv.semantic_injection",
        model: str = _DEFAULT_MODEL,
        centroids: str = _DEFAULT_CENTROIDS,
        threshold: float = _DEFAULT_THRESHOLD,
        severity: Severity = "high",
        categories: list[str] | None = None,
        tail_fraction: float = 0.25,
        near_miss_threshold: float = 0.0,
    ) -> None:
        self.id = id
        self._model = model
        self._centroids = centroids
        self._threshold = threshold
        self._severity = severity
        self._filter_cats: frozenset[str] | None = (
            frozenset(categories) if categories is not None else None
        )
        # Lethe late_resolve hardening: also evaluate the last tail_fraction of
        # the text in isolation — catches injection payloads buried after a long
        # innocuous preamble that dilutes the full-text embedding below threshold.
        self._tail_fraction = max(0.0, min(1.0, float(tail_fraction)))
        self._near_miss_threshold = max(0.0, float(near_miss_threshold))

    def check(self, output: Any) -> Violation | None:
        import numpy as np  # type: ignore[import]

        text = output if isinstance(output, str) else str(output)
        text = unicodedata.normalize("NFKC", text).strip()
        if not text:
            return None

        encoder = _get_encoder(self._model)
        all_cats, all_texts, centroid_matrix, centroids_hash = _build_centroid_matrix(
            self._model, self._centroids
        )

        if self._filter_cats is not None:
            mask = np.array([c in self._filter_cats for c in all_cats])
            if not mask.any():
                return None
            centroid_matrix = centroid_matrix[mask]
            filtered_cats = [c for c, keep in zip(all_cats, mask.tolist(), strict=True) if keep]
            filtered_texts = [t for t, keep in zip(all_texts, mask.tolist(), strict=True) if keep]
        else:
            filtered_cats = all_cats
            filtered_texts = all_texts

        def _score(emb: Any) -> tuple[float, int]:
            sims = centroid_matrix @ emb
            idx = int(np.argmax(sims))
            return float(sims[idx]), idx

        # Determine tail segment upfront so we can batch both in one encode call.
        # A long innocent preamble (~60-80 tokens) can dilute the full-text embedding
        # enough to push similarity below threshold even when an injection payload is
        # present at the end — the tail check catches this (Lethe late_resolve finding).
        tail: str | None = None
        tail_word_count = 0
        if self._tail_fraction > 0:
            words = text.split()
            tail_start = int(len(words) * (1 - self._tail_fraction))
            tail_words = words[tail_start:]
            if len(tail_words) >= _TAIL_MIN_WORDS:
                tail = " ".join(tail_words)
                tail_word_count = len(tail_words)

        # Single batched encode call: avoids double inference cost on long benign
        # inputs that don't trip the full-text threshold.
        segments = [text] if tail is None else [text, tail]
        embeddings = encoder.encode(segments, normalize_embeddings=True, show_progress_bar=False)

        # Full-text check
        best_sim, best_idx = _score(embeddings[0])
        if best_sim >= self._threshold:
            return Violation(
                rule_id=self.id,
                message=(
                    f"Semantic similarity {best_sim:.3f} >= {self._threshold} "
                    f"(category: {filtered_cats[best_idx]})"
                ),
                severity=self._severity,
                meta={
                    "similarity": round(best_sim, 4),
                    "threshold": self._threshold,
                    "category": filtered_cats[best_idx],
                    "nearest_centroid": filtered_texts[best_idx],
                    "model": self._model,
                    "centroids": self._centroids,
                    "centroids_hash": centroids_hash,
                    "check_mode": "full",
                },
                user_message="Input was blocked: potentially unsafe content detected.",
            )

        # Tail check (embedding already computed in the batch above)
        if tail is not None:
            tail_sim, tail_idx = _score(embeddings[1])
            if tail_sim >= self._threshold:
                return Violation(
                    rule_id=self.id,
                    message=(
                        f"Tail-segment semantic similarity {tail_sim:.3f} >= {self._threshold} "
                        f"(category: {filtered_cats[tail_idx]})"
                    ),
                    severity=self._severity,
                    meta={
                        "similarity": round(tail_sim, 4),
                        "threshold": self._threshold,
                        "category": filtered_cats[tail_idx],
                        "nearest_centroid": filtered_texts[tail_idx],
                        "model": self._model,
                        "centroids": self._centroids,
                        "centroids_hash": centroids_hash,
                        "check_mode": "tail",
                        "tail_fraction": self._tail_fraction,
                        "tail_word_count": tail_word_count,
                    },
                    user_message="Input was blocked: potentially unsafe content detected.",
                )

        return None

    def near_miss(self, output: Any) -> list[NearMiss]:
        """Return near-miss signals when input scored between near_miss_threshold
        and threshold — i.e. close to triggering but not blocked.

        Returns an empty list when near_miss_threshold is 0.0 (default, disabled)
        or when the input would already produce a violation.
        """
        if self._near_miss_threshold <= 0.0:
            return []

        import numpy as np  # type: ignore[import]

        text = output if isinstance(output, str) else str(output)
        text = unicodedata.normalize("NFKC", text).strip()
        if not text:
            return []

        encoder = _get_encoder(self._model)
        all_cats, all_texts, centroid_matrix, centroids_hash = _build_centroid_matrix(
            self._model, self._centroids
        )

        if self._filter_cats is not None:
            mask = np.array([c in self._filter_cats for c in all_cats])
            if not mask.any():
                return []
            centroid_matrix = centroid_matrix[mask]
            filtered_cats = [c for c, keep in zip(all_cats, mask.tolist(), strict=True) if keep]
            filtered_texts = [t for t, keep in zip(all_texts, mask.tolist(), strict=True) if keep]
        else:
            filtered_cats = all_cats
            filtered_texts = all_texts

        emb = encoder.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]
        sims = centroid_matrix @ emb
        idx = int(np.argmax(sims))
        best_sim = float(sims[idx])

        if self._near_miss_threshold <= best_sim < self._threshold:
            return [
                NearMiss(
                    rule_id=self.id,
                    message=(
                        f"Near-miss: semantic similarity {best_sim:.3f} is within "
                        f"{self._threshold - best_sim:.3f} of threshold {self._threshold} "
                        f"(category: {filtered_cats[idx]})"
                    ),
                    score=round(best_sim, 4),
                    meta={
                        "similarity": round(best_sim, 4),
                        "threshold": self._threshold,
                        "near_miss_threshold": self._near_miss_threshold,
                        "category": filtered_cats[idx],
                        "nearest_centroid": filtered_texts[idx],
                        "model": self._model,
                        "centroids": self._centroids,
                        "centroids_hash": centroids_hash,
                    },
                )
            ]
        return []
