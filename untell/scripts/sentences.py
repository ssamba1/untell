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
import sys

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


def _targeting_is_uninformative(tier: str) -> bool:
    """Whether the only detector that will score these sentences cannot rank them.

    Measured per-sentence AUROC on real labelled data: 0.493 for the stdlib heuristic against
    0.886-1.000 for every model-backed detector. Re-measured at 100 HC3 sentences while adding the
    result field below, and the shape is worse than a low AUROC suggests: the stdlib path returns
    **6 distinct values across 100 sentences, 91 of them exactly 0.250**, for an AUROC of 0.515.
    The full tier returns 39 distinct values at 0.965. It is not a weak ranking, it is a constant
    with a few exceptions.
    """
    from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector

    if PerplexityBurstinessDetector()._torch_ready():
        return False  # lite auto-upgrades to GPT-2 perplexity, which ranks sentences at AUROC 0.968
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
        **({"warning": UNINFORMATIVE_TARGETING_WARNING} if _targeting_is_uninformative(tier) else {}),
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()  # UTF-8 stdin/stdout/stderr (Windows defaults to cp1252)
    parser = argparse.ArgumentParser(prog="untell-sentences", description="Per-sentence AI scoring.")
    parser.add_argument("text", nargs="?")
    parser.add_argument("--file", "-f")
    parser.add_argument("--tier", default="lite", choices=["lite", "full", "heavy", "commercial"])
    parser.add_argument("--threshold", "-t", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument(
        "--top",
        type=int,
        default=None,
        help="Flag at most this many of the worst sentences (default: ~the worst third).",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.file:
        # read_file(): BOM-aware, sniffs UTF-16/cp1252, handles docx/pdf, rejects binaries.
        # A naive utf-8 open turned a UTF-16 document into mojibake and flagged sentences in THAT.
        from untell.scripts.io_utils import read_file_or_exit

        text = read_file_or_exit(args.file)
    elif args.text:
        text = args.text
    else:
        text = sys.stdin.read()
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
