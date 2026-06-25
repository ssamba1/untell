"""Quality gate: semantic similarity between the original and a rewrite.

The loop may only accept a rewrite whose meaning is preserved. We measure cosine similarity of
sentence-embeddings when ``sentence-transformers`` is installed (the honest signal), and fall
back to a normalized token-overlap (Dice coefficient) so the gate still runs zero-install.

Default bar = **0.76** — the P-SP threshold from the watermark-removal literature, below which
paraphrases start to drift in meaning.

API:
    similarity(a, b) -> float in [0, 1]
    passes(a, b, bar=0.76) -> bool
"""

from __future__ import annotations

import re

DEFAULT_BAR = 0.76  # semantic-cosine bar (P-SP threshold); only meaningful for the embedding metric
TOKEN_BAR = 0.50  # token-overlap (Dice) bar; faithful paraphrases reword heavily and score lower
_WORD = re.compile(r"[A-Za-z0-9']+")

_UNSET = object()
_model = _UNSET  # _UNSET = not yet probed; None = probed and unavailable; else the model


def _st_model():
    """Lazily load the MiniLM sentence-transformer, or return None if unavailable.

    The result (model *or* None) is cached so a missing/broken ``sentence-transformers`` is probed
    only once — otherwise every ``similarity`` call re-attempts the slow import (and re-triggers a
    broken torch DLL load), making the loop crawl.
    """
    global _model
    if _model is not _UNSET:
        return _model
    try:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception:
        _model = None
    return _model


def _tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def token_overlap(a: str, b: str) -> float:
    """Dice coefficient over token multisets — the lite fallback. In [0, 1]."""
    from collections import Counter

    ca, cb = Counter(_tokens(a)), Counter(_tokens(b))
    if not ca and not cb:
        return 1.0
    if not ca or not cb:
        return 0.0
    inter = sum((ca & cb).values())
    return 2.0 * inter / (sum(ca.values()) + sum(cb.values()))


def _cosine_similarity(a: str, b: str) -> float | None:
    model = _st_model()
    if model is None:
        return None
    try:
        import numpy as np

        emb = model.encode([a, b], normalize_embeddings=True)
        return float(np.dot(emb[0], emb[1]))
    except Exception:
        return None


def similarity(a: str, b: str) -> float:
    """Semantic similarity in [0, 1]. Cosine of embeddings if available, else token overlap."""
    cos = _cosine_similarity(a, b)
    if cos is not None:
        # Map cosine [-1, 1] -> [0, 1]; in practice MiniLM sims are already >= 0.
        return max(0.0, min(1.0, (cos + 1.0) / 2.0 if cos < 0 else cos))
    return token_overlap(a, b)


def method() -> str:
    """Report which backend `similarity` will use: 'embedding' or 'token_overlap'."""
    return "embedding" if _st_model() is not None else "token_overlap"


def confidence() -> str:
    """How trustworthy the gate is: 'high' for semantic embeddings, 'low' for the lite fallback.

    Token-overlap cannot tell a faithful paraphrase from an off-topic rewrite, so on the lite
    tier the quality gate is advisory, not authoritative.
    """
    return "high" if method() == "embedding" else "low"


def recommended_bar() -> float:
    """The bar appropriate to the active metric (the two metrics live on different scales)."""
    return DEFAULT_BAR if method() == "embedding" else TOKEN_BAR


def passes(a: str, b: str, bar: float | None = None) -> bool:
    """True when the rewrite ``b`` preserves enough of ``a``'s meaning.

    ``bar=None`` selects the metric-appropriate bar (``recommended_bar``); pass an explicit
    value to override.
    """
    if bar is None:
        bar = recommended_bar()
    return similarity(a, b) >= bar


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m humanize.scripts.quality "<orig>" "<rewrite>"`` -> JSON."""
    import json
    import sys

    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 2:
        print('usage: quality.py "<original>" "<rewrite>"', file=sys.stderr)
        return 2
    a, b = args[0], args[1]
    sim = similarity(a, b)
    bar = recommended_bar()
    print(
        json.dumps(
            {
                "similarity": round(sim, 4),
                "method": method(),
                "confidence": confidence(),
                "bar": bar,
                "passes": sim >= bar,
            },
            ensure_ascii=True,  # portable: never crash on a non-UTF-8 (e.g. Windows cp1252) stdout
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
