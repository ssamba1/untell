"""Per-sentence AI scoring — find the exact sentences a detector flags.

The closed loop is far more efficient when it rewrites only the sentences that read as AI, instead of
re-rolling the whole paragraph (demonstrated live: ZeroGPT flagged an aphoristic closer + opener; fixing
just those took a stuck 35% to 0%). This module scores each sentence and returns the flagged ones, which
the rewriter then targets.

    untell-sentences "Your paragraph here." --tier lite
"""

from __future__ import annotations

import argparse
import json
import logging

# Run-as-file support (zero-dep lite tier): when this file is executed directly
# rather than imported as part of the `untell` package, put the directory that
# *contains* the package on sys.path so `import untell` resolves from any cwd.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

from untell.scripts.score import DEFAULT_THRESHOLD, batch_score_texts
from untell.text_split import split_sentences  # noqa: F401  (re-exported: `untell-sentences` API)

logger = logging.getLogger(__name__)


_WARNED_UNINFORMATIVE = False


UNINFORMATIVE_TARGETING_WARNING = (
    "per-sentence targeting on the pure-stdlib path is near-chance (measured AUROC 0.493 on "
    "labelled data, vs 0.89-1.00 for the model-backed detectors). The 'flagged' sentences are "
    "close to arbitrary. Install .[full] for targeting that means anything."
)


def _targeting_is_uninformative(tier: str, modes: dict | None = None) -> bool:
    """Whether the only detector that scored these sentences could not rank them.

    Measured per-sentence AUROC on real labelled data: 0.493 for the stdlib heuristic against
    0.886-1.000 for every model-backed detector. Re-measured at 100 HC3 sentences while adding the
    result field below, and the shape is worse than a low AUROC suggests: the stdlib path returns
    **6 distinct values across 100 sentences, 91 of them exactly 0.250**, for an AUROC of 0.515.
    The full tier returns 39 distinct values at 0.965. It is not a weak ranking, it is a constant
    with a few exceptions.

    THE 0.886-1.000 RANGE DOES NOT REPRODUCE ON HC3 SENTENCES, and this function's whole purpose is
    to decide when the ranking can be trusted. Re-measured 2026-08-12 over 40 human and 40 AI HC3
    sentences of 8+ words, scoring each one on its own:

        detector                AUROC    human mean    ai mean
        hc3_roberta             0.944       0.400        0.997
        perplexity_burstiness   0.831       0.083        0.275
        mage                    0.815       0.618        1.000
        roberta_openai          0.813       0.376        0.746
        fast_detectgpt          0.806       0.260        0.614
        ENSEMBLE max            0.813

    Only `hc3_roberta` clears 0.886, and it is the one trained on HC3 — home-field advantage this
    repository already documents. The other four sit near 0.81.

    What that costs in practice, at the shipped 0.30 cut: 36 of 40 HUMAN sentences flag, 25 of 40
    score at or above 0.99. Targeting a deliberately mixed document — a 7-sentence AI block inside
    19 human sentences — gave precision 0.444 and recall 0.571, so five of the nine spans handed to
    the rewriter were human writing.

    Stated as a re-measurement rather than a correction: the original range may have been taken on
    a different labelled sentence set, and this is one corpus at n=40 per class. What it does show
    is that "model-backed targeting is reliable" is not safe to assume for the ensemble `max` this
    module actually ranks on.
    """
    # `modes` comes off the scoring result and reports the path TAKEN. `_torch_ready()` — what
    # this used to ask — reports the path PREDICTED, and those separate on the failure that matters:
    # torch imports, the model raises at scoring time (OOM, a corrupted cache, a transformers
    # version bump), the stdlib heuristic silently produces the numbers, and this function says the
    # ranking is fine. The caveat would be suppressed in precisely the run that needed it, and here
    # that is not cosmetic — these scores decide which spans the rewriter attacks, so a coin-flip
    # ranking aims it at whichever sentences read most human.
    #
    # Same correction `mode()` was added for, and the same one `_verdict_threshold` and the
    # single-sentence caveat in score.py already apply.
    if modes is not None:
        if modes.get("perplexity_burstiness") == "gpt2":
            return False  # GPT-2 perplexity ranks sentences at AUROC 0.968
        if modes.get("perplexity_burstiness") != "stdlib":
            return False  # some other detector produced these scores
    else:
        from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector

        # No scoring result to consult (the pre-scoring log path). Predicting is all that is
        # available here, and it errs toward staying quiet — the result field below is the one a
        # caller reads, and it gets the measured answer.
        if PerplexityBurstinessDetector()._torch_ready():
            return False
    from untell.detectors.base import load_detectors

    # Some model-backed detector is present and will do the ranking.
    return not any(d.name != "perplexity_burstiness" for d in load_detectors(tier))


def _warn_if_targeting_is_uninformative(tier: str) -> None:
    """Log it once per process. The RESULT carries it on every call — see `score_sentences`.

    Once-per-process is right for a log line and wrong for a verdict. A long-running API server
    logs this on its first request and is silent for every caller after that, and no caller reads
    the server's log anyway. Same split the score result already makes: warn the terminal once,
    return the caveat every time.
    """
    global _WARNED_UNINFORMATIVE
    if _WARNED_UNINFORMATIVE or not _targeting_is_uninformative(tier):
        return
    _WARNED_UNINFORMATIVE = True
    logger.warning(UNINFORMATIVE_TARGETING_WARNING)



# Whether THIS document's sentence scores can be ranked at all, which is a different question from
# whether the detector that produced them is any good.
#
# `_targeting_is_uninformative` above asks the second: it fires when the only scorer is the stdlib
# heuristic. On the full tier it stays silent, and MEASURED at tier=full on 10 AI documents per
# corpus, spread of per-sentence `max` WITHIN one document:
#
#     corpus   mean spread   median   below 0.05   distinct values / sentences
#     HC3        0.0088      0.0022      9 / 10            0.36
#     RAID       0.6595      0.6855      0 / 10            0.99
#
# On HC3 two documents in eight scored **every sentence at exactly 0.9992** — one distinct value
# across eight sentences, so "the worst third" is whichever order the sort happened to produce. On
# RAID the same detectors on the same tier separate sentences almost perfectly.
#
# The difference is `hc3_roberta`, which is fine-tuned on HC3 and therefore pins every sentence of it
# at the ceiling. So the TIER is the wrong thing to condition on in both directions, and the
# document's own spread is the right one: it is corpus-independent, needs no knowledge of what any
# detector was trained on, and fires exactly when the ranking cannot be trusted.
#
# 0.05 sits in the empty gap between the two populations — HC3's worst document reaches 0.0610 and
# every RAID document exceeds 0.5.
_TARGETING_SPREAD_BAR = 0.05
_MIN_SENTENCES_FOR_SPREAD = 3

UNRANKABLE_TARGETING_WARNING = (
    "these sentences are not rankable: the highest and lowest per-sentence score in this document "
    "differ by less than {bar}, so 'flagged' is close to whichever order the sort produced. This "
    "happens when a detector is at its ceiling on every sentence — MEASURED at tier=full, mean "
    "within-document spread 0.0088 on HC3 against 0.6595 on RAID, and two HC3 documents in eight "
    "scored every sentence at exactly 0.9992. Rewrite the whole passage rather than the flagged "
    "spans."
)


def _targeting_is_unrankable(rows: list[dict]) -> bool:
    """True when this document's own sentence scores are too close together to order."""
    scores = [r["ai"] for r in rows]
    if len(scores) < _MIN_SENTENCES_FOR_SPREAD:
        return False
    return (max(scores) - min(scores)) < _TARGETING_SPREAD_BAR


def score_sentences(
    text: str, tier: str = "lite", threshold: float = DEFAULT_THRESHOLD, top: int | None = None
) -> dict:
    """Score each sentence; flag the WORST ones to rewrite first.

    Per-sentence scores are noisy — short sentences especially, where signals like burstiness are
    undefined — so this targets the worst sentences **relative to the rest** (capped) rather than
    every sentence over an absolute threshold, which floods short text with false positives. The
    ``flagged`` list is "rewrite these first", not an absolute per-sentence verdict.

    **How well this actually works depends entirely on the tier.** MEASURED per-sentence AUROC over
    150 human and 150 ChatGPT sentences drawn from HC3 paragraphs:

        hc3_roberta        1.000        full (GPT-2) perplexity   0.968
        fast_detectgpt     0.940        roberta_openai            0.886
        lite (stdlib)      **0.493**  <- a coin flip

    So on the zero-dependency path — no torch, the pure stdlib heuristic — per-sentence targeting
    points the rewriter at essentially random sentences. Note that "lite" auto-upgrades to GPT-2
    whenever torch is importable, so this only bites a genuinely dependency-free install; the
    caller is told once, because the README markets sentence targeting as a headline feature and
    on that path it is not one.
    """
    _warn_if_targeting_is_uninformative(tier)
    # Split within LAYOUT BLOCKS, not across the whole document. split_sentences breaks on
    # terminators, and a bullet list, transcript or headings outline has none — so the entire
    # document came back as one "sentence" and the worst-sentence list named all of it, which is no
    # localisation at all. MEASURED at 40 lines each: bullets 1 unit, transcript 1, outline 1,
    # semicolon run-on 1, against 40 for ordinary prose. A line that carries a marker is its own
    # unit; consecutive plain lines stay together so a soft-wrapped paragraph is still split by
    # sentence rather than by line.
    from untell.layout import blocks

    sents = [s for block in blocks(text) for s in split_sentences(block)] or split_sentences(text)
    # Score all sentences in one batch so the detector ensemble loads once for the whole
    # paragraph rather than once per sentence (the hot path on the full tier).
    results = batch_score_texts(sents, tier=tier, threshold=threshold)
    scored = [(s, float(r["max"])) for s, r in zip(sents, results)]
    n = len(scored)
    if top is None:
        top = max(1, (n + 2) // 3)  # the worst ~third, at least one
    elif top < 0:
        # `order[:top]` with a negative `top` is a Python slice from the END, not a count: -1
        # flagged n-1 sentences (2 of 3, more than `--top 1`) and -5 flagged 0. The CLI refuses
        # this before it arrives, but this function is importable, so it refuses it too rather
        # than turning a nonsense count into a plausible-looking answer.
        raise ValueError(f"top must be 0 or greater, got {top}")
    # Rank by score (desc); flag the worst `top` that are also at/above threshold.
    order = sorted(range(n), key=lambda i: scored[i][1], reverse=True)
    flag_idx = {i for i in order[:top] if scored[i][1] >= threshold}
    rows: list[dict] = []
    flagged: list[str] = []
    for i, (s, ai) in enumerate(scored):
        is_flagged = i in flag_idx
        rows.append({"text": s, "ai": round(ai, 4), "flagged": is_flagged})
        if is_flagged:
            flagged.append(s)
    return {
        "tier": tier,
        "threshold": threshold,
        "sentences": rows,
        "flagged": flagged,
        "note": "per-sentence scores are noisy (esp. short sentences); 'flagged' = the worst "
        "sentences to rewrite first, not an absolute verdict",
        # The caveat that matters most is the one a machine client could not see: the log line
        # above fires once per PROCESS, so an API server tells its first caller and nobody else.
        **(
            {"unrankable": True}
            if _targeting_is_unrankable(rows)
            else {}
        ),
        **(
            {"warning": _warning_for(text, tier, results, rows)}
            if _warning_for(text, tier, results, rows)
            else {}
        ),
    }


def _warning_for(text: str, tier: str, results: list, rows: list[dict]) -> str | None:
    """The caveat this result carries, most-disqualifying first.

    Language leads. A German paragraph came back with per-sentence AI flags and a caveat about the
    TIER — true, and beside the point, because the detectors and the catalogue are English-only and
    no tier makes them read German. The surface was in the matrix as "warned" purely because a
    standing note happened to be present, which is the failure mode that made this worth checking on
    every surface at once rather than one at a time:

        input         score  tells  sentences  humanize  humanness
        non-english     yes    yes        yes*      yes        yes      (* tier only, before this)

    `score_text`, `score_tells` and `humanness` each had a version of the same gap, found and fixed
    one at a time in the two preceding results. This is the fourth and it was found by the assertion
    written after the third — not "did it warn" but "did it warn about the right thing".
    """
    from untell.scripts.tells import looks_non_english

    if text.strip() and looks_non_english(text):
        return (
            "this text reads as a Latin-script language other than English. The detectors and the "
            "tell catalogue are English-only, so these per-sentence scores are not verdicts about "
            "these sentences — no tier changes that, and the rewriter returns such text unchanged."
        )
    # A document with no letters has no prose for the per-sentence scores to be about. `score_tells`
    # draws the same line ("the text contains no letters at all, so there is no prose to read") and
    # `score_text` abstains on the same grounds, and a German paragraph reaching the branch above
    # while `;;;` fell through to a bare tier note would be the fourth surface repeating the
    # wrong-reason failure this function exists to prevent. MEASURED: `;;; ;;; --- ...` scored one
    # sentence at 0.0000 and returned no warning at all — a verdict-shaped list with nothing attached.
    if text.strip() and not any(ch.isalpha() for ch in text):
        return (
            "this text contains no letters at all, so there is no prose to read — the per-sentence "
            "scores are placeholders, not verdicts"
        )
    # From the results that were actually produced, not from what was predicted before they were.
    # `results` is non-empty whenever `sents` is.
    if _targeting_is_uninformative(tier, (results[0].get("detector_modes") if results else None)):
        return UNINFORMATIVE_TARGETING_WARNING
    if _targeting_is_unrankable(rows):
        return UNRANKABLE_TARGETING_WARNING.format(bar=_TARGETING_SPREAD_BAR)
    return None


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()  # UTF-8 stdin/stdout/stderr (Windows defaults to cp1252)
    parser = argparse.ArgumentParser(prog="untell-sentences", description="Per-sentence AI scoring.")
    parser.add_argument("text", nargs="?", help="text to scan (or --file / stdin)")
    parser.add_argument("--file", "-f", help="read text from this file (.txt/.docx/.pdf)")
    parser.add_argument(
        "--tier",
        default="lite",
        choices=["lite", "full", "heavy", "commercial"],
        help="max detector tier to attempt (default: lite)",
    )
    # Range-checked, like the other scoring commands. `--threshold 5` flagged 0 sentences of 1,
    # because a probability cannot exceed 1 — an answer that looks like "nothing to rewrite".
    from untell.scripts.run import _PROBABILITY, _TOP

    parser.add_argument(
        "--threshold", "-t", type=_PROBABILITY, default=DEFAULT_THRESHOLD,
        help="P(AI) at or above which a sentence is flagged (default: 0.3)",
    )
    parser.add_argument(
        "--top",
        type=_TOP,
        default=None,
        help="Flag at most this many of the worst sentences (default: ~the worst third).",
    )
    parser.add_argument("--json", action="store_true", help="emit the full result as JSON")
    args = parser.parse_args(argv)

    if args.file:
        # read_file(): BOM-aware, sniffs UTF-16/cp1252, handles docx/pdf, rejects binaries.
        # A naive utf-8 open turned a UTF-16 document into mojibake and flagged sentences in THAT.
        from untell.scripts.io_utils import read_file_or_exit

        text = read_file_or_exit(args.file)
    elif args.text:
        text = args.text
    else:
        # None means stdin is a terminal. Reading it would block until the user sent EOF, with no
        # prompt and no output — the command looks hung when what they wanted was the usage line.
        from untell.scripts.io_utils import read_stdin_or_none

        piped = read_stdin_or_none()
        if piped is None:
            print(json.dumps({"error": "no input: pass text, --file PATH, or pipe to stdin"}))
            return 2
        text = piped
    if not text.strip():
        print(json.dumps({"error": "empty input"}))
        return 2

    result = score_sentences(text, tier=args.tier, threshold=args.threshold, top=args.top)
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        for row in result["sentences"]:
            mark = "AI " if row["flagged"] else "ok "
            print(f"[{mark}{row['ai']:.2f}] {row['text']}")
        print(f"\n{len(result['flagged'])}/{len(result['sentences'])} sentences flagged to rewrite first.")
        print(f"note: {result['note']}")
    # 2 when the catalogue and detectors cannot read this script at all — the same code and reasoning
    # `untell-verify`, `untell-score`, `untell-tells` and `untell-humanness` use. MEASURED on a
    # Chinese paragraph, this command printed `[ok 0.00]` beside the text and exited 0: a per-sentence
    # score of 0.00 labelled "ok", on input no pattern in the catalogue can match.
    #
    # The near-chance stdlib path deliberately does NOT return 2. Something did run there, the result
    # carries `warning` saying how little it is worth, and returning 2 on every default lite install
    # would make the code mean "this tier is weak" rather than "nothing ran".
    from untell.scripts.tells import score_tells

    if score_tells(text).get("language_supported") is False:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
