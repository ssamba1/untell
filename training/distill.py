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


def distill(
    dataset: str = "builtin",
    n: int = 200,
    tier: str = "full",
    threshold: float = 0.30,
    margin: float = 0.05,
    # "composite" and best_of=3, matching `untell humanize` and the REST/MCP surfaces. untell_text's
    # own defaults are rewriter=None (auto-select, which needs an API key and otherwise returns
    # "no rewriter configured") and best_of=1 — the weak draw measured at 33% still flagged against
    # 0% at best_of=3. This function's filter keeps only samples the loop got PAST the detectors, so
    # a weak loop does not merely produce weaker rows: it silently drops every sample that a proper
    # loop would have kept, shrinking the distillation set and biasing it toward the easiest texts.
    rewriter: str = "composite",
    best_of: int = 3,
):
    """Run the loop on ``n`` samples; yield SFT rows for the ones that passed (kept the meaning)."""
    from eval.datasets import load_samples
    from untell.rewriter import get_rewriter
    from untell.scripts.quality import recommended_bar
    from untell.scripts.run import untell_text

    rw = None if rewriter == "auto" else get_rewriter(prefer=rewriter)
    if rw is None and rewriter != "auto":
        raise RuntimeError(
            f"rewriter {rewriter!r} is unavailable (some backends need the '.[full]' extra). "
            "Refusing to fall back to auto-select, which would silently use a PAID hosted rewriter "
            "for every one of the samples this builds a training set from."
        )

    rows = []
    kept = 0
    # Count what load_samples actually returned. Reporting the REQUESTED n as the denominator told
    # a user who asked for 2000 from a 50-item dataset "wrote 3/2000", i.e. that 1997 samples were
    # rejected by the meaning/flagged filter, when only 50 were ever seen. That misdiagnosis points
    # at the filter instead of at the dataset.
    # strict for anything but the built-in set: this builds a TRAINING SET and prints the dataset
    # name beside the count, so a silent fallback to five padded paragraphs would be labelled with
    # a real corpus's name and trained on.
    samples = list(load_samples(dataset, n, strict=dataset.lower() not in ("builtin", "sample")))
    for src in samples:
        result = untell_text(
            src, tier=tier, threshold=threshold, margin=margin, rewriter=rw, best_of=best_of
        )
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


def build_parser() -> argparse.ArgumentParser:
    """The distillation CLI's parser, split out of ``main`` so its defaults can be read in tests."""
    parser = argparse.ArgumentParser(prog="training.distill", description=__doc__)
    parser.add_argument("--dataset", default="builtin")
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--tier", default="full", choices=["lite", "full", "heavy", "commercial"])
    parser.add_argument("--out", default="data/sft.jsonl")
    # threshold and margin were parameters of distill() that main neither exposed nor passed, so the
    # two gates deciding which samples enter the training set were unreachable from the command that
    # builds it.
    parser.add_argument(
        "--threshold", "-t", type=float, default=0.30,
        help="max P(AI) a sample must reach to be kept (default 0.30)",
    )
    parser.add_argument(
        "--margin", type=float, default=0.05,
        help="safety headroom below --threshold, so a borderline pass keeps iterating (default 0.05)",
    )
    parser.add_argument(
        "--rewriter", default="composite",
        help="free no-key backend (default composite, matching `untell humanize`), or 'auto' for a "
        "hosted LLM if a key is set",
    )
    parser.add_argument(
        "--best-of", type=int, default=3,
        help="candidates per iteration (default 3, matching `untell humanize`). best-of-1 was "
        "measured at 33%% still flagged against 0%% at 3, and a sample the loop fails to clear is "
        "DISCARDED here, so a weak draw shrinks and biases the training set.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args(argv)

    from untell._env import load_env

    load_env()

    out = distill(
        dataset=args.dataset, n=args.n, tier=args.tier, threshold=args.threshold,
        margin=args.margin, rewriter=args.rewriter, best_of=args.best_of,
    )
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
