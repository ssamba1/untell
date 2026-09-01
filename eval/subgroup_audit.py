"""Who does this detector fail? False-positive rate by writer subgroup, on known-human text.

Every other measurement in this repo asks how *often* a detector is wrong. This one asks *who it
is wrong about*, which is the question the literature says matters and no tool answers.

The evidence that it matters is not ours. Liang et al. (2023) measured a 61.3% false-positive rate
on non-native TOEFL essays against near-perfect classification of native-speaker essays. A 2026 ACL
study across 16 detectors found no detector uniformly fair. arXiv:2603.20254 makes the structural
argument -- in a university there is no single "human distribution", so the null hypothesis is
composite and the false positives are unavoidable -- and works it out at roughly 750 wrongly
flagged students per 10,000. Vendors publish sub-1% false-positive rates from internal testing.
Somebody should be able to check.

**Every flag here is an error by construction.** The corpus is known-human writing, so a detector
that flags it is wrong -- there is no ambiguity to argue about, and no ground-truth labelling for
anyone to dispute. That is what makes a false-positive audit the cleanest measurement available
against a detector, and it is why this module refuses to score anything but known-human text.

Three rules this module will not bend, because a careless subgroup number does more harm than the
detectors it audits:

1. **No rate for a group too small to support one.** Below ``MIN_GROUP`` the row reports its count
   and the word ``insufficient``, never a percentage. A 100% false-positive rate on n=3 is a
   sentence about three people, not about a group.
2. **Every rate carries an interval.** Wilson score, not the normal approximation, because these
   are small samples near 0 and 1 where the normal interval famously misbehaves (it can produce a
   lower bound below zero, and it collapses to zero width when nothing is flagged).
3. **A disparity is a claim about a detector, never about a document.** ``render`` prints that in
   the report itself, because the tool will otherwise be quoted at an individual student, which is
   the exact harm it exists to document.

    python -m eval.subgroup_audit --corpus ellipse --tier lite --n 400
    python -m eval.subgroup_audit --corpus ellipse --tier lite --by race_ethnicity --json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

# The floor below which a group gets a count and no rate. 30 is the conventional small-sample
# threshold and is deliberately not tunable downward from the CLI: the temptation to lower it to
# make a group "reportable" is precisely the failure this constant exists to prevent.
MIN_GROUP = 30

# Subgroup axes ELLIPSE carries. `grade` is included because a detector keyed on perplexity should
# be expected to flag younger writers more, and that is a checkable prediction rather than a guess.
DEFAULT_AXES = ("race_ethnicity", "gender", "SES", "grade")


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion.

    Chosen over the normal approximation because subgroup false-positive rates live near 0 and 1
    at small n, exactly where the normal interval breaks: it returns bounds outside [0, 1] and
    reports zero uncertainty when nothing was flagged. Wilson does neither.
    """
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def audit(
    rows: list[dict],
    tier: str = "lite",
    threshold: float | None = None,
    axes: tuple[str, ...] = DEFAULT_AXES,
    progress: bool = False,
) -> dict:
    """Score known-human texts once, then group the flags by each subgroup axis.

    `rows` are dicts with a ``text`` key plus whatever label columns the corpus carries. Scoring
    happens once per text and the grouping is done afterwards, so adding an axis costs nothing and
    every axis describes the same scored sample rather than a differently-drawn one.
    """
    from untell.scripts.score import DEFAULT_THRESHOLD, score_text

    thr = DEFAULT_THRESHOLD if threshold is None else threshold
    scored: list[dict] = []
    for i, row in enumerate(rows):
        result = score_text(row["text"], tier=tier, threshold=thr)
        top = result.get("max")
        if top is None:  # every detector opted out; not a false negative, just unscored
            continue
        scored.append({**row, "score": top, "flagged": bool(top >= thr)})
        if progress and (i + 1) % 50 == 0:
            print(f"  scored {i + 1}/{len(rows)}", file=sys.stderr)

    flagged = sum(1 for r in scored if r["flagged"])
    overall_lo, overall_hi = wilson(flagged, len(scored))
    report = {
        "corpus_n": len(rows),
        "scored_n": len(scored),
        "tier": tier,
        "threshold": thr,
        "overall_fpr": round(flagged / len(scored), 4) if scored else None,
        "overall_ci": [round(overall_lo, 4), round(overall_hi, 4)],
        "min_group": MIN_GROUP,
        "axes": {},
    }

    report["saturation"] = saturation(report["overall_fpr"])
    report["axes"] = _group(scored, axes)
    return report


# A detector that flags (or clears) almost everyone cannot discriminate between groups, so a
# disparity ratio computed there is not "no bias found" -- it is "this measurement had no room to
# find any". MEASURED 2026-09-01: untell's own lite tier flags 97.4% of ELLIPSE, and every
# subgroup ratio lands between 1.00 and 1.04 with every interval overlapping. Reporting that as
# fairness would be the single most misleading thing this module could do.
SATURATED_HIGH = 0.90
SATURATED_LOW = 0.02


def saturation(overall_fpr: float | None) -> str | None:
    if overall_fpr is None:
        return None
    if overall_fpr >= SATURATED_HIGH:
        return (f"SATURATED HIGH: {overall_fpr:.1%} of known-human text is flagged, so this "
                f"detector is not discriminating between anyone at this threshold. Subgroup "
                f"comparisons below are UNMEASURABLE here, not equal. Re-run with --sweep.")
    if overall_fpr <= SATURATED_LOW:
        return (f"SATURATED LOW: only {overall_fpr:.1%} is flagged, so there are too few errors "
                f"to attribute to any group. Subgroup comparisons below are UNMEASURABLE here, "
                f"not equal. Re-run with --sweep.")
    return None


def sweep(rows: list[dict], tier: str, thresholds: tuple[float, ...],
          axes: tuple[str, ...]) -> list[dict]:
    """Audit at several thresholds, so a non-saturated operating point can be found.

    Scoring is the expensive part and does not depend on the threshold, so this scores once and
    re-thresholds -- which also means every threshold describes exactly the same sample.
    """
    from untell.scripts.score import score_text

    scored = []
    for row in rows:
        result = score_text(row["text"], tier=tier, threshold=thresholds[0])
        if result.get("max") is not None:
            scored.append({**row, "score": result["max"]})
    out = []
    for thr in thresholds:
        flagged = [dict(r, flagged=r["score"] >= thr) for r in scored]
        rep = _group(flagged, axes)
        hits = sum(1 for r in flagged if r["flagged"])
        fpr = hits / len(flagged) if flagged else None
        lo, hi = wilson(hits, len(flagged))
        out.append({"threshold": thr, "scored_n": len(flagged),
                    "overall_fpr": round(fpr, 4) if fpr is not None else None,
                    "overall_ci": [round(lo, 4), round(hi, 4)],
                    "saturation": saturation(fpr), "axes": rep})
    return out


def _group(scored: list[dict], axes: tuple[str, ...]) -> dict:
    axes_out = {}
    for axis in axes:
        groups: dict[str, list[dict]] = {}
        for r in scored:
            if r.get(axis) not in (None, ""):
                groups.setdefault(str(r[axis]), []).append(r)
        rendered = {}
        for name, members in sorted(groups.items()):
            hits = sum(1 for m in members if m["flagged"])
            if len(members) < MIN_GROUP:
                rendered[name] = {"n": len(members), "flagged": hits, "fpr": None,
                                  "status": "insufficient"}
                continue
            lo, hi = wilson(hits, len(members))
            rendered[name] = {"n": len(members), "flagged": hits,
                              "fpr": round(hits / len(members), 4),
                              "ci": [round(lo, 4), round(hi, 4)], "status": "reported"}
        axes_out[axis] = {"groups": rendered, "disparity": _disparity(rendered)}
    return axes_out


def _disparity(groups: dict) -> dict | None:
    """Highest over lowest reportable group rate, and whether their intervals even separate.

    A ratio on its own invites the headline and hides the uncertainty. Two groups whose Wilson
    intervals overlap have not been shown to differ at all, however large the ratio between their
    point estimates, so `separated` is reported beside it and is the field that decides whether
    there is anything to say.
    """
    usable = {k: v for k, v in groups.items() if v["status"] == "reported"}
    if len(usable) < 2:
        return None
    hi_name = max(usable, key=lambda k: usable[k]["fpr"])
    lo_name = min(usable, key=lambda k: usable[k]["fpr"])
    hi, lo = usable[hi_name], usable[lo_name]
    ratio = (hi["fpr"] / lo["fpr"]) if lo["fpr"] > 0 else None
    return {
        "worst": hi_name, "worst_fpr": hi["fpr"],
        "best": lo_name, "best_fpr": lo["fpr"],
        "ratio": round(ratio, 2) if ratio is not None else None,
        # Non-overlapping Wilson intervals: a conservative separation check, not a hypothesis test.
        "separated": bool(hi["ci"][0] > lo["ci"][1]),
    }


def render(report: dict) -> str:
    out = [
        f"False-positive rate on KNOWN-HUMAN text  --  tier {report['tier']}, "
        f"threshold {report['threshold']}",
        f"{report['scored_n']} essays scored of {report['corpus_n']}. "
        f"Every flag below is an error: this corpus is human-written.",
        "",
    ]
    ci = report["overall_ci"]
    out.append(f"OVERALL false-positive rate: {report['overall_fpr']:.1%} "
               f"(95% CI {ci[0]:.1%}-{ci[1]:.1%})")
    if report.get("saturation"):
        out += ["", "  !! " + report["saturation"]]
    for axis, block in report["axes"].items():
        out.append("")
        out.append(f"by {axis}")
        for name, g in sorted(block["groups"].items(),
                              key=lambda kv: (kv[1]["fpr"] is None, -(kv[1]["fpr"] or 0))):
            if g["status"] == "insufficient":
                out.append(f"  {name:34} n={g['n']:<5} insufficient "
                           f"(< {report['min_group']}); no rate reported")
                continue
            lo, hi = g["ci"]
            out.append(f"  {name:34} n={g['n']:<5} {g['fpr']:6.1%}  "
                       f"(95% CI {lo:5.1%}-{hi:5.1%})")
        d = block["disparity"]
        if d:
            verdict = ("intervals separate" if d["separated"]
                       else "intervals OVERLAP - not shown to differ")
            ratio = f"{d['ratio']}x" if d["ratio"] is not None else "n/a"
            out.append(f"  -> worst {d['worst']} vs best {d['best']}: {ratio}, {verdict}")
    out += [
        "",
        "This measures a DETECTOR, not a document. A per-group rate says nothing about whether any",
        "individual text was machine-written, and must never be quoted at a person.",
    ]
    return "\n".join(out)


def render_sweep(results: list[dict]) -> str:
    """One line per threshold, so the operating point where disparity is measurable is visible.

    The point of the sweep is not to pick a flattering threshold -- it is to show where the
    detector has any discriminating power at all, because outside that band a subgroup comparison
    is arithmetic without meaning.
    """
    out = ["threshold sweep on KNOWN-HUMAN text (every flag is an error)", ""]
    out.append(f"{'thr':>6} {'overall FPR':>12}  {'state':<12} worst-vs-best group disparity")
    usable = 0
    for r in results:
        state = "saturated" if r["saturation"] else "measurable"
        usable += state == "measurable"
        bits = []
        for axis, block in r["axes"].items():
            d = block["disparity"]
            if d and d["ratio"] is not None:
                mark = "*" if d["separated"] else " "
                bits.append(f"{axis}={d['ratio']}x{mark}")
        fpr = f"{r['overall_fpr']:.1%}" if r["overall_fpr"] is not None else "n/a"
        out.append(f"{r['threshold']:>6} {fpr:>12}  {state:<12} " + "  ".join(bits))
    out += ["", "* = the two groups' 95% Wilson intervals do not overlap (a real difference).",
            "  No star means the ratio is not distinguishable from noise at this sample size."]
    if not usable:
        out.append("")
        out.append("NO measurable operating point: this detector flags nearly all human text at "
                   "every threshold tried. Its false-positive rate is the finding; a fairness "
                   "comparison cannot be made against it.")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default="ellipse")
    ap.add_argument("--csv", type=Path, default=None,
                    help="a local labelled CSV instead of the fetched corpus")
    ap.add_argument("--tier", default="lite")
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--n", type=int, default=300, help="0 for the whole corpus")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--by", default=",".join(DEFAULT_AXES))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sweep", action="store_true",
                    help="audit across thresholds to find a non-saturated operating point")
    ap.add_argument("--thresholds", default="0.3,0.5,0.7,0.8,0.9,0.95,0.99")
    a = ap.parse_args(argv)

    from eval.datasets import load_labelled

    rows = load_labelled(a.corpus, csv_path=a.csv)
    if a.n and a.n < len(rows):
        random.Random(a.seed).shuffle(rows)
        rows = rows[: a.n]
    axes = tuple(x for x in a.by.split(",") if x)
    if a.sweep:
        thrs = tuple(float(x) for x in a.thresholds.split(",") if x)
        results = sweep(rows, a.tier, thrs, axes)
        print(json.dumps(results, indent=2) if a.json else render_sweep(results))
        return 0
    report = audit(rows, tier=a.tier, threshold=a.threshold, axes=axes, progress=not a.json)
    print(json.dumps(report, indent=2) if a.json else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
