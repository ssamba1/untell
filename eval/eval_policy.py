"""Offline A/B eval of the RL-trained LoRA policy.

Does single-pass rewriting with the trained policy actually lower P(AI) while preserving meaning — and
does it beat the *untuned* base model? Loads held-out AI samples, generates ONE rewrite per sample with
the policy (and, with ``--vs-base``, with the raw base model), scores both with the detector tier +
semantic similarity, and prints mean pre/post P(AI), bypass rate, and mean similarity.

    untell-eval-policy --policy out/rl-humanizer --n 25 --tier full --vs-base

Runs on CPU (slow) or GPU. The honest verdict is post P(AI) on a tier the policy did NOT optimize
against, at similarity >= 0.76. If you trained against the local ensemble, ``--tier full`` here is
circular — the real test is pasting a few rewrites into real GPTZero (this is the cheap offline proxy).
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics

logger = logging.getLogger(__name__)


def _eval(rw, samples: list[str], tier: str, threshold: float) -> list[dict]:
    from untell.scripts.quality import similarity
    from untell.scripts.score import score_text

    rows: list[dict] = []
    for i, s in enumerate(samples):
        pre_r = score_text(s, tier=tier)
        out = rw.rewrite(s, {"detectors": {}}, threshold=threshold)
        post_r = score_text(out, tier=tier)
        # Carry `scored` through. score_text returns max: 0.0 as a placeholder when no detector
        # produced a number, and dropping that flag here made a dead stack look like a perfect
        # policy: 0.0 -> 0.0 with a 100% bypass rate.
        rows.append(
            {
                "pre": float(pre_r["max"]),
                "post": float(post_r["max"]),
                "sim": similarity(s, out),
                "scored": pre_r.get("scored") is not False and post_r.get("scored") is not False,
            }
        )
        logger.info(
            "[%s] %d/%d  P(AI) %.2f -> %.2f%s",
            rw.name, i + 1, len(samples), rows[-1]["pre"], rows[-1]["post"],
            "" if rows[-1]["scored"] else "  (UNSCORED — no detector produced a number)",
        )
    return rows


def _summary(name: str, rows: list[dict], threshold: float) -> str:
    if not rows:
        return f"{name}: no rows"
    # Samples where nothing scored are excluded rather than counted as bypasses; see the same
    # guard in eval/report.py. Similarity is independent of the detector stack, so it keeps the
    # full denominator — the counts are spelled out below so the two are not confused.
    scored = [r for r in rows if r.get("scored") is not False]
    sim = statistics.mean(r["sim"] for r in rows)
    if not scored:
        return (
            f"{name:12s} NOT MEASURED — no detector scored any of {len(rows)} samples "
            f"(install the tier's models) | mean sim {sim:.3f}"
        )
    pre = statistics.mean(r["pre"] for r in scored)
    post = statistics.mean(r["post"] for r in scored)
    bypass = sum(1 for r in scored if r["post"] < threshold) / len(scored)
    unscored = len(rows) - len(scored)
    return (
        f"{name:12s} mean P(AI) {pre:.3f} -> {post:.3f} | bypass {bypass:.0%} "
        f"(<{threshold:.2f}) | mean sim {sim:.3f}"
        + (f" | {unscored}/{len(rows)} unscored, excluded" if unscored else "")
    )


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()
    p = argparse.ArgumentParser(prog="untell-eval-policy", description=__doc__)
    p.add_argument("--policy", help="adapter dir (default: $UNTELL_POLICY_DIR)")
    p.add_argument("--dataset", default="builtin", help="held-out source set (eval.datasets)")
    p.add_argument("--n", type=int, default=25)
    p.add_argument("--tier", default="full", help="detector tier to score against")
    p.add_argument(
        "--threshold", type=float, default=0.30,
        help="stop target handed to the rewriter, and the bar for counting a bypass (both)",
    )
    p.add_argument("--vs-base", action="store_true", help="also eval the untuned base model")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    from eval.datasets import load_samples
    from untell.rewriter.local_policy import LocalPolicyRewriter

    policy = LocalPolicyRewriter(adapter_dir=a.policy)
    if not policy.available():
        logger.error(
            "policy unavailable: set --policy / $UNTELL_POLICY_DIR to a real adapter dir and "
            "`pip install -e .[train]` (needs torch+transformers+peft)."
        )
        return 2

    samples = load_samples(a.dataset, a.n)
    out: dict = {"tier": a.tier, "n": len(samples), "threshold": a.threshold}
    lines: list[str] = []

    if a.vs_base:
        base = LocalPolicyRewriter(adapter_dir=a.policy, use_adapter=False)
        if not base.available():  # same clean exit as the policy guard, instead of an ImportError in _load
            logger.error(
                "base model unavailable for --vs-base: needs torch+transformers (`pip install -e .[train]`)."
            )
            return 2
        out["base"] = _eval(base, samples, a.tier, a.threshold)
        lines.append(_summary("base", out["base"], a.threshold))

    out["policy"] = _eval(policy, samples, a.tier, a.threshold)
    lines.append(_summary("policy", out["policy"], a.threshold))

    print(json.dumps(out, indent=2) if a.json else "\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
