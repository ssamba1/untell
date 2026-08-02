"""Pass/fail verification against the commercial AI checkers.

This is the literal "does it pass all major AI detectors" tool. It scores text with every
*configured* commercial detector (those whose API keys are set) and reports, per checker, the AI
probability and whether it is under the pass threshold — plus an overall ``passes_all`` verdict.

    untell-verify "text to check" --threshold 0.30
    untell-verify --file out.txt --json

With no commercial keys set it reports that no checkers are configured (and exits non-zero), because
"passes all major checkers" cannot be asserted without running against them.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from untell._env import load_env

# Run-as-file support
# rather than imported as part of the `untell` package, put the directory that
# *contains* the package on sys.path so `import untell` resolves from any cwd.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

from untell.detectors.base import clamp01
from untell.scripts.score import DEFAULT_THRESHOLD, score_text


def verify(
    text: str,
    threshold: float = DEFAULT_THRESHOLD,
    sandbox: bool = False,
    browser: list[str] | None = None,
    tier: str | None = None,
) -> dict:
    """Score ``text`` against every configured commercial checker; return a verdict dict.

    ``sandbox=True`` puts Copyleaks in free mock mode (pipeline test only — scores not meaningful).
    ``browser`` is a list of free-web-UI checker names (e.g. ``["zerogpt"]``) to drive via Playwright
    (no API key, but slow/fragile — see untell.browser_check).
    """
    # Lazy import: commercial adapters pull in requests (and may fail on broken installs).
    from untell.detectors.commercial import CopyleaksDetector, commercial_detectors

    detectors = commercial_detectors()
    if sandbox:
        for d in detectors:
            if isinstance(d, CopyleaksDetector):
                d.sandbox = True
    results: dict[str, dict] = {}
    names: list[str] = []

    # Local ensemble scores first (when a tier is requested — default is full unless commercial-only).
    if tier is not None:
        local = score_text(text, tier=tier, threshold=threshold)
        for det_name, val in (local.get("detectors") or {}).items():
            # Skip the diagnostic sidecar keys ("<name>__error", "<name>__out_of_range") — they are
            # metadata about a detector, not detectors, and a float sidecar would otherwise appear
            # here as its own checker row.
            if isinstance(val, (int, float)) and "__" not in det_name:
                key = f"local:{det_name}"
                names.append(key)
                results[key] = {"ai": round(val, 4), "passes": val < threshold}
        key = f"local:max ({local['tier']})"
        names.append(key)
        if local.get("scored") is False:
            # Nothing scored, so local["max"] is a 0.0 PLACEHOLDER. Reporting `passes: 0.0 <
            # threshold` here would print a clean pass on a verdict surface whose entire job is an
            # honest answer — the worst possible place to fabricate one.
            results[key] = {
                "ai": None,
                "passes": False,
                "tier": local["tier"],
                "error": "no local detector produced a score",
            }
        else:
            results[key] = {
                "ai": round(local["max"], 4),
                "passes": local["max"] < threshold,
                "tier": local["tier"],
            }

    for d in (d for d in detectors if d.available()):
        names.append(d.name)
        try:
            raw = d.score(text)
            if raw is None:
                results[d.name] = {"ai": None, "passes": False, "error": "no signal (empty/unavailable for this text)"}
                continue
            ai = clamp01(float(raw))
            results[d.name] = {"ai": round(ai, 4), "passes": ai < threshold}
        except Exception as exc:  # surface per-checker failure rather than crashing the verdict
            results[d.name] = {"ai": None, "passes": False, "error": str(exc)[:160]}

    for site in browser or []:
        from untell.browser_check import get_browser_checker

        key = f"{site}(web)"
        names.append(key)
        chk = get_browser_checker(site)
        if chk is None or not chk.available():
            results[key] = {
                "ai": None,
                "passes": False,
                "error": "browser checker unavailable — pip install .[browser] && playwright install chromium",
            }
            continue
        try:
            ai = clamp01(float(chk.check(text)))
            results[key] = {"ai": round(ai, 4), "passes": ai < threshold}
        except Exception as exc:
            results[key] = {"ai": None, "passes": False, "error": str(exc)[:160]}

    # `local:max (<tier>)` is a SUMMARY of the local detector rows above it, not an independent
    # checker. Counting it inflated both sides of the headline: four local detectors with two
    # passing were reported as "2/5 checkers passed", and a run with one local detector read as
    # "1/2". It still gets a row — it is the number the loop drives — but it is excluded from the
    # tally so the count means "checkers", as the sentence says.
    #
    # `passes_all` is unaffected either way: the max is below threshold exactly when every local
    # detector is, so including it could never change that verdict.
    checkers = [n for n in names if not n.startswith("local:max ")]
    passing = [n for n in checkers if results.get(n, {}).get("passes")]
    return {
        "configured": names,
        "threshold": threshold,
        "results": results,
        "passes_all": bool(names) and all(r.get("passes") for r in results.values()),
        "n_configured": len(checkers),
        "n_passing": len(passing),
    }


def _render(v: dict) -> str:
    if not v["results"]:
        return (
            "No checkers ran. Use --tier to select a local detector tier (lite/full/heavy) "
            "or set commercial API keys (ORIGINALITY_API_KEY, GPTZERO_API_KEY, "
            "WINSTON_API_KEY, SAPLING_API_KEY, ZEROGPT_API_KEY, COPYLEAKS_EMAIL+COPYLEAKS_API_KEY) "
            "and install .[commercial]."
        )
    lines = [f"AI-checker verification (threshold {v['threshold']}: AI prob must be below it)", ""]
    for name, r in v["results"].items():
        if r.get("error"):
            lines.append(f"  {name:24} ERROR: {r['error']}")
        else:
            mark = "PASS" if r["passes"] else "FAIL"
            lines.append(f"  {name:24} AI={r['ai']:.3f}  [{mark}]")
    lines.append("")
    lines.append(
        f"PASSES ALL {v['n_configured']} CHECKERS"
        if v["passes_all"]
        else f"FAILS — {v['n_passing']}/{v['n_configured']} checkers passed"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()  # UTF-8 stdin/stdout/stderr (Windows defaults to cp1252)
    load_env()  # pick up ANTHROPIC_API_KEY / commercial keys from a .env file if present
    parser = argparse.ArgumentParser(prog="untell-verify", description="Verify text against AI detectors (local ensemble + commercial checkers).")
    parser.add_argument("text", nargs="?", help="text to verify (or --file / stdin)")
    parser.add_argument("--file", "-f", help="read text from this file")
    parser.add_argument("--threshold", "-t", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--tier",
        default="full",
        choices=["lite", "full", "heavy", "commercial"],
        help="Local detector tier (default: full). Pass 'commercial' or set --tier '' for commercial-only.",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="suppress the stderr progress notice (stdout is unaffected)",
    )
    parser.add_argument(
        "--sandbox",
        action="store_true",
        help="Copyleaks free mock mode — tests the pipeline at no cost (scores are NOT real).",
    )
    parser.add_argument(
        "--browser",
        help="comma-separated free-web-UI checkers to drive via Playwright (e.g. 'zerogpt'). "
        "No API key, but slow/fragile; respect each site's terms.",
    )
    args = parser.parse_args(argv)
    browser = [s.strip() for s in args.browser.split(",")] if args.browser else None

    if args.file:
        # read_file(): BOM-aware, sniffs UTF-16/cp1252, handles docx/pdf, rejects binaries.
        # A naive utf-8 open turned a UTF-16 document into mojibake and verified THAT.
        from untell.scripts.io_utils import read_file

        text = read_file(args.file)
    elif args.text:
        text = args.text
    else:
        text = sys.stdin.read()
    if not text.strip():
        print(json.dumps({"error": "empty input"}))
        return 2

    # Map --tier: 'commercial' or empty string means local-skip (commercial-only).
    tier_arg: str | None = None if (args.tier or "").lower() in ("commercial", "") else args.tier
    # Same courtesy as untell-score: say what is loading BEFORE the ~17s of silent model loading,
    # during which the only output is raw HuggingFace progress bars. stdout stays pure JSON.
    if tier_arg in ("full", "heavy") and not args.quiet:
        print(
            f"[untell-verify] loading the '{tier_arg}' detector tier — real models, ~20s on first "
            "run (cached after). Use --tier lite for an instant zero-dependency check.",
            file=sys.stderr,
        )
    v = verify(text, threshold=args.threshold, sandbox=args.sandbox, browser=browser, tier=tier_arg)
    print(json.dumps(v, ensure_ascii=True, indent=2) if args.json else _render(v))
    # exit  0 if all configured checkers pass
    #       1 if any checker fails (reported)
    #       0 if nothing ran (the user just got the empty report)
    if not v["results"]:
        return 0
    return 0 if v["passes_all"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
