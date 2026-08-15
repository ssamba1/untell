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
import os
import re

# RUN DIRECTLY (`python .../untell/scripts/quality.py`), put the directory that *contains* the package
# on sys.path so `import untell` resolves from any cwd. SKILL.md tells Claude to run this file by
# path on the zero-dependency tier, where nothing is installed — without this it dies on its first
# `from untell...` line. Must sit BEFORE those imports: below them it is unreachable.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

from untell.text_split import aligned_chunks  # noqa: E402

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
    # UNTELL_LITE_NO_TORCH=1 is the documented way to force the pure-stdlib lite path (README's
    # env table, and the fallback note below), but it used to gate only the perplexity detector:
    # the embedding quality gate loaded sentence-transformers anyway whenever it was installed, so
    # "lite" silently ran ~20s of torch imports plus an embedding encode per comparison while being
    # documented (and reported by `method()`) as token-overlap. MEASURED on the slice12 corpus
    # bench: a 309-word flagged doc took 13.19s with the embeddings live and 0.69s on the true
    # stdlib path. Checked BEFORE the cached model so a test flipping the variable mid-process
    # still gets the stdlib gate.
    if os.environ.get("UNTELL_LITE_NO_TORCH") == "1":
        return None
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
    """Dice coefficient over token multisets — the lite fallback. In [0, 1].

    Known limit, measured, and not fixable by tuning: on the zero-dependency path this is the ONLY
    meaning gate, and it cannot detect one destroyed sentence inside a paragraph. Replacing a whole
    sentence with unrelated text in a 280-word document —

        chunk size   score   caught (bar 0.50)?   faithful rewrites rejected
        whole        0.9680  no                   0/25
        90 words     0.8732  no                   0/25
        40 words     0.7500  no                   0/25
        20 words     0.1000  YES                  3/25

    — is only caught at a granularity that also rejects 12% of genuine rewrites, because a faithful
    paraphrase rewords most of a 20-word window too. There is no setting that separates them: Dice
    measures word overlap, and "reworded heavily" and "replaced entirely" both have low overlap.

    So the free path detects meaning *drift across a document* and does not detect meaning
    *destruction in one sentence*. That is a real gap in the zero-install configuration and the
    reason `.[full]` installs the entailment and role gates, which do separate the two.
    """
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
    # Long input is scored piecewise, at the WORST piece. Both embedding backends truncate, so a
    # single call reads only the front of a long document. Measured, replacing an entire sentence
    # with unrelated text ("The intervention halved mortality" -> "Cats are pleasant animals"):
    #
    #     words   edit at the START   edit at the END
    #        76   0.5775              0.7824
    #       144   0.8189              0.9061
    #       280   0.8577              1.0000   <- identical, to a gate whose bar is 0.76
    #       552   0.8577              1.0000
    #
    # 1.0000 is not "similar enough", it is the model reporting the two texts as the same string:
    # the changed sentence is past the tokeniser's cut and was never embedded. The bar could be set
    # anywhere and this would still pass. Same defect as the entailment gate, same fix, and the
    # chunking helper is shared with it so the two cannot drift.
    #
    # min, not mean: meaning destroyed in one paragraph is destroyed, and averaging it against four
    # untouched paragraphs is what hid it in the first place.
    chunks = aligned_chunks(a, b)
    # Recurse only into pieces that are strictly smaller than the pair they came from. `len(chunks)
    # > 1` is not a termination guarantee: it says the splitter produced several pieces, not that
    # any of them shrank, and a piece the same size as its parent recurses forever.
    #
    # MEASURED: this crashed a real run. `untell-holdout --rewriter ensemble` on RAID seed 2 died
    # with `RecursionError: maximum recursion depth exceeded` inside this function, having produced
    # a 185KB traceback of nothing but this line. The exact input was not isolated — a sweep of 4000
    # synthetic shapes and 3000 small-vocabulary pairs reproduced no cycle, so the trigger is
    # something about real rewriter output that neither sweep generated.
    #
    # Guarding the invariant rather than the input, because the invariant is the thing that has to
    # hold for any input: a recursion that only descends into strictly smaller work terminates,
    # whatever the splitter does. A pair that does not shrink is scored directly below instead,
    # which is what would have happened anyway had the splitter returned it whole.
    parent = len(a.split()) + len(b.split())
    smaller = [(ca, cb) for ca, cb in chunks if len(ca.split()) + len(cb.split()) < parent]
    if len(chunks) > 1 and len(smaller) == len(chunks):
        return min(similarity(ca, cb) for ca, cb in smaller)
    # BERTScore is NOT used as the gate. It was, as the "higher-fidelity backend", and MEASURED
    # 2026-08-09 it is unusable for this job — not mis-tuned, inverted:
    #
    #     faithful paraphrases        0.7995 - 0.8409
    #     meaning-CHANGED rewrites    0.8526 - 0.9577
    #
    # Every meaning-changed pair scored ABOVE every faithful one, so no threshold separates them.
    # The reason is structural: BERTScore rewards token-level overlap, and a negation flip changes
    # one word while an honest paraphrase changes many. Against the shipped BERTSCORE_BAR of 0.88
    # it rejected 19 of 20 real composite rewrites — with `pip install untell[quality]`, the loop
    # threw away 95% of its own good candidates.
    #
    # This is the same failure the module docstring already records for cosine similarity, which is
    # why the NLI gate exists. BERTScore has it too, and being a stronger metric does not help: the
    # thing being measured is the wrong thing. `_bert_score_similarity` is kept for direct API
    # callers and its tests (recall against a reference is a genuinely useful number — just not a
    # meaning gate), but no CLI command reports it: there is no `untell-quality` script, and this
    # module's own CLI emits only similarity/method/confidence/bar/passes.
    cos = _cosine_similarity(a, b)
    if cos is not None:
        # Clamp raw cosine into [0, 1]; the 0.76 bar lives on this raw-cosine scale.
        return max(0.0, min(1.0, cos))
    # No embedding backend (the lightweight training environment reward.py describes, or
    # UNTELL_LITE_NO_TORCH=1): fall back to token overlap. The inverted `is None` branch was
    # reintroduced by a stash-pop conflict merge (aee3d2e) and made this line UNREACHABLE —
    # `max(0.0, min(1.0, None))` raises TypeError, so the documented fallback crashed instead
    # of running.
    return token_overlap(a, b)


def method() -> str:
    """Report which backend `similarity` will use: 'embedding' or 'token_overlap'.

    "bertscore" is no longer a possible answer. It used to be returned whenever `bert-score` was
    importable, which then selected BERTSCORE_BAR — and the gate rejected 19 of 20 real rewrites.
    Reporting a backend the gate does not use would leave `recommended_bar` picking a bar for a
    path that is never taken, which is how that combination produced 0.5 for a cosine score.
    """
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
    # No bertscore branch: `similarity` no longer routes the gate through BERTScore, so a bar for
    # it would describe a path that is not taken. BERTSCORE_BAR is kept for the reported metric.
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
            # `bertscore` was still advertised here long after `method()` stopped being able to return
        # it — its docstring says so in as many words, and this line said otherwise. A user reading
        # --help to learn the JSON schema saw an enum value that can never appear, and the history
        # right above makes that worse than cosmetic: selecting BERTSCORE_BAR is what rejected 19
        # of 20 real rewrites, so advertising the value invites someone to write a branch for a
        # path the gate no longer takes.
        "Prints JSON: similarity, method (embedding|token_overlap), confidence, bar,\n"
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
