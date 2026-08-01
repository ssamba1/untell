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
import logging
import sys
from collections import Counter

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
from untell.scripts.preserve import _SENTINEL_RE, lock, restore
from untell.scripts.quality import method, recommended_bar, similarity
from untell.scripts.score import DEFAULT_THRESHOLD, score_text
from untell.scripts.tells import score_tells

# Detector-score noise band. Among best-of-N candidates whose detector max is within this of each
# other, prefer the one with FEWER AI tells — a strictly more human-reading rewrite at no cost to
# evasion. Detectors anti-correlate with human-ness on some text, so tells are the better tie-breaker.
_TELLS_EPS = 0.02


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
        out = {
            "tier": label,
            "detectors": scores,
            "max": round(mx, 4),
            "mean": round(sum(numeric) / len(numeric), 4) if numeric else 0.5,
            "threshold": threshold,
            "flagged": mx >= threshold,
        }
        if not numeric:  # every checker errored this round — 0.5 is a placeholder, not a real signal
            out["all_checkers_failed"] = True
        return out

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
    best_of: int = 1,
    detector_thresholds: dict[str, float] | None = None,
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
            "error": "no rewriter configured — run with --rewriter composite (free, $0, no key), or "
            "set ANTHROPIC_API_KEY / OPENAI_API_KEY / UNTELL_POLICY_DIR",
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
        # Per-detector gate (optional): every named detector must be below its own threshold.
        # Different detectors calibrate differently, so a single global max is a blunt instrument;
        # `detector_thresholds` lets a caller require e.g. mage<0.40 AND roberta_openai<0.25.
        if detector_thresholds:
            dets = s.get("detectors", {})
            for name, t in detector_thresholds.items():
                v = dets.get(name)
                if isinstance(v, (int, float)) and v >= t:
                    return False
        # Never declare a pass on a vacuous score: if EVERY detector errored this round there is no
        # real signal, and ``max`` is a placeholder (0.5 in browser mode, whatever the ensemble
        # defaulted to locally). Treating that as "passed" would ship un-scored text as clean.
        if s.get("all_checkers_failed"):
            return False
        dets = s.get("detectors", {})
        has_signal = any(
            isinstance(v, (int, float)) for k, v in dets.items() if not str(k).endswith("__error")
        )
        if not has_signal:
            return False
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
        # Best-of-N: draw `best_of` candidates this round and keep the strongest VALID one. A
        # candidate is valid only if it (a) keeps EVERY sentinel intact — a dropped/altered sentinel
        # would silently lose a locked citation/number on restore, defeating the whole lock — and
        # (b) holds the meaning-similarity gate. Among the valid ones, pick the lowest detector max,
        # and only adopt it if it does not worsen the running best.
        prev_masked = best_masked  # to detect a stalled (no-op) iteration below
        cand_best, cand_best_score, cand_best_tells = None, None, None
        drew = 0
        for _ in range(max(1, best_of)):
            try:
                candidate = rw.rewrite(best_masked, best_score, threshold)
            except Exception as exc:  # surface the failure rather than silently looping
                if drew == 0:
                    return {"error": f"rewriter failed: {type(exc).__name__}: {str(exc)[:160]}", "final": restore(best_masked, mapping)}
                break  # a later draw failed; use the candidates we already have
            drew += 1
            rewrites += 1
            # Multiset compare against the masked source's own sentinels — NOT Counter(mapping), whose
            # dict values ("Smith (2020)", "47") would be read as counts. A valid rewrite reproduces
            # every sentinel exactly as often as it appears in `masked`: no drop, no alter, no dup.
            if Counter(_SENTINEL_RE.findall(candidate)) != Counter(_SENTINEL_RE.findall(masked)):
                continue  # dropped/altered/DUPLICATED a locked span — reject outright
            cscore = score(candidate)
            if similarity(masked, candidate) >= sim_bar:
                # Primary objective: lowest detector max. Secondary (within the noise band): fewer
                # AI tells, so a near-tie is resolved toward the more human-reading candidate.
                cand_tells = score_tells(candidate).get("tells", 0)
                if cand_best_score is None:
                    cand_best, cand_best_score, cand_best_tells = candidate, cscore, cand_tells
                else:
                    delta = cscore["max"] - cand_best_score["max"]
                    if delta < -_TELLS_EPS or (
                        abs(delta) <= _TELLS_EPS and cand_tells < cand_best_tells
                    ):
                        cand_best, cand_best_score, cand_best_tells = candidate, cscore, cand_tells
        if cand_best is not None and cand_best_score["max"] <= best_score["max"]:
            best_masked, best_score = cand_best, cand_best_score
        if _passed(best_score):
            stopped = "passed"
            break
        # A deterministic rewriter (e.g. surgical word-substitution) fed identical input produces
        # identical output, so once an iteration leaves the working text unchanged, every remaining
        # iteration is a guaranteed no-op. Stop instead of re-running the (often expensive) rewrite
        # for the rest of max_iters. Stochastic rewriters (LLM/policy) have no such flag and keep going.
        if getattr(rw, "deterministic", False) and best_masked == prev_masked:
            stopped = "stalled"
            break

    # Restore sentinels to get the final human-readable text before any confirm/polish/return.
    final = restore(best_masked, mapping)

    # Reproducibility guard: re-score the winner a few times on the FINAL (restored) text;
    # detectors are noisy and a one-off pass on masked text can re-flag once sentinels are
    # replaced by the real citations/numbers/URLs the detector might key on.
    if stopped == "passed" and confirm > 0:
        for _ in range(confirm):
            rescore = score(final)
            if rescore["max"] >= threshold - margin:
                best_score = rescore
                stopped = "passed_unconfirmed"
                break

    # Optional cheap CPU polish: surgical word-importance substitution to shave a bit more signal.
    polished_applied = False
    if polish:
        try:
            from untell.attacks import surgical_substitute

            # Optimize against the SAME signal the loop scored against (so the swaps target the real
            # objective), except in browser mode whose composite tier isn't directly scoreable -> lite.
            polish_tier = "lite" if browser_score is not None else tier
            polished = surgical_substitute(final, tier=polish_tier, threshold=threshold)["text"]
            polished_score = score(polished)
            # Polish on the restored (final) text: verify meaning preserved (vs the original masked
            # text) and score not worse. Sentinel check is irrelevant — text is already restored.
            if (
                polished_score["max"] <= best_score["max"]
                and similarity(text, polished) >= sim_bar
            ):
                final, best_score = polished, polished_score
                polished_applied = True
        except Exception:
            pass

    return {
        "final": final,
        "iterations": iters,
        "rewrites": rewrites,
        "pre": pre,
        "post": best_score,
        # Report meaning-preservation vs the true final output. Pre-polish, ``best_masked`` restores to
        # ``final`` so the locked-text similarity is exact; polish rewrites the restored text (sentinels
        # already gone), so compare the scrubbed original against the actual final instead of stale.
        "similarity": similarity(text, final) if polished_applied else similarity(masked, best_masked),
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
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()
    parser = argparse.ArgumentParser(prog="untell-loop", description="Run the headless untell loop.")
    parser.add_argument("text", nargs="?", help="text to untell (or --file / stdin)")
    parser.add_argument("--file", "-f", help="read text from this file")
    parser.add_argument("--tier", default="full", choices=["lite", "full", "heavy", "commercial"])
    parser.add_argument("--threshold", "-t", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--max-iters", type=int, default=5)
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=None,
        help="alias for --max-iters (rounds of rewrite). Overrides --max-iters when set.",
    )
    parser.add_argument(
        "--detector-thresholds",
        default=None,
        help='per-detector pass gate as a JSON object, e.g. \'{"mage":0.40,"roberta_openai":0.25}\'. '
        "Every named detector must fall below its own threshold to declare a pass (in addition to "
        "the global --threshold). Lets you hold the hardest detectors to a stricter bar.",
    )
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
    parser.add_argument(
        "--rewriter",
        choices=[
            "auto", "surgical", "structural", "composite", "neural", "ensemble", "max",
            "t5_paraphrase", "mt_pivot", "base",
        ],
        default="composite",
        help="'composite' = structural + surgical chained ($0, best free path, DEFAULT); "
        "'ensemble'/'max' = run composite + mt_pivot + neural and keep the per-input detector-lowest "
        "(strongest free path; >= any single method; needs .[full] for the neural/mt members); "
        "'neural' = T5 paraphrase + structural + surgical (needs .[full]; "
        "moves detectors far more than rule-based alone; falls back to composite without the deps); "
        "'structural' = sentence-level transforms ($0); "
        "'surgical' = word-substitution rewriter ($0); "
        "'t5_paraphrase' = free neural paraphraser alone (needs .[full]); "
        "'mt_pivot' = round-trip machine translation (needs .[full]; best on watermarked input); "
        "'base' = untuned base model, no LoRA adapter (A/B baseline; needs .[full] + UNTELL_POLICY_BASE); "
        "'auto' = hosted-LLM / local-policy rewriter (needs a key or UNTELL_POLICY_DIR).",
    )
    parser.add_argument("--no-scrub", action="store_true", help="skip stripping hidden watermark/unicode chars from input")
    parser.add_argument("--polish", action="store_true", help="add a cheap surgical word-substitution polish pass at the end")
    parser.add_argument(
        "--style",
        choices=["casual", "professional", "academic", "blunt", "storytelling", "journalistic",
                 "technical", "persuasive", "empathetic", "humorous", "poetic",
                 "instructional", "conversational", "minimalist"],
        help="bias the rewrite toward a writing style/voice (14 modes)",
    )
    parser.add_argument(
        "--best-of",
        type=int,
        default=1,
        help="draw N candidate rewrites per iteration and keep the best valid one (sentinels intact + "
        "meaning gate, lowest detector max). Default 1.",
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

    rewriter = None
    if args.rewriter in (
        "surgical", "structural", "composite", "neural", "ensemble", "max", "t5_paraphrase", "mt_pivot"
    ):
        from untell.rewriter import get_rewriter

        rewriter = get_rewriter(prefer=args.rewriter)
        if rewriter is None:
            print(
                f"ERROR: --rewriter {args.rewriter} is unavailable — it needs the '.[full]' extra "
                "(pip install -e '.[full]'). Try --rewriter composite for the zero-dependency path."
            )
            return 1
    elif args.rewriter == "base":
        from untell.rewriter.local_policy import LocalPolicyRewriter

        rewriter = LocalPolicyRewriter(use_adapter=False)
        if not rewriter.available():
            print(
                "ERROR: --rewriter base needs torch + transformers (pip install -e '.[full]'); "
                "set UNTELL_POLICY_BASE to a HF model id to override the default base."
            )
            return 1

    detector_thresholds = None
    if args.detector_thresholds:
        try:
            detector_thresholds = {k: float(v) for k, v in json.loads(args.detector_thresholds).items()}
        except (ValueError, AttributeError) as exc:
            print(f"ERROR: --detector-thresholds must be a JSON object of name:number pairs ({exc}).")
            return 2

    result = untell_text(
        text,
        tier=args.tier,
        threshold=args.threshold,
        max_iters=args.max_rounds if args.max_rounds is not None else args.max_iters,
        rewriter=rewriter,
        browser=args.browser,
        margin=args.margin,
        confirm=args.confirm,
        scrub=not args.no_scrub,
        polish=args.polish,
        style=args.style,
        best_of=args.best_of,
        detector_thresholds=detector_thresholds,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    elif "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        # Rich output when available, otherwise the standard render
        try:
            from untell.rich_output import print_humanize_result

            print_humanize_result(
                original=text,
                final=result.get("final", ""),
                pre_score=result.get("pre", {}),
                post_score=result.get("post", {}),
                iterations=result.get("iterations", 0),
                stopped=result.get("stopped", "unknown"),
            )
        except Exception:
            print(_render(result))
    return 1 if "error" in result else 0


if __name__ == "__main__":
    raise SystemExit(main())
