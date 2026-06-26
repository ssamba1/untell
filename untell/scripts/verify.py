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

from untell.detectors.base import clamp01
from untell.detectors.commercial import CopyleaksDetector, commercial_detectors
from untell.scripts.score import DEFAULT_THRESHOLD


def verify(
    text: str,
    threshold: float = DEFAULT_THRESHOLD,
    sandbox: bool = False,
    browser: list[str] | None = None,
) -> dict:
    """Score ``text`` against every configured commercial checker; return a verdict dict.

    ``sandbox=True`` puts Copyleaks in free mock mode (pipeline test only — scores not meaningful).
    ``browser`` is a list of free-web-UI checker names (e.g. ``["zerogpt"]``) to drive via Playwright
    (no API key, but slow/fragile — see untell.browser_check).
    """
    detectors = commercial_detectors()
    if sandbox:
        for d in detectors:
            if isinstance(d, CopyleaksDetector):
                d.sandbox = True
    results: dict[str, dict] = {}
    names: list[str] = []

    for d in (d for d in detectors if d.available()):
        names.append(d.name)
        try:
            ai = clamp01(float(d.score(text)))
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

    passing = [n for n, r in results.items() if r.get("passes")]
    return {
        "configured": names,
        "threshold": threshold,
        "results": results,
        "passes_all": bool(names) and all(r.get("passes") for r in results.values()),
        "n_configured": len(names),
        "n_passing": len(passing),
    }


def _render(v: dict) -> str:
    if not v["configured"]:
        return (
            "No commercial checkers configured. Set API keys (ORIGINALITY_API_KEY, GPTZERO_API_KEY, "
            "WINSTON_API_KEY, SAPLING_API_KEY, ZEROGPT_API_KEY, COPYLEAKS_EMAIL+COPYLEAKS_API_KEY) "
            "and install .[commercial]. Cannot verify 'passes all checkers' without them."
        )
    lines = [f"AI-checker verification (threshold {v['threshold']}: AI prob must be below it)", ""]
    for name, r in v["results"].items():
        if r.get("error"):
            lines.append(f"  {name:12} ERROR: {r['error']}")
        else:
            mark = "PASS" if r["passes"] else "FAIL"
            lines.append(f"  {name:12} AI={r['ai']:.3f}  [{mark}]")
    lines.append("")
    lines.append(
        f"PASSES ALL {v['n_configured']} CHECKERS"
        if v["passes_all"]
        else f"FAILS — {v['n_passing']}/{v['n_configured']} checkers passed"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from untell._env import load_env

    load_env()  # pick up keys from a .env file if present
    parser = argparse.ArgumentParser(prog="untell-verify", description="Verify text against commercial AI checkers.")
    parser.add_argument("text", nargs="?", help="text to verify (or --file / stdin)")
    parser.add_argument("--file", "-f", help="read text from this file")
    parser.add_argument("--threshold", "-t", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--json", action="store_true")
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
        with open(args.file, encoding="utf-8") as fh:
            text = fh.read()
    elif args.text:
        text = args.text
    else:
        text = sys.stdin.read()
    if not text.strip():
        print(json.dumps({"error": "empty input"}))
        return 2

    v = verify(text, threshold=args.threshold, sandbox=args.sandbox, browser=browser)
    print(json.dumps(v, ensure_ascii=True, indent=2) if args.json else _render(v))
    # exit 0 only when there is at least one checker AND all pass
    return 0 if v["passes_all"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
