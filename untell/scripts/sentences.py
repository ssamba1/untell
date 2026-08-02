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


def _warn_if_targeting_is_uninformative(tier: str) -> None:
    """Say once when the only detector that will score these sentences cannot rank them.

    Measured per-sentence AUROC on real labelled data: 0.493 for the stdlib heuristic against
    0.886-1.000 for every model-backed detector. A caller has no way to see that from the output —
    the scores look like scores.
    """
    global _WARNED_UNINFORMATIVE
    if _WARNED_UNINFORMATIVE:
        return
    from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector

    det = PerplexityBurstinessDetector()
    if det._torch_ready():
        return  # lite auto-upgrades to GPT-2 perplexity, which ranks sentences at AUROC 0.968
    from untell.detectors.base import load_detectors

    if any(d.name != "perplexity_burstiness" for d in load_detectors(tier)):
        return  # some model-backed detector is present and will do the ranking
    _WARNED_UNINFORMATIVE = True
    logger.warning(
        "per-sentence targeting on the pure-stdlib path is near-chance (measured AUROC 0.493 on "
        "labelled data, vs 0.89-1.00 for the model-backed detectors). The 'flagged' sentences are "
        "close to arbitrary. Install .[full] for targeting that means anything."
    )


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
    sents = split_sentences(text)
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
        from untell.scripts.io_utils import read_file

        text = read_file(args.file)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
