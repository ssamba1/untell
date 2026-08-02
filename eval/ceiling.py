"""Measure untell's inference-only evasion ceiling against the LOCAL detector ensemble.

The literature has no data point for what the training-free closed loop actually achieves: only the
~1% one-shot-style floor and the ~97% RL-trained ceiling (see docs/free-ceiling-report.md). This
script produces that missing number. It scores a corpus of AI text, runs the untell loop on each,
and reports the before/after flagged rate plus per-detector mean P(AI).

Without a rewriter configured it reports the BASELINE (pre-rewrite detection) only, which is always
runnable and still useful. With a rewriter (an API key, or one passed to ``measure_ceiling``) it
reports the full before/after delta — the actual inference-only ceiling on the local tier.

    untell-ceiling                       # built-in sample, baseline (or full delta if a key is set)
    untell-ceiling --dataset hc3 --n 12  # real ChatGPT answers — the number that generalises
    untell-ceiling --file corpus.txt     # paragraphs separated by blank lines
    untell-ceiling --tier full --best-of 3 --json

The default corpus is three HAND-WRITTEN paragraphs, and it is measurably easier than real AI
output: it starts at mean max P(AI) 0.859 where actual ChatGPT answers start at 0.998. At identical
length the loop lands at 0.234 on it and clears every sample, against 0.628 with half still flagged
on HC3. That gap is the corpus, not the length. Quote a number from ``--dataset hc3``; the built-in
sample demonstrates the mechanics.
"""

from __future__ import annotations

import argparse
import json
import logging

# Run-as-file support: put the package parent on sys.path when executed directly.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

from untell.scripts.run import untell_text
from untell.scripts.score import DEFAULT_THRESHOLD, score_text

# A few formulaic AI paragraphs (no locked facts needed; this measures detector movement).
#
# HAND-WRITTEN, and measurably EASIER than real AI output. They were composed to read as AI, and
# they do — but they start at mean max P(AI) 0.859, where actual ChatGPT answers start at 0.998.
# Measured on 6 HC3 pairs at tier=full, best_of=3, max_iters=5, with length held constant:
#
#     corpus                          words   pre     post    still flagged
#     built-in sample                 37      0.859   0.234   0%
#     HC3 ChatGPT answers, cut to 36w 36      0.998   0.628   50%
#     HC3 ChatGPT answers, full       186     0.999   0.762   83%
#
# So the gap is the CORPUS, not the length: at identical length the built-in sample lands three
# times lower and clears every sample. Any number measured on it is a demo of the loop's mechanics,
# not the ceiling against real AI text — use --dataset hc3 for that. The warning in _render says so
# on every run that uses this default.
_SAMPLE = [
    "Furthermore, artificial intelligence has fundamentally transformed numerous industries in recent "
    "years. Moreover, organizations increasingly leverage these technologies to optimize operational "
    "efficiency and drive innovation. Overall, the transformative impact continues to expand across "
    "various sectors.",
    "In today's rapidly evolving digital landscape, cybersecurity has become paramount. It is important "
    "to note that organizations must navigate the complexities of an ever-changing threat environment. "
    "Ultimately, a robust and comprehensive security posture is essential for success.",
    "Climate change represents one of the most pressing challenges of our time. Notably, rising global "
    "temperatures underscore the urgent need for action. By fostering collaboration and harnessing "
    "innovative solutions, society can pave the way toward a more sustainable future.",
]


def _numeric(score: dict) -> dict:
    return {
        k: v
        for k, v in score.get("detectors", {}).items()
        if isinstance(v, (int, float)) and not k.endswith("__error")
    }


def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 4) if xs else None


def _stdev(xs: list[float]) -> float | None:
    """Population stdev; None for fewer than 2 samples."""
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return round((sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5, 4)


def measure_ceiling(
    texts: list[str] | None = None,
    tier: str = "full",
    threshold: float = DEFAULT_THRESHOLD,
    max_iters: int = 5,
    rewriter=None,
    best_of: int = 1,
    repeats: int = 1,
    corpus: str = "builtin",
) -> dict:
    """Score each text, run the loop, and aggregate the before/after detector movement.

    ``repeats`` re-runs the whole corpus N times. The free rewriters are RANDOMIZED (composite draws
    different seeds per attempt, the neural path samples), so a single pass is not reproducible
    evidence — measured, the same corpus moved a rewriter's mean max P(AI) from 0.080 to 0.144 across
    two runs. With ``repeats > 1`` the result carries ``post_mean_max_stdev`` and the per-run means,
    so a reported number can be read with its spread instead of being mistaken for a point estimate.
    """
    if texts is None:
        texts = list(_SAMPLE)
    run_post_means: list[float] = []
    sims: list[float] = []
    pre_max: list[float] = []
    post_max: list[float] = []
    per_pre: dict[str, list[float]] = {}
    per_post: dict[str, list[float]] = {}
    rewrote = 0
    unscored = 0

    for _run in range(max(1, repeats)):
        run_posts: list[float] = []
        for t in texts:
            pre = score_text(t, tier=tier, threshold=threshold)
            # An unscored result carries max: 0.0 as a placeholder, and flagged_rate below counts
            # `s >= threshold` — so a dead detector stack would report a 0% post-flagged rate, i.e.
            # "we beat every detector", as the headline ceiling number. Exclude, don't count.
            if pre.get("scored") is False:
                unscored += 1
            else:
                pre_max.append(pre["max"])
                for k, v in _numeric(pre).items():
                    per_pre.setdefault(k, []).append(v)

            res = untell_text(
                t, tier=tier, threshold=threshold, max_iters=max_iters, rewriter=rewriter,
                best_of=best_of,
            )
            if "error" not in res and "post" in res:
                post = res["post"]
                if post.get("scored") is not False:
                    post_max.append(post["max"])
                    run_posts.append(post["max"])
                    for k, v in _numeric(post).items():
                        per_post.setdefault(k, []).append(v)
                rewrote += 1
                # Evasion without meaning preservation is worthless — a rewrite that destroys the
                # text trivially "beats" every detector. Report it alongside, so a ceiling number
                # can never be read without the fidelity it cost.
                if isinstance(res.get("similarity"), (int, float)):
                    sims.append(float(res["similarity"]))
        if run_posts:
            run_post_means.append(round(sum(run_posts) / len(run_posts), 4))

    def flagged_rate(scores: list[float]) -> float | None:
        return round(sum(1 for s in scores if s >= threshold) / len(scores), 4) if scores else None

    return {
        "n": len(texts),
        # WHICH texts. A ceiling is a property of the corpus as much as of the loop — the built-in
        # sample starts at 0.859 and real ChatGPT answers start at 0.998 — and the result carried no
        # record of which one produced it, so two very different numbers were indistinguishable
        # once written down.
        "corpus": corpus,
        "corpus_mean_words": round(sum(len(t.split()) for t in texts) / len(texts), 1) if texts else None,
        "tier": tier,
        "threshold": threshold,
        "max_iters": max_iters,
        "best_of": best_of,
        "repeats": max(1, repeats),
        "run_post_means": run_post_means or None,
        "post_mean_max_stdev": _stdev(run_post_means),
        "rewrote": rewrote,
        "mean_similarity": _mean(sims),
        "min_similarity": round(min(sims), 4) if sims else None,
        "rewriter_available": rewrote > 0,
        "unscored": unscored,
        "pre_flagged_rate": flagged_rate(pre_max),
        "post_flagged_rate": flagged_rate(post_max),
        "pre_mean_max": _mean(pre_max),
        "post_mean_max": _mean(post_max),
        "per_detector_pre": {k: _mean(v) for k, v in per_pre.items()},
        "per_detector_post": {k: _mean(v) for k, v in per_post.items()} or None,
    }


def _render(r: dict) -> str:
    lines = [
        f"untell inference-only ceiling — tier={r['tier']} threshold={r['threshold']} "
        f"best_of={r['best_of']} n={r['n']} corpus={r.get('corpus', 'builtin')} "
        f"({r.get('corpus_mean_words')} words avg)",
        "",
        f"  pre  flagged rate: {r['pre_flagged_rate']}   mean max P(AI): {r['pre_mean_max']}",
    ]
    if r.get("corpus") == "builtin":
        # The default corpus is three HAND-WRITTEN paragraphs. They read as AI, but they start at
        # 0.859 where real ChatGPT answers start at 0.998, and at identical length the loop lands
        # three times lower on them and clears every sample. Printing the number without this makes
        # a demo look like a benchmark.
        lines.insert(
            1,
            "  NOTE: built-in sample = 3 hand-written paragraphs, measurably easier than real AI "
            "text (pre 0.86 vs 1.00). Use --dataset hc3 for the ceiling against real AI output.",
        )
    if r.get("unscored"):
        # Say which samples produced no signal at all. Silently excluding them would leave a
        # confident-looking ceiling computed from a fraction of the corpus.
        lines.insert(1, f"  WARNING: {r['unscored']}/{r['n']} samples scored by NO detector — excluded")
    if r["rewriter_available"]:
        # Denominator is n * repeats, i.e. the number of ATTEMPTS. `rewrote` accumulates across
        # every repeat while `n` is one run's corpus size, so `rewrote/n` printed "(rewrote 9/3)"
        # at --repeats 3 and "(rewrote 27/3)" at --repeats 9 — a success count larger than the
        # total it is measured against, on the line reporting the headline result.
        attempts = r["n"] * max(1, r.get("repeats", 1) or 1)
        lines.append(
            f"  post flagged rate: {r['post_flagged_rate']}   mean max P(AI): {r['post_mean_max']}   "
            f"(rewrote {r['rewrote']}/{attempts})"
        )
        if r.get("repeats", 1) > 1:
            # The free rewriters are randomized, so the spread across runs is the honest error bar.
            lines.append(
                f"  across {r['repeats']} runs: per-run mean max = {r['run_post_means']}   "
                f"stdev = {r['post_mean_max_stdev']}"
            )
        if r.get("mean_similarity") is not None:
            # A ceiling number is meaningless without the fidelity it cost.
            lines.append(
                f"  meaning preserved: mean similarity {r['mean_similarity']}   "
                f"worst {r['min_similarity']}"
            )
        lines.append("")
        lines.append("  per-detector mean P(AI)  before -> after:")
        for k, before in sorted(r["per_detector_pre"].items()):
            after = (r["per_detector_post"] or {}).get(k)
            lines.append(f"    {k:24} {before} -> {after}")
    else:
        lines.append("")
        lines.append(
            "  No rewriter configured (no ANTHROPIC_API_KEY / OPENAI_API_KEY, and not in the skill) "
            "— showing BASELINE detection only. Set a key, or run inside the /untell skill where "
            "Claude is the rewriter, to measure the after-rewrite ceiling."
        )
    return "\n".join(lines)


def _read_corpus(path: str) -> list[str]:
    with open(path, encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
    blocks = [b.strip() for b in raw.split("\n\n")]
    return [b for b in blocks if b]


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()
    parser = argparse.ArgumentParser(prog="untell-ceiling", description=__doc__)
    parser.add_argument("--file", "-f", help="corpus file (paragraphs separated by blank lines)")
    parser.add_argument(
        "--dataset",
        default="builtin",
        help="corpus of AI text to measure against: builtin (3 hand-written paragraphs — a demo, "
        "and measurably easier than real AI output), or hc3 / raid / mage for real generated text "
        "(needs .[eval]). --file overrides this.",
    )
    parser.add_argument(
        "--n", type=int, default=6, help="samples to draw from --dataset (ignored for builtin)"
    )
    parser.add_argument("--tier", default="full", choices=["lite", "full", "heavy", "commercial"])
    parser.add_argument("--threshold", "-t", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--max-iters", type=int, default=5)
    parser.add_argument("--best-of", type=int, default=1)
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="re-run the whole corpus N times and report the spread. The free rewriters are RANDOMIZED, "
        "so a single pass is not reproducible evidence — use >=3 before quoting a number.",
    )
    parser.add_argument(
        "--rewriter",
        choices=[
            "auto", "surgical", "structural", "composite", "targeted", "neural", "ensemble",
            "max", "t5_paraphrase", "mt_pivot",
        ],
        default="auto",
        help="'auto' uses a hosted-LLM rewriter if a key is set (else baseline only); every other "
        "choice is a FREE no-key backend so the loop runs at $0 — 'composite' (structural+surgical), "
        "'ensemble'/'max' (best of all free methods), 'neural' (T5 best-of-N; needs .[full]).",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from untell._env import load_env

    load_env()
    if args.file:
        texts, corpus = _read_corpus(args.file), f"file:{args.file}"
    elif args.dataset.lower() in ("builtin", "sample"):
        texts, corpus = list(_SAMPLE), "builtin"
    else:
        from eval.datasets import DatasetUnavailable, load_samples

        # strict=True: load_samples otherwise substitutes the built-in sample when `datasets` is
        # missing or the load fails, and reporting that as an hc3 ceiling would attach real-corpus
        # authority to the demo corpus — the exact confusion the `corpus` field exists to prevent.
        try:
            texts = load_samples(args.dataset, args.n, strict=True)
        except DatasetUnavailable as exc:
            print(f"ERROR: {exc}")
            return 1
        corpus = args.dataset.lower()
    if not texts:
        print(json.dumps({"error": "empty corpus"}))
        return 2
    rewriter = None
    if args.rewriter != "auto":
        from untell.rewriter import get_rewriter

        rewriter = get_rewriter(prefer=args.rewriter)
        if rewriter is None:
            print(
                f"ERROR: --rewriter {args.rewriter} is unavailable — it needs the '.[full]' extra "
                "(pip install -e '.[full]'). Try --rewriter composite for the zero-dependency path."
            )
            return 1
    result = measure_ceiling(
        texts,
        tier=args.tier,
        threshold=args.threshold,
        max_iters=args.max_iters,
        best_of=args.best_of,
        repeats=args.repeats,
        rewriter=rewriter,
        corpus=corpus,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2) if args.json else _render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
