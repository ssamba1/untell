"""Ensemble detector scoring — the skill's eyes on the text.

Loads every detector available at the requested tier, scores the text with each, and emits
JSON the skill (Claude) reads as feedback:

    {
      "tier": "lite",
      "detectors": {"perplexity_burstiness": 0.71, ...},
      "max": 0.71,          # the proxy the loop drives below threshold (multi-detector evasion)
      "mean": 0.71,
      "threshold": 0.30,
      "flagged": true       # max >= threshold => still looks AI, keep rewriting
    }

The ``max`` aggregation targets the hardest detector in the ensemble (report gap #3): a rewrite
only "passes" when *every* detector is under threshold.

CLI / console entry (`untell-score`):
    untell-score "<text>"
    untell-score --file path.txt --tier full --threshold 0.3
    echo "text" | untell-score
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from untell.detectors.base import _TIER_RANK, load_detectors, resolved_tier

logger = logging.getLogger(__name__)
# (`python scripts/score.py`) rather than imported as part of the `untell` package,
# put the directory that *contains* the package on sys.path so `import untell`
# resolves regardless of the current working directory.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break


DEFAULT_THRESHOLD = 0.30


_MAX_INPUT_CHARS = 50_000  # detectors truncate at 512 tokens anyway; cap input length to avoid OOM


def batch_score_texts(
    texts: list[str],
    tier: str = "full",
    threshold: float = DEFAULT_THRESHOLD,
) -> list[dict]:
    """Score multiple texts with the detector ensemble, loading detectors ONCE for the batch.

    Each text gets the same result dict shape as ``score_text``. Use this when you have many
    short texts (e.g. sentences) to score — avoids re-initialising detectors per call.
    """
    if not texts:
        return []
    detectors = load_detectors(tier)
    return [_score_with_detectors(detectors, _truncate(t), tier, threshold) for t in texts]


def _truncate(text: str) -> str:
    """Truncate absurdly long input so detectors don't OOM on the full tier."""
    if len(text) > _MAX_INPUT_CHARS:
        return text[:_MAX_INPUT_CHARS]
    return text


def score_text(text: str, tier: str = "full", threshold: float = DEFAULT_THRESHOLD) -> dict:
    """Score ``text`` with the available detector ensemble; return the result dict.

    A detector that fails to load or score (e.g. a broken ML env) is **excluded** from the
    aggregate — it is never folded in as a neutral ``0.5``, which would silently pin ``max`` at
    a meaningless value. The reported ``tier`` reflects the detectors that actually produced a
    number, so a full-tier run whose ML stack is broken honestly reports ``lite`` (plus a
    ``warning`` and a ``failed_detectors`` list), instead of looking like a real full-tier score.
    """
    return _score_with_detectors(load_detectors(tier), _truncate(text), tier, threshold)


def _score_with_detectors(
    detectors: list,
    text: str,
    tier: str = "full",
    threshold: float = DEFAULT_THRESHOLD,
) -> dict:
    """Score ``text`` against a *pre-loaded* detector list (avoids re-initialisation)."""
    scores: dict[str, float | None] = {}
    live = []  # detectors that produced a genuine numeric score
    out_of_range_raw: dict[str, float] = {}  # name -> the raw value before clamping
    for d in detectors:
        try:
            val = d.score(text)
        except Exception as exc:  # a flaky/broken detector must not crash or skew the loop
            scores[d.name] = None  # type: ignore[assignment]
            scores[f"{d.name}__error"] = str(exc)[:140]  # type: ignore[assignment]
            continue
        if val is None:  # detector explicitly produced no signal -> exclude, don't fake a 0.5
            scores[d.name] = None  # type: ignore[assignment]
            continue
        # Defensive clamp at the AGGREGATION layer, not just in each adapter. A detector is supposed
        # to return P(AI) in [0, 1], but this session found three adapters shipping wrong values, and
        # an out-of-range score does real damage here: a commercial API answering on a 0-100 scale
        # makes ai_percent read 8500.0, and the common "-1 means error" sentinel reads as MORE human
        # than any real text, so broken-detector output would look like a perfect result. Clamping is
        # the safe direction; the raw value is surfaced so the adapter bug is still visible.
        # The conversion is INSIDE its own guard: `float()` on a non-numeric value raises, and this
        # line sits outside the try above, so an adapter handing back an error string instead of a
        # number took down the whole scoring call rather than excluding itself.
        try:
            raw = float(val)
        except (TypeError, ValueError):
            scores[d.name] = None  # type: ignore[assignment]
            scores[f"{d.name}__error"] = f"non-numeric score {val!r}"  # type: ignore[assignment]
            continue
        # NaN is neither < 0 nor > 1, so it slips through the clamp below untouched and then
        # poisons everything downstream: max and mean become NaN, `NaN >= threshold` is False so
        # `flagged` reads False — a confident "this is human" produced by a broken detector — and
        # json.dumps emits a bare NaN, which is not valid JSON for any API client.
        if raw != raw:
            scores[d.name] = None  # type: ignore[assignment]
            scores[f"{d.name}__error"] = "detector returned NaN"  # type: ignore[assignment]
            continue
        clamped = 0.0 if raw < 0.0 else (1.0 if raw > 1.0 else raw)
        if clamped != raw:
            # Recorded OUTSIDE the detectors dict on purpose. Every consumer that iterates
            # `detectors` filters sidecars by `endswith("__error")` — run.py, verify.py and
            # training/reward.py all do — so adding a differently-suffixed FLOAT key here silently
            # broke them: reward.py folded the raw 100.0 from a 0-100-scale API into its weighted
            # mean as a phantom detector, turning a correct ~0.75 reward into -49.5. Keeping the
            # diagnostic out of the dict removes that trap for every present and future consumer.
            out_of_range_raw[d.name] = round(raw, 4)
        scores[d.name] = round(clamped, 4)
        live.append(d)

    numeric = [v for v in scores.values() if isinstance(v, (int, float))]
    mx = max(numeric) if numeric else 0.0
    mean = sum(numeric) / len(numeric) if numeric else 0.0
    effective = resolved_tier(live) if live else "lite"
    failed = [k[: -len("__error")] for k in scores if k.endswith("__error")]
    result: dict = {
        "tier": effective,
        "tier_requested": tier,
        "detectors": scores,
        "max": round(mx, 4),
        "mean": round(mean, 4),
        "ai_percent": round(mx * 100, 1),  # 0-100 AI-likelihood (the headline number competitors show)
        "threshold": threshold,
        "flagged": bool(numeric) and mx >= threshold,
    }
    if failed:
        result["failed_detectors"] = failed
    if out_of_range_raw:
        result["out_of_range_detectors"] = sorted(out_of_range_raw)
        result["out_of_range_raw"] = out_of_range_raw
    if not numeric:
        # NOTHING was scored. max/mean are 0.0 placeholders, and 0.0 otherwise reads as a confident
        # "definitely human" — the most misleading value this function could return. Say so
        # explicitly rather than letting a caller mistake an unscored result for a clean one.
        result["scored"] = False
        result.setdefault(
            "warning", "no detector produced a score — max/mean are placeholders, not a verdict"
        )
    # Loudly flag a silent downgrade: full requested, but the ML stack didn't produce scores.
    if _TIER_RANK.get(tier, 0) > _TIER_RANK.get(effective, 0):
        result["warning"] = (
            f"requested tier '{tier}' but only '{effective}' produced scores"
            + (f"; failed to load: {', '.join(failed)}" if failed else "")
            + f". The reported numbers reflect the '{effective}' tier only "
            "(commonly a NumPy 2.x / torch mismatch — see the README troubleshooting section)."
        )
    return result


def _read_input(args: argparse.Namespace) -> str:
    if args.file:
        with open(args.file, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    if args.text:
        return args.text
    return sys.stdin.read()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()  # UTF-8 stdin/stdout/stderr (Windows defaults to cp1252)
    parser = argparse.ArgumentParser(
        prog="untell-score",
        description="Score text with the local AI-detector ensemble and print JSON.",
    )
    parser.add_argument("text", nargs="?", help="Text to score (or use --file / stdin).")
    parser.add_argument("--file", "-f", help="Read text from this file.")
    parser.add_argument(
        "--tier",
        default="full",
        choices=["lite", "full", "heavy", "commercial"],
        help="Max detector tier to attempt; auto-degrades to what is installed/configured "
        "(default: full). 'commercial' adds the paid API checkers whose keys are set.",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="suppress the stderr progress/tier notices (stdout JSON is unaffected)",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Max-proxy P(AI) below which text is considered human-passing (default: {DEFAULT_THRESHOLD}).",
    )
    args = parser.parse_args(argv)

    from untell._env import load_env

    load_env()  # pick up commercial keys from a .env file if present (for --tier commercial)

    text = _read_input(args)
    if not text.strip():
        print(json.dumps({"error": "empty input"}))
        return 2

    # Say what is about to happen BEFORE it happens. The full tier loads real transformer models —
    # measured at ~19s cold on CPU — during which the only output is raw HuggingFace weight-loading
    # bars and HF Hub warnings. That reads as a hang, and nothing told the user there is an instant
    # alternative. stderr keeps stdout pure JSON for the skill to parse.
    if args.tier in ("full", "heavy") and not args.quiet:
        print(
            f"[untell-score] loading the '{args.tier}' detector tier — real models, ~20s on first "
            "run (cached after). Use --tier lite for an instant zero-dependency heuristic.",
            file=sys.stderr,
        )

    result = score_text(text, tier=args.tier, threshold=args.threshold)
    # Log which tier actually ran to stderr (stdout stays pure JSON for the skill to parse). A direct
    # stderr write (not logging) so it survives the root logger sitting at WARNING and is captured by
    # the current sys.stderr under test.
    if not args.quiet:
        print(f"[untell-score] tier requested={args.tier} ran={result['tier']}", file=sys.stderr)
    # ensure_ascii=True: detector error strings may carry non-ASCII; never crash a Windows stdout.
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
