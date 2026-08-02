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

import logging
import re

logger = logging.getLogger(__name__)

DEFAULT_BAR = 0.76  # semantic-cosine bar (P-SP threshold); only meaningful for the embedding metric
TOKEN_BAR = 0.50  # token-overlap (Dice) bar; faithful paraphrases reword heavily and score lower
BERTSCORE_BAR = 0.88  # BERTScore-F1 bar (rescaled-with-baseline); faithful paraphrases land ~0.88-0.92
# Unicode-aware: the ASCII-only [A-Za-z0-9']+ tokenised every non-Latin script to nothing, and
# token_overlap then scored two unrelated Russian, Greek or Chinese texts as a perfect 1.0.
_WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)*", re.UNICODE)

_UNSET = object()
_model = _UNSET  # _UNSET = not yet probed; None = probed and unavailable; else the model
_bs_model = _UNSET  # BERTScore scorer cache (same _UNSET/None/model convention)


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
    except (ImportError, OSError):
        _model = None
    return _model


def _bs_scorer():
    """Lazily load the BERTScore scorer, or return None if unavailable (cached like _st_model)."""
    global _bs_model
    if _bs_model is not _UNSET:
        return _bs_model
    try:
        from bert_score import BERTScorer

        # rescale_with_baseline maps raw F1 onto a calibrated [0,1] scale where 0.88 is a
        # meaningful faithful-paraphrase bar (raw F1 would sit ~0.93+ and need a different bar).
        _bs_model = BERTScorer(lang="en", rescale_with_baseline=True)
    except Exception:
        _bs_model = None
    return _bs_model


def _bert_score_similarity(a: str, b: str) -> float | None:
    """BERTScore F1 of rewrite ``b`` against reference ``a``, or None if unavailable.

    BERTScore *recall* catches propositional drift in the prose (dropped claims, altered causal
    structure) that a single sentence-embedding cosine can average away — the genuine upgrade over
    the MiniLM path. Facts/numbers/citations are already covered by the sentinel lock.
    """
    scorer = _bs_scorer()
    if scorer is None:
        return None
    try:
        _p, _r, f1 = scorer.score([b], [a])  # ([candidate], [reference])
        return float(f1.mean())
    except Exception:
        return None


def _tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def _char_bigrams(text: str):
    """Whitespace-stripped character bigrams — the granularity of last resort."""
    from collections import Counter

    s = "".join(text.split()).lower()
    if len(s) < 2:
        return Counter(s)
    return Counter(s[i:i + 2] for i in range(len(s) - 1))


def token_overlap(a: str, b: str) -> float:
    """Dice coefficient over token multisets — the lite fallback. In [0, 1]."""
    from collections import Counter

    ca, cb = Counter(_tokens(a)), Counter(_tokens(b))
    # Under two word tokens on either side leaves word-level Dice nothing to work with:
    # punctuation- or formula-only text, and scriptio-continua scripts (Chinese, Japanese, Thai)
    # where a whole clause is a single token. Drop to character bigrams instead of comparing two
    # empty multisets, which used to return 1.0 — a perfect meaning-preservation score for texts
    # with nothing whatsoever in common. This is the gate's only similarity metric when
    # sentence-transformers is absent, so it decided whether such a rewrite was admissible.
    if sum(ca.values()) < 2 or sum(cb.values()) < 2:
        ca, cb = _char_bigrams(a), _char_bigrams(b)
    if not ca and not cb:
        return 1.0 if a.strip() == b.strip() else 0.0
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
        # Raw cosine: the 0.76 bar (P-SP threshold) is defined on this scale, so do NOT rescale.
        return float(np.dot(emb[0], emb[1]))
    except Exception:
        return None


def similarity(a: str, b: str) -> float:
    """Semantic similarity in [0, 1]. Cosine of embeddings if available, else token overlap."""
    # Empty-input guard (both metrics agree): two empties are identical; empty-vs-nonempty is 0.
    # Without this the embedding path returns a spurious non-zero cosine for "" vs "something".
    a_empty, b_empty = not a.strip(), not b.strip()
    if a_empty or b_empty:
        return 1.0 if (a_empty and b_empty) else 0.0
    bs = _bert_score_similarity(a, b)
    if bs is not None:
        # BERTScore F1 (rescaled) — the highest-fidelity backend when bert-score is installed.
        return max(0.0, min(1.0, bs))
    cos = _cosine_similarity(a, b)
    if cos is not None:
        # Clamp raw cosine into [0, 1]; the 0.76 bar lives on this raw-cosine scale.
        return max(0.0, min(1.0, cos))
    return token_overlap(a, b)


def method() -> str:
    """Report which backend `similarity` will use: 'bertscore', 'embedding', or 'token_overlap'."""
    if _bs_scorer() is not None:
        return "bertscore"
    return "embedding" if _st_model() is not None else "token_overlap"


def confidence() -> str:
    """How trustworthy the gate is: 'high' for a semantic metric, 'low' for the lite fallback.

    Token-overlap cannot tell a faithful paraphrase from an off-topic rewrite, so on the lite
    tier the quality gate is advisory, not authoritative.

    This used to read ``method() == "embedding"``, which INVERTED the ranking once the bertscore
    tier was added: bertscore is the highest-fidelity backend (see ``_bert_score_similarity``), yet
    it compared unequal to "embedding" and was reported as "low" — while the middle tier, MiniLM
    embeddings, was reported as "high". Any caller gating on ``confidence() == "high"`` would
    distrust the best metric available and trust a weaker one. Both semantic metrics are
    authoritative; only the token-overlap fallback is not.
    """
    return "low" if method() == "token_overlap" else "high"


def recommended_bar() -> float:
    """The bar appropriate to the active metric (each metric lives on a different scale)."""
    m = method()
    if m == "bertscore":
        return BERTSCORE_BAR
    return DEFAULT_BAR if m == "embedding" else TOKEN_BAR


def passes(a: str, b: str, bar: float | None = None) -> bool:
    """True when the rewrite ``b`` preserves enough of ``a``'s meaning.

    ``bar=None`` selects the metric-appropriate bar (``recommended_bar``); pass an explicit
    value to override.
    """
    if bar is None:
        bar = recommended_bar()
    return similarity(a, b) >= bar


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m untell.scripts.quality "<orig>" "<rewrite>"`` -> JSON."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    import json
    import sys

    args = argv if argv is not None else sys.argv[1:]
    # -h/--help is a universal expectation, and every other script in this package honours it. This
    # one treated it as text, so `quality.py --help` printed a usage line as an ERROR and exited 2 —
    # a user checking how to call the meaning gate got what looked like a failure.
    if any(a in ("-h", "--help") for a in args):
        print(
            'usage: quality.py "<original>" "<rewrite>"\n\n'
            "Prints JSON: similarity, method (bertscore|embedding|token_overlap), confidence, bar,\n"
            "and whether the pair passes the bar for the ACTIVE metric (each lives on its own scale).",
        )
        return 0
    if len(args) < 2:
        logger.error('usage: quality.py "<original>" "<rewrite>"')
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
