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

# RUN DIRECTLY (`python .../untell/scripts/verify.py`), put the directory that *contains* the package
# on sys.path so `import untell` resolves from any cwd. Must come BEFORE any `from untell...`
# import: below them it is unreachable, because the import raises ModuleNotFoundError first. An
# editable install hides that on every developer machine — it only shows on a bare interpreter,
# which is the zero-dependency skill path the README leads with.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

from untell._env import load_env  # noqa: E402
from untell.detectors.base import clamp01
from untell.scripts.score import (
    DEFAULT_THRESHOLD,
    _threshold_range_warning,
    score_text,
)


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
        # Verdict surfaces use the CALIBRATED cut, not the loop's optimisation target. `score_text`
        # publishes `verdict_threshold` for exactly this: on the stdlib lite path the swept optimum
        # is 0.45, while the rewrite loop keeps driving against 0.30 so stronger rewriting is not
        # traded away for a kinder verdict. That fix landed in `score` and not here, and this
        # command is the one that exits non-zero.
        #
        # MEASURED over 40 human HC3 texts on the stdlib lite path:
        #
        #     raw max >= 0.30          21/40  (52%)
        #     score_text "flagged"      7/40  (18%)   <- calibrated
        #     verify "not passing"     21/40  (52%)   <- this surface, uncalibrated
        #
        # Two commands in one tool disagreeing about the same text, with the CI-facing one nearly
        # three times more likely to call human writing AI.
        #
        # Only when the caller did not choose a threshold. An explicit `--threshold` is a request,
        # and silently substituting a different number would be its own dishonesty.
        verdict_cut = threshold
        if threshold == DEFAULT_THRESHOLD:
            published = local.get("verdict_threshold")
            if isinstance(published, (int, float)) and not isinstance(published, bool):
                verdict_cut = float(published)
        for det_name, val in (local.get("detectors") or {}).items():
            # Skip the diagnostic sidecar keys ("<name>__error", "<name>__out_of_range") — they are
            # metadata about a detector, not detectors, and a float sidecar would otherwise appear
            # here as its own checker row.
            if isinstance(val, (int, float)) and "__" not in det_name:
                key = f"local:{det_name}"
                names.append(key)
                # Carries the cut that judged it, for the reason the `local:max` row already gives
                # below: a pass at 0.38 must not read as a pass at 0.30. These rows moved onto
                # `verdict_cut` when that fix landed and did not gain the field that explains it,
                # so the only row in the report stating its own bar was the summary.
                results[key] = {
                    "ai": round(val, 4),
                    "passes": val < verdict_cut,
                    "verdict_threshold": verdict_cut,
                }
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
                "passes": local["max"] < verdict_cut,
                "tier": local["tier"],
                # Say which cut answered, so a pass at 0.38 is not read as a pass at 0.30.
                "verdict_threshold": verdict_cut,
            }

    for d in (d for d in detectors if d.available()):
        names.append(d.name)
        try:
            raw = d.score(text)
            if raw is None:
                results[d.name] = {"ai": None, "passes": False, "error": "no signal (empty/unavailable for this text)"}
                continue
            ai = clamp01(float(raw))
            if ai != ai:  # NaN: a broken detector must not read as a score (json.dumps would emit bare NaN)
                results[d.name] = {"ai": None, "passes": False, "error": "detector returned NaN"}
                continue
            # Judged at the caller's `threshold`, NOT at `verdict_cut`. That cut is swept for the
            # local stdlib ensemble and published by `score_text` for it; a commercial detector
            # returns its own probability on its own scale, and borrowing a calibration derived
            # from a different scorer would be a guess wearing a measurement's clothes. The row
            # says which bar answered so the two kinds are not read as one.
            results[d.name] = {
                "ai": round(ai, 4),
                "passes": ai < threshold,
                "verdict_threshold": threshold,
            }
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
            # Same reasoning as the commercial rows above: a site's own score, judged at the
            # caller's bar, saying so.
            results[key] = {
                "ai": round(ai, 4),
                "passes": ai < threshold,
                "verdict_threshold": threshold,
            }
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
    # This is the surface that produces a VERDICT and an exit code, so it is the one where an
    # evasion does the most damage: zero-width injection flips an AI text's verdict to clean on
    # 14 of 20 HC3 texts, homoglyph substitution on 13 of 15 (Results 62 and 63). `score_text`
    # warns about both; `verify` was reporting PASS on the same input in silence.
    from untell.scripts.score import _homoglyph_warning, _invisible_char_warning

    # The threshold note belongs here most of all. This is the surface that exits 0 on a pass, so a
    # bar no score can reach turns a CI gate green in silence — MEASURED: at `threshold=45` (a
    # caller meaning 45 per cent) `passes_all` is True on AI text, and before this the only warning
    # anywhere was the generic lite caveat, which quotes "the 0.30 loop threshold" the caller never
    # used.
    # The roster note belongs here for the same reason the threshold one does, and more so: this is
    # the command that exits 0 on a pass. MEASURED on one paragraph at `--tier full` with
    # `UNTELL_DISABLE_MAGE=1`, before this line:
    #
    #     score_text   roster note present
    #     untell_text  roster note present
    #     verify       roster note ABSENT, passes_all True
    #
    # A reduced ensemble can only lower `max`, so it can only turn a fail into a pass — and the one
    # surface that turns a pass into an exit code was the one not saying it had happened.
    # FORWARD the score's own warning rather than re-listing selected caveats by hand. Hand-picking
    # is why this surface kept missing them: every caveat added to `score_text` had to be wired here
    # separately, and three of the four added this session were not. MEASURED across the surfaces,
    # one input per caveat:
    #
    #     caveat             score_text   untell_text   verify
    #     no prose              yes          yes         NO
    #     mostly locked         yes          yes         NO
    #     one sentence/para     yes          yes         NO
    #     threshold range       yes          yes         yes    <- wired by hand, one loop earlier
    #
    # `untell_text` never had the problem because it forwards `best_score["warning"]`. This does the
    # same, which also retires the two caveats that had been wired here by hand — the threshold note
    # and the short-roster note both travel inside the forwarded string now.
    caveats: list[str] = []
    if tier is not None and isinstance(local, dict):
        forwarded = local.get("warning")
        if forwarded:
            caveats.append(forwarded)
    else:
        # Commercial-only mode: no local score ran, so there is no warning to forward and the
        # text-shape caveats are the only ones that can apply.
        caveats = [w for w in (_invisible_char_warning(text), _homoglyph_warning(text)) if w]
        threshold_note = _threshold_range_warning(threshold)
        if threshold_note:
            caveats.append(threshold_note)

    out = {
        "configured": names,
        "threshold": threshold,
        "results": results,
        "passes_all": bool(names) and all(r.get("passes") for r in results.values()),
        "n_configured": len(checkers),
        "n_passing": len(passing),
    }
    if caveats:
        out["warning"] = " ".join(caveats)
    return out


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
        # The aggregate row is marked as one. It is excluded from `n_configured` on purpose — see
        # the comment beside `checkers` — so the table prints two rows above "0/1 checkers passed"
        # and a reader has no way to tell which of the two is not a checker. The count is right and
        # the display was making it look wrong, which is the same reader-facing gap as the detector
        # audit's summary contradicting its own table.
        aggregate = " (aggregate, not counted)" if name.startswith("local:max ") else ""
        if r.get("error"):
            lines.append(f"  {name:24} ERROR: {r['error']}{aggregate}")
        else:
            mark = "PASS" if r["passes"] else "FAIL"
            lines.append(f"  {name:24} AI={r['ai']:.3f}  [{mark}]{aggregate}")
    lines.append("")
    lines.append(
        f"PASSES ALL {v['n_configured']} CHECKERS"
        if v["passes_all"]
        else f"FAILS — {v['n_passing']}/{v['n_configured']} checkers passed"
    )
    # Printed after the verdict, not before it: the verdict is what the reader came for, and a
    # caveat above it would be skimmed past. A PASS obtained this way is the one to distrust.
    if v.get("warning"):
        lines.append("")
        lines.append(f"WARNING: {v['warning']}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """The `untell-verify` argument parser.

    Split out of ``main`` so the tier vocabulary it declares — which includes the "" that means
    commercial-only — can be read without running the CLI. POST /verify restates it, and a test
    pins the two together rather than trusting them to stay in step.
    """
    parser = argparse.ArgumentParser(prog="untell-verify", description="Verify text against AI detectors (local ensemble + commercial checkers).")
    parser.add_argument("text", nargs="?", help="text to verify (or --file / stdin)")
    parser.add_argument("--file", "-f", help="read text from this file")
    # Range-checked, not a bare float. `--threshold 5` was accepted, and since detector scores live
    # in [0, 1] nothing can ever reach it: text scoring 0.826 was marked [PASS], the command printed
    # "PASSES ALL 1 CHECKERS" and exited 0. On the command whose entire job is gating, a slip of the
    # decimal point certifies anything.
    #
    # Every other surface already refuses it — `untell humanize` through this same validator, the
    # REST API with 422, the MCP tools with "a value above 1 can never be reached" — so this was the
    # fourth surface and the one where it mattered most.
    #
    # Imported rather than re-declared, and imported HERE rather than at module scope: one
    # definition of the bound, and `verify --help` does not pay for loading the loop.
    from untell.scripts.run import _PROBABILITY

    parser.add_argument("--threshold", "-t", type=_PROBABILITY, default=DEFAULT_THRESHOLD)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--tier",
        default="full",
        # "" is in `choices` because the help text has always advertised it and the code below
        # already handles it — `(args.tier or "").lower() in ("commercial", "")` maps both to
        # commercial-only. Without it argparse rejected `--tier ''` with exit 2, so the documented
        # invocation was the one thing that could not work.
        choices=["lite", "full", "heavy", "commercial", ""],
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
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()  # UTF-8 stdin/stdout/stderr (Windows defaults to cp1252)
    load_env()  # pick up ANTHROPIC_API_KEY / commercial keys from a .env file if present
    args = build_parser().parse_args(argv)
    browser = [s.strip() for s in args.browser.split(",")] if args.browser else None

    if args.file:
        # read_file(): BOM-aware, sniffs UTF-16/cp1252, handles docx/pdf, rejects binaries.
        # A naive utf-8 open turned a UTF-16 document into mojibake and verified THAT.
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
    #       2 if NOTHING ran — not 0
    #
    # This returned 0 when no checker ran, with the comment "the user just got the empty report".
    # Exit 0 means PASS to everything that reads it. `untell-verify --tier commercial` on a machine
    # with no API keys printed "No checkers ran." and exited 0, so a CI job gating on this command
    # was told the text passed every major AI checker when not one had been consulted.
    #
    # The module docstring already promised the opposite — "with no commercial keys set it reports
    # that no checkers are configured (and exits non-zero), because 'passes all major checkers'
    # cannot be asserted without running against them". The code and the promise disagreed, and the
    # code was wrong.
    #
    # 2 rather than 1, deliberately: 1 means "checkers ran and something failed", which a caller may
    # reasonably act on by rewriting. Nothing ran is a configuration problem, not a verdict about
    # the text, and conflating them would send someone to rewrite text that was never checked.
    if not v["results"]:
        return 2
    return 0 if v["passes_all"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
