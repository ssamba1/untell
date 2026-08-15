"""Score the loop's output with a detector the loop was never allowed to see.

Every evasion figure this project publishes is measured with the same detector ensemble the loop
minimises. That is in-sample by construction, and ``best_of`` — documented throughout as the single
biggest lever — is exactly the mechanism that would exploit a scorer's quirks rather than the
property the scorer stands for. Nothing here had ever checked the difference.

``RadarDetector`` is the control this repository already owned without using it as one. RADAR is
adversarially trained against a paraphraser, and it is gated behind ``UNTELL_ENABLE_RADAR=1``, so it
has never appeared in a selection set or in a published number. That gate is what makes it a
holdout, and it is why this module refuses to run when the gate is open: with RADAR inside the tier
the loop optimises against it and the arm measures nothing. ``eval/benchmark.py --enable-radar``
does precisely that, deliberately — it asks "can we beat RADAR when we try", which is a different
question from the one here.

    python -m eval.holdout --dataset raid --n 10 --seed 0

MEASURED at n=10 on RAID, shipped configuration, three seeds:

    in sample   0.9162 -> 0.4268 / 0.4063 / 0.4301    flagged 10/10 -> 4 / 2 / 3
    held out    0.7222 -> 0.5035 / 0.4981 / 0.4391    flagged  7/10 -> 4 / 4 / 4

**The in-sample flagged count moves and the held-out one does not.** Seed 1 drove the local ensemble
to 2 of 10 — its best run — and ended at the same 4 of 10 out of sample as the others. Two documents
are never cleared out of sample in any seed while doing well in sample; on the sharpest of them the
loop reports 0.9928 -> 0.345 and the holdout reads 1.000 all three times. Rank correlation between
the two post-scores is +0.394 / +0.782 / +0.333, so the local ``max`` does not order documents the
way an unseen detector does, and how strongly it disagrees is itself unstable.

``by_conviction`` is a diagnostic, NOT the finding, and this is the one warning worth carrying: on
seed 0 alone it read ``-0.0129`` for the confident group against ``-0.3560`` for the unsure one, and
it was quoted as the result. The repeats gave ``-0.2321 / -0.2189`` and ``-0.2745 / -0.2890`` — no
split at all. One document with a 0.9991 prior fell to 0.288 on the second seed. A group of four,
from one draw of a stochastic rewriter, produced a clean story that does not exist.

The premise check runs every time. A control that cannot separate human from AI text on this corpus
measures nothing, and reporting a transfer number computed through a dead detector would be worse
than reporting none — so ``separates`` is part of the result and a caller that ignores it is
quoting an unvalidated number.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics

from eval.datasets import load_pairs
from untell.scripts.run import untell_text
from untell.scripts.score import DEFAULT_THRESHOLD

# The verdict bar, not the loop's 0.30 target. "Still flagged" is the question a user asks, and it
# is the one number that means the same thing in-sample and out.
FLAG_BAR = 0.45

# Above this, the holdout had already made up its mind about the document before anything was
# rewritten. 0.90 sits in a real gap in the measured distribution — priors ran 0.9387-0.9996 above it
# and topped out at 0.8323 below — but note that the gap is in the PRE scores, which are a property
# of the corpus and identical across seeds. It is not evidence that the two groups behave
# differently afterwards; measured over three seeds they do not. Kept because "what did the control
# already think" is the right axis to slice a transfer number on, not because the slice found
# anything.
CONVICTION = 0.90


def _score_holdout(detector, rows) -> None:
    """Score every frozen row with the control. Called only after the loop has finished."""
    for row in rows:
        row["holdout_pre"] = detector.score(row["source"])
        row["holdout_post"] = detector.score(row["final"])
        row["holdout_human"] = detector.score(row["human"])


def _holdout_detector():
    """The control, with the gate that keeps it out of the tier checked rather than assumed."""
    if os.environ.get("UNTELL_ENABLE_RADAR") == "1":
        raise RuntimeError(
            "UNTELL_ENABLE_RADAR=1 puts RADAR inside the tier the loop selects against, so it is "
            "no longer held out and this measurement has no subject. Unset it."
        )
    from untell.detectors.radar import RadarDetector

    return RadarDetector()


def run(
    dataset: str = "raid",
    n: int = 10,
    tier: str = "full",
    rewriter: str = "composite",
    threshold: float = DEFAULT_THRESHOLD,
    best_of: int = 3,
    max_iters: int = 5,
    seed: int = 0,
) -> dict:
    """Run the loop, then score its frozen outputs with the held-out detector."""
    detector = _holdout_detector()
    pairs = load_pairs(dataset, n=n, min_words=60)
    if not pairs:
        return {"error": f"no paired data for {dataset!r}"}

    rows = []
    for i, (human, ai) in enumerate(pairs):
        result = untell_text(
            ai, tier=tier, threshold=threshold, max_iters=max_iters,
            best_of=best_of, rewriter=rewriter, seed=seed,
        )
        # `untell_text` reports a refusal as {"error": ...} with no `pre`/`post`, and this indexed
        # straight into `result["pre"]`. MEASURED with a typo'd backend name, `--rewriter compsite`:
        #
        #     KeyError: 'pre'
        #
        # a bare traceback for a message the loop had already written correctly ("rewriter
        # 'compsite' is not available"). Every refusal took that path — an unset API key, an
        # unavailable backend, a meaning gate that vetoed every draw — so the one thing a user
        # needed to read was the one thing they could not see.
        #
        # `--rewriter` is deliberately left without an argparse `choices` list: hosted backends are
        # valid names here, and `untell_text` resolves them against what is actually configured,
        # which argparse cannot. The fix is to surface its answer, not to duplicate its knowledge.
        if "error" in result:
            raise SystemExit(f"untell_text refused sample {i}: {result['error']}")
        rows.append({
            "i": i,
            "pre_max": result["pre"]["max"],
            "post_max": result["post"]["max"],
            "similarity": result["similarity"],
            "final": result["final"],
            "source": ai,
            "human": human,
        })

    # Scored only now, on text the loop can no longer influence. Doing this inside the loop would
    # leak the control into selection through nothing more than an ordering mistake.
    #
    # The gate has to be OPEN for scoring and SHUT for the loop, and those are the same environment
    # variable. `RadarDetector.available()` returns False without it, so the first version of this
    # harness — which kept it shut throughout, correctly for the loop — got `None` from every call
    # and returned "radar returned no scores". It failed loudly because `if not scored` is checked;
    # the eight tests missed it entirely because they inject a fake detector and never touch the
    # real gate. Opened here, after every rewrite is frozen, and restored afterwards so a caller's
    # environment is unchanged and a later `_holdout_detector()` in the same process still refuses.
    previous = os.environ.get("UNTELL_ENABLE_RADAR")
    os.environ["UNTELL_ENABLE_RADAR"] = "1"
    try:
        _score_holdout(detector, rows)
    finally:
        if previous is None:
            os.environ.pop("UNTELL_ENABLE_RADAR", None)
        else:
            os.environ["UNTELL_ENABLE_RADAR"] = previous

    scored = [r for r in rows if isinstance(r.get("holdout_post"), float)]
    if not scored:
        return {"error": f"{detector.name} returned no scores; nothing to compare against"}

    # The in-sample column can be pinned by one saturated member, and then "did clearing the tier
    # transfer" has no subject because nothing cleared. MEASURED: the first run of this experiment
    # reported 1.0000 -> 1.0000 on every document, because `mage` scores ordinary AI prose at
    # 0.99998736-0.99998772 — a dynamic range of 3.6e-06 across ten texts — and it is in the default
    # full tier. Every published evasion figure is taken with UNTELL_DISABLE_MAGE=1; a run of this
    # harness that forgets it produces a vacuous table that looks like a finding.
    pinned = all(r["pre_max"] >= 0.99 and r["post_max"] >= 0.99 for r in scored)

    ai_side = statistics.fmean(r["holdout_pre"] for r in scored)
    human_side = statistics.fmean(r["holdout_human"] for r in scored)
    paired_wins = sum(r["holdout_pre"] > r["holdout_human"] for r in scored)

    by_conviction = {}
    for label, group in (
        ("confident", [r for r in scored if r["holdout_pre"] >= CONVICTION]),
        ("unsure", [r for r in scored if r["holdout_pre"] < CONVICTION]),
    ):
        if not group:
            continue
        by_conviction[label] = {
            "n": len(group),
            "mean_delta_tier": statistics.fmean(r["post_max"] - r["pre_max"] for r in group),
            "mean_delta_holdout": statistics.fmean(
                r["holdout_post"] - r["holdout_pre"] for r in group
            ),
            "still_flagged": sum(r["holdout_post"] >= FLAG_BAR for r in group),
        }

    return {
        "config": {"dataset": dataset, "n": len(rows), "tier": tier, "rewriter": rewriter,
                   "best_of": best_of, "max_iters": max_iters, "seed": seed,
                   "holdout": detector.name},
        # The premise. `separates` false means every number below is uninterpretable, not bad.
        "control": {
            "holdout_mean_ai": ai_side,
            "holdout_mean_human": human_side,
            "paired_ai_above_human": f"{paired_wins}/{len(scored)}",
            "separates": paired_wins >= 0.75 * len(scored),
        },
        "in_sample": {
            "pinned": pinned,
            "mean_pre": statistics.fmean(r["pre_max"] for r in scored),
            "mean_post": statistics.fmean(r["post_max"] for r in scored),
            "flagged_pre": sum(r["pre_max"] >= FLAG_BAR for r in scored),
            "flagged_post": sum(r["post_max"] >= FLAG_BAR for r in scored),
        },
        "out_of_sample": {
            "mean_pre": statistics.fmean(r["holdout_pre"] for r in scored),
            "mean_post": statistics.fmean(r["holdout_post"] for r in scored),
            "flagged_pre": sum(r["holdout_pre"] >= FLAG_BAR for r in scored),
            "flagged_post": sum(r["holdout_post"] > FLAG_BAR for r in scored),
            "improved_on": sum(r["holdout_post"] < r["holdout_pre"] for r in scored),
        },
        "by_conviction": by_conviction,
        "mean_similarity": statistics.fmean(r["similarity"] for r in scored),
        "rows": [{k: v for k, v in r.items() if k not in ("final", "source", "human")}
                 for r in scored],
    }


def render(result: dict) -> str:
    if "error" in result:
        return f"error: {result['error']}"
    cfg, ctl = result["config"], result["control"]
    ins, out = result["in_sample"], result["out_of_sample"]
    n = cfg["n"]
    lines = [
        f"{cfg['dataset']} n={n} tier={cfg['tier']} rewriter={cfg['rewriter']} "
        f"best_of={cfg['best_of']} seed={cfg['seed']}  holdout={cfg['holdout']}",
        "",
        f"control: {cfg['holdout']} separates AI {ctl['holdout_mean_ai']:.4f} from human "
        f"{ctl['holdout_mean_human']:.4f}, paired {ctl['paired_ai_above_human']}"
        + ("" if ctl["separates"] else "   <- DOES NOT SEPARATE; the numbers below mean nothing"),
        "",
        f"in sample      {ins['mean_pre']:.4f} -> {ins['mean_post']:.4f}   "
        f"flagged {ins['flagged_pre']}/{n} -> {ins['flagged_post']}/{n}"
        + ("\n  every document is pinned above 0.99 in and out, so nothing cleared the tier and the"
           "\n  transfer question has no subject — rerun with UNTELL_DISABLE_MAGE=1" if ins["pinned"]
           else ""),
        f"held out       {out['mean_pre']:.4f} -> {out['mean_post']:.4f}   "
        f"flagged {out['flagged_pre']}/{n} -> {out['flagged_post']}/{n}   "
        f"improved on {out['improved_on']}/{n}",
        "",
        "by what the holdout thought BEFORE the rewrite:",
    ]
    for label, row in result["by_conviction"].items():
        lines.append(
            f"  {label:<10} n={row['n']}  d in-sample {row['mean_delta_tier']:+.4f}  "
            f"d held-out {row['mean_delta_holdout']:+.4f}  "
            f"still flagged {row['still_flagged']}/{row['n']}"
        )
    lines += ["", f"mean similarity {result['mean_similarity']:.4f}"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", default="raid", choices=["hc3", "raid", "mage"])
    parser.add_argument("--n", type=int, default=10)
    # Every tier the loader supports, `commercial` included. It was missing, so this CLI rejected
    # at parse time a value its own `score_text` call accepts — the exact divergence
    # `test_surface_parity.py` exists to catch, and the reason that test has been red.
    #
    # Accepting it is right even without API keys configured: `score_text(tier="commercial")`
    # returns normally and reports the tier that actually produced numbers ("full" here), so the
    # honest answer comes from the loader, which knows what is configured, rather than from an
    # argparse list that cannot.
    parser.add_argument("--tier", default="full", choices=["lite", "full", "heavy", "commercial"])
    parser.add_argument("--rewriter", default="composite")
    parser.add_argument("--threshold", "-t", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--best-of", type=int, default=3)
    parser.add_argument("--max-iters", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = run(
        dataset=args.dataset, n=args.n, tier=args.tier, rewriter=args.rewriter,
        threshold=args.threshold, best_of=args.best_of, max_iters=args.max_iters, seed=args.seed,
    )
    print(json.dumps(result, indent=2) if args.json else render(result))
    return 1 if "error" in result else 0


if __name__ == "__main__":
    raise SystemExit(main())
