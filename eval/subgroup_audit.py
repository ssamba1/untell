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

**This measures HALF of a fairness audit by default, and says so.** The standard toolkits -- Aequitas,
AIF360, Fairlearn -- compute false-positive-rate parity *and* false-negative-rate parity, because
equalised odds needs both. This module computes only the first. That is a deliberate limit, not an
oversight: false negatives require known-AI text from the same writers and the same task, and no
such corpus exists. Pairing an arbitrary AI corpus against these essays would measure the
difference between two datasets and report it as a property of a detector.

So a clean bill of health from this tool is **not** a clean bill of health. A detector could show
perfect false-positive parity here and still miss machine-written work at wildly different rates
across groups, which would harm exactly the students who are not being flagged. Read every result
below as "who does this detector wrongly accuse", never as "is this detector fair".

`equalised_odds()` computes both rates and both parities, and is the honest entry point -- but it
REQUIRES a corpus carrying machine-written text from the same writers on the same prompts, which
nothing here ships. It is a documented input requirement rather than a hole in the tool.

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

# Values that mean "we do not know", not "this group". MEASURED 2026-09-01: ASAP 2.0 codes
# missing demography as the string "NA", and 4,019 of its 17,307 essays lack economic and
# disability status. Those rows scored 19.1% where every real group scored 30-38%, so treating
# "NA" as a subgroup made it the "best" group on two axes and produced a 2.01x headline ratio
# against a data-collection artifact. A missing-data bucket is not a population and must never be
# a comparison arm.
_MISSING = {"na", "n/a", "unknown", "none", "null", "not reported", "unspecified", "-", ""}

# Subgroup axes ELLIPSE carries. `Overall` is the writer's rated English proficiency and is the
# axis that actually separates: at threshold 0.50 the lite tier's false-positive rate rises
# MONOTONICALLY with proficiency, 33.7% at level 2 to 53.1% at level 4.5. `grade` is here because
# a perplexity-keyed detector should flag younger writers more, which is a checkable prediction.
DEFAULT_AXES = ("Overall", "race_ethnicity", "gender", "SES", "grade")


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
            v = r.get(axis)
            if v is not None and str(v).strip().lower() not in _MISSING:
                groups.setdefault(str(v), []).append(r)
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
        # An axis the corpus does not carry must SAY so. It rendered as a bare heading with
        # nothing under it once (a --csv label-filter bug dropped `ell_status`), and a heading
        # with no rows reads exactly like "no disparity found here" to anyone skimming.
        axes_out[axis] = {"groups": rendered, "disparity": _disparity(rendered),
                          "missing": not rendered}
    return axes_out


def equalised_odds(rows: list[dict], tier: str = "lite", threshold: float | None = None,
                   axes: tuple[str, ...] = DEFAULT_AXES, label_key: str = "is_ai") -> dict:
    """BOTH error rates per subgroup: the other half of a fairness audit.

    `rows` must carry a truth label under `label_key` -- truthy for machine-written, falsy for
    human. Every other entry point in this module refuses AI text on purpose; this one requires it,
    because false negatives cannot be measured without it.

    Reports false-positive rate (human called machine) and false-negative rate (machine called
    human) per group, plus both parities. Equalised odds asks for BOTH to be similar across groups,
    and a detector can pass one while failing the other badly -- a detector that never flags one
    group has perfect FPR parity for them and lets their machine-written work through, which harms
    the same students by a different route.

    **This needs a corpus that pairs human and machine text from the same writers on the same
    prompts.** Pairing an arbitrary AI corpus against a human one measures the distance between two
    datasets and reports it as a property of a detector. RAID, MAGE and HC3 are the nearest
    candidates. Nothing in this repository ships such a corpus: `.claude/corpora/` is HC3 HUMAN
    text, and `eval/detector_audit.py` carries five hand-written AI probes, which is a smoke test
    and not a sample. Supply your own, and say in any write-up which corpus it was.
    """
    from untell.scripts.score import DEFAULT_THRESHOLD, score_text

    thr = DEFAULT_THRESHOLD if threshold is None else threshold
    scored = []
    for row in rows:
        if label_key not in row:
            raise ValueError(
                f"equalised odds needs a {label_key!r} label on every row; without machine-written "
                f"text there are no false negatives to measure. Use audit() for the "
                f"false-positive-only report."
            )
        result = score_text(row["text"], tier=tier, threshold=thr)
        top = result.get("max")
        if top is None:
            continue
        scored.append({**row, "score": top, "flagged": bool(top >= thr),
                       "is_ai": bool(row[label_key])})

    humans = [r for r in scored if not r["is_ai"]]
    ais = [r for r in scored if r["is_ai"]]
    out: dict = {"scored_n": len(scored), "human_n": len(humans), "ai_n": len(ais),
                 "tier": tier, "threshold": thr, "min_group": MIN_GROUP, "axes": {}}
    if not humans or not ais:
        out["error"] = ("both classes are required: got "
                        f"{len(humans)} human and {len(ais)} machine-written rows")
        return out

    for axis in axes:
        groups: dict[str, dict] = {}
        names = {str(r[axis]) for r in scored
                 if r.get(axis) is not None and str(r[axis]).strip().lower() not in _MISSING}
        for name in sorted(names):
            h = [r for r in humans if str(r.get(axis)) == name]
            a = [r for r in ais if str(r.get(axis)) == name]
            if len(h) < MIN_GROUP or len(a) < MIN_GROUP:
                groups[name] = {"human_n": len(h), "ai_n": len(a), "status": "insufficient"}
                continue
            fp = sum(1 for r in h if r["flagged"])
            fn = sum(1 for r in a if not r["flagged"])
            flo, fhi = wilson(fp, len(h))
            nlo, nhi = wilson(fn, len(a))
            groups[name] = {
                "human_n": len(h), "ai_n": len(a),
                "fpr": round(fp / len(h), 4), "fpr_ci": [round(flo, 4), round(fhi, 4)],
                "fnr": round(fn / len(a), 4), "fnr_ci": [round(nlo, 4), round(nhi, 4)],
                "status": "reported",
            }
        usable = {k: v for k, v in groups.items() if v["status"] == "reported"}
        out["axes"][axis] = {
            "groups": groups,
            "fpr_disparity": _rate_disparity(usable, "fpr", "fpr_ci"),
            "fnr_disparity": _rate_disparity(usable, "fnr", "fnr_ci"),
        }
    return out


def _rate_disparity(groups: dict, rate_key: str, ci_key: str) -> dict | None:
    if len(groups) < 2:
        return None
    hi_name = max(groups, key=lambda k: groups[k][rate_key])
    lo_name = min(groups, key=lambda k: groups[k][rate_key])
    hi, lo = groups[hi_name], groups[lo_name]
    ratio = (hi[rate_key] / lo[rate_key]) if lo[rate_key] > 0 else None
    return {"worst": hi_name, "worst_rate": hi[rate_key],
            "best": lo_name, "best_rate": lo[rate_key],
            "ratio": round(ratio, 2) if ratio is not None else None,
            "separated": bool(hi[ci_key][0] > lo[ci_key][1])}


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
        if block.get("missing"):
            out.append("  !! this corpus carries no values for this axis - nothing measured here")
            continue
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


def ablate(rows: list[dict], axis: str, bands: dict) -> dict:
    """Audit each COMPONENT of the lite detector separately, at equal statistical power.

    A composite detector reports one number, and one number can hide two large biases pointing
    opposite ways. MEASURED 2026-09-01 on ELLIPSE, replicated on the held-out split: the
    vocabulary half of `perplexity_burstiness` flags LOW-proficiency writers 1.57x more, and the
    burstiness half flags HIGH-proficiency writers 1.42x more. Both separate at 95%. In the
    combined detector they partly cancel, so an aggregate fairness score understates both.

    That is the argument for auditing components rather than black boxes, and it is the one thing
    a benchmark that treats a detector as opaque structurally cannot report.

    Each component is thresholded at its OWN median so both flag about half the corpus. Without
    that, the component with the more extreme operating point looks less biased purely because it
    has less room to differ, which is the same saturation trap `saturation()` guards elsewhere.
    """
    import statistics

    from untell.detectors.perplexity_burstiness import (
        _burstiness,
        _common_ratio,
        _sentences,
    )

    recs = []
    for row in rows:
        b = bands(row.get(axis)) if callable(bands) else bands.get(str(row.get(axis)))
        if not b:
            continue
        text = row["text"]
        recs.append((b, _common_ratio(text), _burstiness(_sentences(text))))
    if not recs:
        return {"error": "no rows fell into a band"}

    med_c = statistics.median(r[1] for r in recs)
    med_b = statistics.median(r[2] for r in recs)
    out = {"n": len(recs), "components": {}}
    for name, flag in (
        ("vocabulary", lambda r: r[1] >= med_c),   # predictable words => AI-like
        ("burstiness", lambda r: r[2] <= med_b),   # uniform sentences => AI-like
    ):
        agg: dict[str, list[int]] = {}
        for r in recs:
            d = agg.setdefault(r[0], [0, 0])
            d[0] += 1
            d[1] += bool(flag(r))
        groups = {}
        for band_name, (n, hits) in agg.items():
            lo, hi = wilson(hits, n)
            groups[band_name] = {"n": n, "fpr": round(hits / n, 4),
                                 "ci": [round(lo, 4), round(hi, 4)]}
        names = sorted(groups, key=lambda k: groups[k]["fpr"])
        # Separation is worst-versus-best and does not depend on how many bands there are. It was
        # computed only for exactly two, so a categorical axis reported `separated: null` beside a
        # 145x ratio -- a number with no significance attached, which is the shape of claim this
        # instrument exists to refuse.
        sep = None
        if len(names) >= 2:
            best, worst = groups[names[0]], groups[names[-1]]
            sep = worst["ci"][0] > best["ci"][1]
        out["components"][name] = {
            "groups": groups,
            "worst": names[-1] if names else None,
            "ratio": (round(groups[names[-1]]["fpr"] / groups[names[0]]["fpr"], 2)
                      if names and groups[names[0]]["fpr"] > 0 else None),
            "separated": sep,
        }
    a, b = out["components"].get("vocabulary"), out["components"].get("burstiness")
    out["opposed"] = bool(a and b and a["worst"] != b["worst"]
                          and a["separated"] and b["separated"])
    return out


def render_ablation(result: dict) -> str:
    if "error" in result:
        return result["error"]
    out = [f"COMPONENT ablation, n={result['n']} "
           f"(each component thresholded at its own median: equal power)", ""]
    for name, block in result["components"].items():
        out.append(f"  {name}")
        for g, v in sorted(block["groups"].items(), key=lambda kv: kv[1]["fpr"]):
            out.append(f"     {g:14} n={v['n']:<5} {v['fpr']:6.1%} "
                       f"[{v['ci'][0]:.1%}, {v['ci'][1]:.1%}]")
        out.append(f"     -> worst {block['worst']}, {block['ratio']}x, "
                   f"separated={block['separated']}")
    if result["opposed"]:
        out += ["", "  !! THE COMPONENTS ARE BIASED IN OPPOSITE DIRECTIONS, both separated at 95%.",
                "     They partly cancel in the combined score, so ANY aggregate fairness number",
                "     for this detector understates both. A black-box audit cannot see this."]
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
    ap.add_argument("--corpus", default="ellipse",
                    help="ellipse | asap | liang, or use --csv")
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
    ap.add_argument("--ablate", action="store_true",
                    help="audit each detector component separately (lite tier only)")
    ap.add_argument("--band-axis", default="Overall")
    a = ap.parse_args(argv)

    from eval.datasets import load_labelled, load_liang

    # Liang's populations are corpora, not columns in one CSV, so it loads separately -- and it
    # carries its own axes. `--by` is only overridden when the caller left it at the default,
    # because ELLIPSE's demographic axes do not exist here and would render as empty headings.
    if a.corpus == "liang" and a.csv is None:
        rows = load_liang()
        if a.by == ",".join(DEFAULT_AXES):
            a.by = "population,machine_edited"
    else:
        rows = load_labelled(a.corpus, csv_path=a.csv)
    if a.n and a.n < len(rows):
        random.Random(a.seed).shuffle(rows)
        rows = rows[: a.n]
    axes = tuple(x for x in a.by.split(",") if x)
    if a.ablate:
        # `ablate` takes either a callable or a value->band dict. The callable below bands a
        # NUMERIC axis into low/high, which is right for ELLIPSE's proficiency score and silently
        # wrong for a categorical one: `--ablate --band-axis population` on Liang's corpus
        # returned "no rows fell into a band", which reads like an empty result rather than a
        # mismatched flag. A categorical axis is already banded -- each value is its own band.
        numeric = 0
        for row in rows:
            try:
                float(row.get(a.band_axis))
            except (TypeError, ValueError):
                continue
            numeric += 1
        if numeric >= MIN_GROUP:
            def bands(v):
                try:
                    p = float(v)
                except (TypeError, ValueError):
                    return None
                return "low (<=2.5)" if p <= 2.5 else ("high (>=3.5)" if p >= 3.5 else None)
        else:
            counts: dict[str, int] = {}
            for row in rows:
                v = row.get(a.band_axis)
                if v is not None and str(v).strip().lower() not in _MISSING:
                    counts[str(v)] = counts.get(str(v), 0) + 1
            bands = {k: k for k, n in counts.items() if n >= MIN_GROUP}
            if not bands:
                print(f"--band-axis {a.band_axis!r}: no group reaches the {MIN_GROUP}-row floor "
                      f"(found {counts or 'no values at all'})", file=sys.stderr)
                return 2

        res = ablate(rows, a.band_axis, bands)
        print(json.dumps(res, indent=2) if a.json else render_ablation(res))
        return 0
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
