"""Headless untell loop — run the full lock -> score -> rewrite -> restore loop as a CLI.

Inside Claude Code the SKILL.md procedure drives the loop with Claude as the rewriter. This module
is the *standalone* path: a `untell-loop` console command (and `untell_text` API) that runs the
same loop programmatically using a hosted-LLM rewriter (``untell.rewriter``). It reuses the exact
same scripts the skill calls — preserve-lock, the detector ensemble, and the quality gate — so the
two paths stay behaviourally identical.

A rewriter must be configured (``pip install -e ".[api]"`` + ``ANTHROPIC_API_KEY``/``OPENAI_API_KEY``);
without one this returns a clear error rather than silently no-op'ing (use the Claude skill instead).
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

from untell.rewriter import get_rewriter
from untell.scripts.preserve import find_sentinels, lock, restore
from untell.scripts.quality import method, recommended_bar, similarity
from untell.scripts.score import DEFAULT_THRESHOLD, score_text


def _browser_scorer(sites: list[str], mapping: dict, threshold: float):
    """Return a scorer(masked_text)->score-dict that drives one or more free web detectors (no key).

    Scores the *restored* text (what a real detector actually sees) against every available site and
    drives the **max** across them — so the loop must beat ALL configured detectors, not just the
    weakest (the closest thing to "foolproof" we can do for free). Returns None if none are available.
    """
    from untell.browser_check import get_browser_checker
    from untell.scripts.preserve import restore

    checkers = []
    for site in sites:
        chk = get_browser_checker(site)
        if chk is not None and chk.available():
            checkers.append((site, chk))
    if not checkers:
        return None

    label = "browser:" + ",".join(s for s, _ in checkers)

    def _score(masked_text: str) -> dict:
        real = restore(masked_text, mapping)
        scores: dict[str, float | None] = {}
        for name, chk in checkers:
            try:
                scores[name] = round(float(chk.check(real)), 4)
            except Exception as exc:
                scores[name] = None
                scores[f"{name}__error"] = str(exc)[:120]
        numeric = [v for v in scores.values() if isinstance(v, (int, float))]
        mx = max(numeric) if numeric else 0.5
        return {
            "tier": label,
            "detectors": scores,
            "max": round(mx, 4),
            "mean": round(sum(numeric) / len(numeric), 4) if numeric else 0.5,
            "threshold": threshold,
            "flagged": mx >= threshold,
        }

    return _score


def untell_text(
    text: str,
    tier: str = "full",
    threshold: float = DEFAULT_THRESHOLD,
    max_iters: int = 5,
    sim_bar: float | None = None,
    rewriter=None,
    browser: str | list[str] | None = None,
    margin: float = 0.0,
    confirm: int = 0,
    scrub: bool = True,
    polish: bool = False,
    style: str | None = None,
) -> dict:
    """Run the closed loop on ``text``; return a structured result dict.

    Keys: ``final`` (humanized text, spans restored), ``iterations``, ``pre``/``post`` score dicts,
    ``similarity``, ``tier``, ``sim_bar``, ``flagged`` (final), and ``stopped`` (why it stopped).
    If no rewriter is available, returns ``{"error": ...}`` without modifying the text.

    ``browser`` (e.g. ``"zerogpt"`` or ``"zerogpt,detecting-ai"``) scores each iteration against free
    web detector(s) instead of local proxies — optimizing against the **max** across real checkers, no
    API key (slow: ~10s each/iter). ``margin`` adds headroom: the loop only declares success when the
    max score is below ``threshold - margin``, so it doesn't stop on a borderline pass that a noisy
    detector might re-flag (the practical fix for detector non-reproducibility).
    """
    if sim_bar is None:
        sim_bar = recommended_bar()
    rw = rewriter if rewriter is not None else get_rewriter()
    if rw is None:
        return {
            "error": "no rewriter configured — install .[api] and set ANTHROPIC_API_KEY or "
            "OPENAI_API_KEY, or use the /untell Claude skill (Claude is the rewriter).",
            "final": text,
        }

    if scrub:  # strip any hidden watermark / zero-width / homoglyph chars before we start
        from untell.attacks import scrub_hidden

        text = scrub_hidden(text)

    masked, mapping = lock(text)

    sites = [s.strip() for s in browser.split(",")] if isinstance(browser, str) else (browser or [])
    sites = [s for s in sites if s]
    browser_score = _browser_scorer(sites, mapping, threshold) if sites else None
    if sites and browser_score is None:
        return {
            "error": f"no browser checker available from {sites} — pip install .[browser] && playwright install chromium",
            "final": text,
        }

    def score(masked_text: str) -> dict:
        if browser_score is not None:
            return browser_score(masked_text)
        return score_text(masked_text, tier=tier, threshold=threshold)

    def _passed(s: dict) -> bool:
        # Comfortable pass: below threshold by the safety margin (headroom vs detector noise).
        return s["max"] < threshold - margin

    pre = score(masked)
    best_masked, best_score = masked, pre
    iters = 0
    rewrites = 0
    stopped = "max_iters"
    for i in range(1, max_iters + 1):
        iters = i
        if _passed(best_score) and similarity(masked, best_masked) >= sim_bar:
            stopped = "passed"
            break
        # Targeted feedback: name the specific sentences that read as AI (cheap lite scoring), so the
        # rewriter fixes only those instead of re-rolling the whole text (fewer iters, less drift).
        try:
            from untell.scripts.sentences import score_sentences

            best_score = {
                **best_score,
                "flagged_sentences": score_sentences(best_masked, tier="lite", threshold=threshold)["flagged"],
                "style": style,
            }
        except Exception:
            pass
        try:
            candidate = rw.rewrite(best_masked, best_score, threshold)
        except Exception as exc:  # surface the failure rather than silently looping
            return {"error": f"rewriter failed: {type(exc).__name__}: {str(exc)[:160]}", "final": restore(best_masked, mapping)}
        rewrites += 1
        cand_score = score(candidate)
        # Accept only if the rewrite (a) keeps EVERY sentinel intact — a dropped or altered sentinel
        # would silently lose a locked citation/number/fact on restore, defeating the whole lock —
        # (b) holds the meaning-similarity gate, and (c) does not worsen the detector max.
        if (
            find_sentinels(candidate) == set(mapping)
            and similarity(masked, candidate) >= sim_bar
            and cand_score["max"] <= best_score["max"]
        ):
            best_masked, best_score = candidate, cand_score
        if _passed(best_score):
            stopped = "passed"
            break

    # Reproducibility guard: re-score the winner a few times; detectors are noisy and a one-off pass
    # can re-flag. Only keep "passed" if every confirmation pass also clears.
    if stopped == "passed" and confirm > 0:
        for _ in range(confirm):
            rescore = score(best_masked)
            if rescore["max"] >= threshold - margin:  # same headroom as the pass test (_passed)
                best_score = rescore
                stopped = "passed_unconfirmed"
                break

    # Optional cheap CPU polish: surgical word-importance substitution to shave a bit more signal.
    if polish:
        try:
            from untell.attacks import surgical_substitute

            polished = surgical_substitute(best_masked, tier="lite", threshold=threshold)["text"]
            polished_score = score(polished)
            # Polish must clear the same gates as a rewrite: sentinels intact, meaning preserved,
            # detector max not worse. (Reuse polished_score; don't re-score and risk detector noise.)
            if (
                find_sentinels(polished) == set(mapping)
                and similarity(masked, polished) >= sim_bar
                and polished_score["max"] <= best_score["max"]
            ):
                best_masked, best_score = polished, polished_score
        except Exception:
            pass

    final = restore(best_masked, mapping)
    return {
        "final": final,
        "iterations": iters,
        "rewrites": rewrites,
        "pre": pre,
        "post": best_score,
        "similarity": similarity(masked, best_masked),
        "tier": best_score.get("tier", tier),
        "sim_bar": sim_bar,
        "quality_metric": method(),
        "flagged": best_score["flagged"],
        "stopped": stopped,
    }


def _render(result: dict) -> str:
    if "error" in result:
        return f"ERROR: {result['error']}"
    pre, post = result["pre"], result["post"]
    lines = ["# untell result", ""]
    lines.append(f"tier={result['tier']}  iterations={result['iterations']}  stopped={result['stopped']}")
    lines.append(f"max P(AI): {pre['max']:.3f} -> {post['max']:.3f}  (threshold {post['threshold']})")
    lines.append(f"similarity: {result['similarity']:.3f} (bar {result['sim_bar']}, {result['quality_metric']})")
    lines.append("\nper-detector (pre -> post):")
    for name in pre.get("detectors", {}):
        if "__error" in name:
            continue
        p = pre["detectors"].get(name)
        q = post["detectors"].get(name)
        if isinstance(p, (int, float)) and isinstance(q, (int, float)):
            lines.append(f"  {name}: {p:.3f} -> {q:.3f}")
    lines.append("\n--- humanized text ---\n" + result["final"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()  # UTF-8 stdin/stdout/stderr (Windows defaults to cp1252)
    from untell._env import load_env

    load_env()  # pick up ANTHROPIC_API_KEY / commercial keys from a .env file if present
    parser = argparse.ArgumentParser(prog="untell-loop", description="Run the headless untell loop.")
    parser.add_argument("text", nargs="?", help="text to untell (or --file / stdin)")
    parser.add_argument("--file", "-f", help="read text from this file")
    parser.add_argument("--tier", default="full", choices=["lite", "full", "heavy", "commercial"])
    parser.add_argument("--threshold", "-t", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--max-iters", type=int, default=5)
    parser.add_argument(
        "--browser",
        help="score each iteration against free web detector(s) instead of local proxies — "
        "comma-separated (e.g. 'zerogpt,detecting-ai'); the loop must beat the MAX across all. "
        "Real checkers, no key, but slow (~10s each/iter). Needs .[browser] + playwright.",
    )
    parser.add_argument(
        "--margin",
        type=float,
        default=0.0,
        help="safety headroom: only stop when max score < threshold - margin (e.g. 0.10), so a "
        "borderline pass a noisy detector might re-flag keeps iterating. Default 0.",
    )
    parser.add_argument(
        "--confirm",
        type=int,
        default=0,
        help="after a pass, re-score the result N more times; keep 'passed' only if every re-scan "
        "still clears (guards against a noisy detector re-flagging). Default 0.",
    )
    parser.add_argument("--no-scrub", action="store_true", help="skip stripping hidden watermark/unicode chars from input")
    parser.add_argument("--polish", action="store_true", help="add a cheap surgical word-substitution polish pass at the end")
    parser.add_argument(
        "--style",
        choices=["casual", "professional", "academic", "blunt", "storytelling", "journalistic"],
        help="bias the rewrite toward a writing style/voice",
    )
    parser.add_argument("--json", action="store_true", help="emit the full result as JSON")
    args = parser.parse_args(argv)

    if args.file:
        from untell.scripts.io_utils import read_file

        text = read_file(args.file)  # .txt / .docx / .pdf
    elif args.text:
        text = args.text
    else:
        text = sys.stdin.read()
    if not text.strip():
        print(json.dumps({"error": "empty input"}))
        return 2

    result = untell_text(
        text,
        tier=args.tier,
        threshold=args.threshold,
        max_iters=args.max_iters,
        browser=args.browser,
        margin=args.margin,
        confirm=args.confirm,
        scrub=not args.no_scrub,
        polish=args.polish,
        style=args.style,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        print(_render(result))
    return 1 if "error" in result else 0


if __name__ == "__main__":
    raise SystemExit(main())
