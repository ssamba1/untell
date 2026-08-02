"""Distill our SOTA inference loop into SFT training data — our unique training edge.

Our Claude + detector-feedback + per-sentence loop is already a strong teacher. Run it on many AI
samples, keep the outputs that PASS the ensemble while preserving meaning, and emit {prompt, source,
humanized} JSONL. SFT a small model on that = a fast model as good as the expensive loop, with no API
key at inference. Most repos have no teacher this strong.

    pip install -e ".[full,api]" && export ANTHROPIC_API_KEY=...   # the loop needs a rewriter (teacher)
    python -m training.distill --dataset raid --n 2000 --tier full --out data/sft.jsonl
    # then: SFT a small model on data/sft.jsonl, optionally GRPO/DPO refine (training.rl_humanizer).
"""

from __future__ import annotations

import argparse
import json
import logging

from untell.rewriter.local_policy import _TRAIN_PROMPT as _PROMPT


def distill(dataset: str = "builtin", n: int = 200, tier: str = "full", threshold: float = 0.30, margin: float = 0.05):
    """Run the loop on ``n`` samples; yield SFT rows for the ones that passed (kept the meaning)."""
    from eval.datasets import load_samples
    from untell.scripts.quality import recommended_bar
    from untell.scripts.run import untell_text

    rows = []
    kept = 0
    # Count what load_samples actually returned. Reporting the REQUESTED n as the denominator told
    # a user who asked for 2000 from a 50-item dataset "wrote 3/2000", i.e. that 1997 samples were
    # rejected by the meaning/flagged filter, when only 50 were ever seen. That misdiagnosis points
    # at the filter instead of at the dataset.
    samples = list(load_samples(dataset, n))
    for src in samples:
        result = untell_text(src, tier=tier, threshold=threshold, margin=margin)
        if "error" in result:
            continue
        # Use the bar that matches the metric similarity() actually used. It is backend-adaptive
        # (BERTScore 0.88 / cosine 0.76 / token-overlap 0.50) and a fixed 0.76 is only meaningful for
        # the middle one — the same defect just fixed in training/reward.py. Here it is arguably
        # worse: this filter decides which examples enter the DISTILLATION SET, so on a box without
        # sentence-transformers it silently rejects nearly every good rewrite and "successfully"
        # trains on an almost-empty dataset.
        sim_bar = recommended_bar()
        if not result.get("flagged") and result.get("similarity", 0.0) >= sim_bar:
            rows.append({"prompt": _PROMPT.format(text=src), "source": src, "humanized": result["final"]})
            kept += 1
    return {"kept": kept, "total": len(samples), "requested": n, "rows": rows}


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(prog="training.distill", description=__doc__)
    parser.add_argument("--dataset", default="builtin")
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--tier", default="full", choices=["lite", "full", "heavy", "commercial"])
    parser.add_argument("--out", default="data/sft.jsonl")
    args = parser.parse_args(argv)

    from untell._env import load_env

    load_env()

    out = distill(dataset=args.dataset, n=args.n, tier=args.tier)
    import os

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for row in out["rows"]:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")
    short = ""
    if out["total"] < out["requested"]:
        short = f" (dataset supplied {out['total']} of the {out['requested']} requested)"
    print(f"wrote {out['kept']}/{out['total']} passing samples -> {args.out}{short}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
