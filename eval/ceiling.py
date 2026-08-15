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
from pathlib import Path

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

logger = logging.getLogger(__name__)

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


def _score_one(args: tuple) -> tuple:
    """Score + loop ONE text. Module-level so it is picklable by ProcessPoolExecutor.

    The rewriter is passed by NAME, not as an object: rewriter instances hold loaded models and are
    not picklable, and each worker has to build its own anyway.
    """
    text, tier, threshold, max_iters, rewriter_name, best_of, seed = args
    import os

    # Each worker gets its own torch. Without capping threads, N workers each spawn a full thread
    # pool and oversubscribe the box, which is slower than running serially.
    os.environ.setdefault("OMP_NUM_THREADS", "2")
    os.environ.setdefault("MKL_NUM_THREADS", "2")
    try:
        import torch

        torch.set_num_threads(2)
    except Exception:
        pass

    from untell.rewriter import get_rewriter

    rw = get_rewriter(prefer=rewriter_name) if rewriter_name else None
    pre = score_text(text, tier=tier, threshold=threshold)
    res = untell_text(
        text, tier=tier, threshold=threshold, max_iters=max_iters, rewriter=rw, best_of=best_of,
        seed=seed,
    )
    return text, pre, res


def _each_text(texts, tier, threshold, max_iters, rewriter, best_of, workers, seed=None):
    """Yield (text, pre_score, loop_result) per text, in parallel when asked and possible.

    MEASURED, and the answer depends entirely on how expensive one text is. Each worker re-imports
    the stack and loads its own detector copies, which costs ~15-20s before it does any work:

        stdlib lite, n=8, max_iters=2   workers 1 -> 16.6s   4 -> 20.0s   8 -> 24.7s   (SLOWER)
        full tier,   n=4, max_iters=1   workers 1 -> 85.7s   4 -> 47.7s               (1.8x)

    So the default is 1. Parallelism is for the case this was written for — full-tier runs on real
    text, where a single text costs 250s with `composite` and 950s with `neural` at max_iters=5 and
    startup is noise. At those sizes the speedup approaches the worker count; at lite-tier sizes it
    is pure overhead.

    Falls back to the serial path whenever parallelism cannot be used, so behaviour is identical
    and only the wall-clock changes:
      - workers <= 1, or a single text (nothing to gain);
      - the rewriter was passed as an OBJECT rather than a name (it holds models and cannot be
        pickled — the CLI passes a name, library callers may not);
      - the pool fails to start at all (frozen interpreters, restricted sandboxes).
    """
    name = rewriter if isinstance(rewriter, str) else getattr(rewriter, "name", None)
    parallel_ok = workers and workers > 1 and len(texts) > 1 and (rewriter is None or name)
    if parallel_ok:
        try:
            from concurrent.futures import ProcessPoolExecutor

            payload = [(t, tier, threshold, max_iters, name, best_of, seed) for t in texts]
            with ProcessPoolExecutor(max_workers=min(workers, len(texts))) as pool:
                # `map` preserves input order, so aggregation stays deterministic.
                yield from pool.map(_score_one, payload)
            return
        except Exception as exc:  # noqa: BLE001 — any pool failure must degrade, never abort a run
            logger.warning(
                "parallel ceiling run failed (%s: %s); falling back to serial",
                type(exc).__name__, str(exc)[:80],
            )

    for t in texts:
        pre = score_text(t, tier=tier, threshold=threshold)
        res = untell_text(
            t, tier=tier, threshold=threshold, max_iters=max_iters, rewriter=rewriter,
            best_of=best_of, seed=seed,
        )
        yield t, pre, res


def measure_ceiling(
    texts: list[str] | None = None,
    tier: str = "full",
    threshold: float = DEFAULT_THRESHOLD,
    max_iters: int = 5,
    rewriter=None,
    best_of: int = 1,
    repeats: int = 1,
    corpus: str = "builtin",
    workers: int = 1,
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

    # Texts are INDEPENDENT — each one is scored, looped and re-scored with no shared state — so
    # this loop was leaving a whole machine idle. It ran strictly serially, which is the real reason
    # every real-text ceiling figure in this repo is n=6: not that samples are scarce (HC3 yields
    # 2000+ pairs on request) but that one text costs ~250s with `composite` and ~950s with
    # `neural` at max_iters=5, so n=6 was already an hour and a half.
    #
    # `workers` fans the per-text work out across processes. Each worker re-imports torch and loads
    # its own detector copies, so memory is the binding constraint rather than cores; the default is
    # deliberately conservative and the env var exists to tune it per machine.
    for _run in range(max(1, repeats)):
        run_posts: list[float] = []
        # A DIFFERENT seed per repeat, or `repeats` measures nothing.
        #
        # `untell_text` seeds its RNG from the input text, so every repeat of the same corpus was
        # byte-identical and `post_mean_max_stdev` came back 0.0 — MEASURED at repeats=3: means
        # [0.2458, 0.2458, 0.2458]. That zero reads as "this number has no uncertainty", which is
        # the opposite of what this option exists to report, and it would have hidden the very
        # spread the docstring above quotes (0.080 vs 0.144 across two runs).
        #
        # `_run` as the seed keeps both properties at once: repeat i differs from repeat j, and
        # repeat i is the same on every invocation, so a published figure can be re-derived.
        for _source, pre, res in _each_text(
            texts, tier, threshold, max_iters, rewriter, best_of, workers, seed=_run
        ):
            # An unscored result carries max: 0.0 as a placeholder, and flagged_rate below counts
            # `s >= threshold` — so a dead detector stack would report a 0% post-flagged rate, i.e.
            # "we beat every detector", as the headline ceiling number. Exclude, don't count.
            if pre.get("scored") is False:
                unscored += 1
            else:
                pre_max.append(pre["max"])
                for k, v in _numeric(pre).items():
                    per_pre.setdefault(k, []).append(v)

            if "error" not in res and "post" in res:
                post = res["post"]
                if post.get("scored") is not False:
                    post_max.append(post["max"])
                    run_posts.append(post["max"])
                    for k, v in _numeric(post).items():
                        per_post.setdefault(k, []).append(v)
                # Count a REWRITE, not a run. This was `rewrote += 1` on every result that carried a
                # `post`, which is every result that did not error — so it counted loop invocations
                # and happened to be right only because the "no rewriter configured" error path
                # returned no `post` at all. Once that path became a fallback to `composite`, a
                # `max_iters=0` baseline started reporting `rewriter_available: True`.
                #
                # `rewrites` is the loop's own count of candidate rewrites drawn. The text check is
                # the fallback for a stubbed loop — tests replace `untell_text` wholesale and their
                # doubles do not carry every key — and it is the more direct evidence anyway: the
                # output differs from the input, so something rewrote it.
                if res.get("rewrites") or res.get("final", _source) != _source:
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
        # WHICH rewriter, for exactly the same reason as `corpus` above, and the omission cost the
        # same kind of mistake. The repo's headline real-text figure — "0.999 -> 0.860, flagged
        # 1.00, hc3_roberta barely moves" — was recorded without naming the rewriter that produced
        # it, and was then read as a property of the free TIER. It is not. Same corpus, same
        # command, same settings, only `--rewriter` changed:
        #     composite   0.999 -> 0.860   flagged 1.00   hc3_roberta 0.810
        #     neural      0.999 -> 0.502   flagged 0.50   hc3_roberta 0.407
        # `rewriter_available` below records only THAT one ran, never which. Prefer the object's
        # own `name` over the caller's string so an alias is recorded as what actually ran: "max"
        # and "ensemble" both build the same EnsembleRewriter.
        "rewriter": getattr(rewriter, "name", None) or (rewriter if isinstance(rewriter, str) else None),
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


# A detector that does not move drags the headline with it, because the headline is a MAX.
#
# MEASURED on HC3, composite, best-of 3, 3 repeats:
#
#     hc3_roberta              0.9992 -> 0.9992      moved by nothing
#     roberta_openai           0.9986 -> 0.6228      moved by 0.376
#     fast_detectgpt           0.6563 -> 0.4782
#     perplexity_burstiness    0.6059 -> 0.5679
#
#     headline: post flagged rate 1.0, mean max P(AI) 0.9997 -> 0.9994
#
# Three detectors improved substantially and the report said the tool achieved nothing, because
# `max` is whichever detector is highest and that one never budged. `hc3_roberta` is fine-tuned ON
# HC3, so against HC3 it is in-distribution: human mean 0.0796, AI mean 0.9992, and the ENTIRE
# spread across 15 AI documents is 1.2e-05. It discriminates perfectly and has no dynamic range
# left to give — on RAID, which it never trained on, the same detector runs 0.0018 human against
# 0.6953 AI and moves freely.
#
# Not literally constant, which matters: read at four decimals it looks pinned at exactly 0.9992
# and the first reading here said "constant". Full precision shows 14 distinct values in 15. The
# practical consequence is the same, since the loop threshold is 0.30 and the spread is a
# hundred-thousandth, but "effectively saturated" and "returns a constant" are different claims and
# only one of them is true.
#
# So the report says it. A reader comparing 0.9997 to 0.9994 should not have to derive from the
# per-detector table that the number is pinned by one member.
_PINNED_DELTA = 0.01


def _pinned_note(r: dict) -> list[str]:
    """Name any detector that held the max still while others moved."""
    pre, post = r.get("per_detector_pre") or {}, r.get("per_detector_post") or {}
    if not post:
        return []
    deltas = {k: pre[k] - post[k] for k in pre if isinstance(post.get(k), (int, float))}
    if not deltas:
        return []
    top = max(pre, key=lambda k: pre[k])
    if deltas.get(top, 0.0) >= _PINNED_DELTA:
        return []
    movers = [k for k, d in deltas.items() if d > _PINNED_DELTA]
    if not movers:
        return []
    best = max(movers, key=lambda k: deltas[k])
    return [
        "",
        f"  NOTE: the max is pinned by {top} ({pre[top]} -> {post[top]}), which barely moved, while "
        f"{len(movers)} detector(s) did — {best} by {deltas[best]:.3f}.",
        "        A headline built on max cannot show that. Read the per-detector rows above before "
        "concluding the loop achieved nothing.",
    ]


def _code_state() -> str:
    """The commit this run measured, for the header.

    A published number from this script carried the COMMAND that produced it and nothing about the
    code that ran. That was enough until it wasn't: the README's composite column
    (0.778, hc3_roberta 0.710) stopped reproducing when `structural.py`'s draws were seeded, and the
    command in the docs beside it still reads exactly the same. Nothing in the figure said which
    build it came from, so the drift was invisible until someone re-ran it by hand.

    The audit already enforces that every measured number states a source, and accepts "MEASURED",
    "n=6" or "Result 12" — none of which pins a build. A randomized rewriter's output number needs
    one. Cheaper to stamp it here, on every run, than to police the prose afterwards.

    Degrades to "unknown" outside a checkout: a number from a pip install is still a number, and a
    report that crashed for want of git would be a worse trade than a missing field.
    """
    import subprocess

    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            dirty = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=Path(__file__).resolve().parent.parent,
                capture_output=True, text=True, timeout=10,
            )
            suffix = "+dirty" if dirty.returncode == 0 and dirty.stdout.strip() else ""
            return out.stdout.strip() + suffix
    except Exception:  # a provenance stamp must never break the measurement it labels
        pass
    return "unknown"


def _render(r: dict) -> str:
    lines = [
        f"untell inference-only ceiling — tier={r['tier']} threshold={r['threshold']} "
        f"best_of={r['best_of']} n={r['n']} rewriter={r.get('rewriter') or 'unknown'} "
        f"corpus={r.get('corpus', 'builtin')} ({r.get('corpus_mean_words')} words avg) "
        f"commit={r.get('commit') or _code_state()}",
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
        lines.extend(_pinned_note(r))
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


def build_parser() -> argparse.ArgumentParser:
    """The `untell-ceiling` argument parser.

    Split out of ``main`` so its vocabularies can be read without running the command — the tier
    and rewriter lists are restated here and pinned against the loader's table and
    ``api_server._FREE_REWRITERS`` by tests/test_surface_parity.py.
    """
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
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="run N texts in parallel (each worker loads its own detector copies, so memory is "
        "the limit, not cores). Texts are independent; the default 1 is the old serial path. "
        "This is what made n=6 the practical ceiling for full-tier real-text runs.",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def _validate(ns: argparse.Namespace, parser: argparse.ArgumentParser) -> argparse.Namespace:
    """Reject out-of-range numeric args before a measurement starts.

    Every other CLI (untell/score/loop/verify) rejects out-of-range numeric args at parse.
    This one shipped without checks: MEASURED --n 0 silently ran the default 3-sample
    builtin (exit 0), --threshold 2.5 ran with a threshold where nothing can ever flag
    (pre_flagged_rate 0.0), --repeats 0/-1 and --best-of 0 all silently ran a measurement.
    A number quoted from such a run would be produced by a degenerate configuration.
    Reject here so the measurements engine cannot be asked to measure with nonsense.
    """
    if ns.n <= 0:
        parser.error(f"--n must be >= 1, got {ns.n}")
    if ns.repeats <= 0:
        parser.error(f"--repeats must be >= 1 (the help says use >=3 before quoting a number), got {ns.repeats}")
    if ns.max_iters <= 0:
        parser.error(f"--max-iters must be >= 1, got {ns.max_iters}")
    if ns.best_of <= 0:
        parser.error(f"--best-of must be >= 1, got {ns.best_of}")
    if ns.workers <= 0:
        parser.error(f"--workers must be >= 1, got {ns.workers}")
    if not 0.0 <= ns.threshold <= 1.0:
        parser.error(f"--threshold must be in [0, 1], got {ns.threshold}")
    return ns


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()
    args = _validate(build_parser().parse_args(argv), build_parser())

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
        workers=args.workers,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2) if args.json else _render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
