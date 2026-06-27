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
import statistics
import sys


def _eval(rw, samples: list[str], tier: str) -> list[dict]:
    from untell.scripts.quality import similarity
    from untell.scripts.score import score_text

    rows: list[dict] = []
    for i, s in enumerate(samples):
        pre = float(score_text(s, tier=tier)["max"])
        out = rw.rewrite(s, {"detectors": {}}, threshold=0.30)
        post = float(score_text(out, tier=tier)["max"])
        rows.append({"pre": pre, "post": post, "sim": similarity(s, out)})
        print(f"  [{rw.name}] {i + 1}/{len(samples)}  P(AI) {pre:.2f} -> {post:.2f}", file=sys.stderr)
    return rows


def _summary(name: str, rows: list[dict], threshold: float) -> str:
    if not rows:
        return f"{name}: no rows"
    pre = statistics.mean(r["pre"] for r in rows)
    post = statistics.mean(r["post"] for r in rows)
    sim = statistics.mean(r["sim"] for r in rows)
    bypass = sum(1 for r in rows if r["post"] < threshold) / len(rows)
    return (
        f"{name:12s} mean P(AI) {pre:.3f} -> {post:.3f} | bypass {bypass:.0%} "
        f"(<{threshold:.2f}) | mean sim {sim:.3f}"
    )


def main(argv: list[str] | None = None) -> int:
    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()
    p = argparse.ArgumentParser(prog="untell-eval-policy", description=__doc__)
    p.add_argument("--policy", help="adapter dir (default: $UNTELL_POLICY_DIR)")
    p.add_argument("--dataset", default="builtin", help="held-out source set (eval.datasets)")
    p.add_argument("--n", type=int, default=25)
    p.add_argument("--tier", default="full", help="detector tier to score against")
    p.add_argument("--threshold", type=float, default=0.30)
    p.add_argument("--vs-base", action="store_true", help="also eval the untuned base model")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    from eval.datasets import load_samples
    from untell.rewriter.local_policy import LocalPolicyRewriter

    policy = LocalPolicyRewriter(adapter_dir=a.policy)
    if not policy.available():
        print(
            "policy unavailable: set --policy / $UNTELL_POLICY_DIR to a real adapter dir and "
            "`pip install -e .[train]` (needs torch+transformers+peft).",
            file=sys.stderr,
        )
        return 2

    samples = load_samples(a.dataset, a.n)
    out: dict = {"tier": a.tier, "n": len(samples), "threshold": a.threshold}
    lines: list[str] = []

    if a.vs_base:
        base = LocalPolicyRewriter(adapter_dir=a.policy, use_adapter=False)
        out["base"] = _eval(base, samples, a.tier)
        lines.append(_summary("base", out["base"], a.threshold))

    out["policy"] = _eval(policy, samples, a.tier)
    lines.append(_summary("policy", out["policy"], a.threshold))

    print(json.dumps(out, indent=2) if a.json else "\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
