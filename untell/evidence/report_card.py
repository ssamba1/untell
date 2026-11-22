"""A detector's report card: dated, versioned, reproducible — and diffable.

Detectors change their models without notice (Turnitin shipped one in February 2026, Pangram 4 in
2026), so a single accuracy number has a shelf life. A report card records what was measured, on
which corpus (fingerprinted), against which detector version, on which date — and
:func:`drift` compares two report cards so a silent model change shows up as a measured one.

Everything reported comes with its sample size and a 95% interval. A rate of 0 out of 40 is
reported as "0%, 95% CI 0–8.8%", never as "never wrong".
"""

from __future__ import annotations

import datetime as _dt
import random
from collections import defaultdict

from . import stats as S
from .corpus import Doc, corpus_fingerprint
from .scorers import Scorer
from .stability import measure_stability

__all__ = ["LENGTH_BUCKETS", "run_report_card", "drift", "render_report_card_markdown"]

LENGTH_BUCKETS = ((0, 150, "<150 words"), (150, 300, "150–299"), (300, 600, "300–599"),
                  (600, 10**9, "600+"))


def _bucket(words: int) -> str:
    for lo, hi, name in LENGTH_BUCKETS:
        if lo <= words < hi:
            return name
    return LENGTH_BUCKETS[-1][2]


def _rate(k: int, n: int) -> dict:
    if n == 0:
        return {"n": 0, "k": 0, "rate": None, "ci95": None}
    lo, hi = S.wilson_interval(k, n)
    return {"n": n, "k": k, "rate": k / n, "ci95": [lo, hi]}


def _quantiles(xs: list[float]) -> dict:
    if not xs:
        return {}
    s = sorted(xs)

    def q(p: float) -> float:
        i = (len(s) - 1) * p
        lo = int(i)
        hi = min(lo + 1, len(s) - 1)
        return s[lo] + (s[hi] - s[lo]) * (i - lo)

    return {"min": s[0], "p25": q(0.25), "median": q(0.5), "p75": q(0.75), "p95": q(0.95),
            "max": s[-1]}


def run_report_card(
    scorer: Scorer,
    docs: list[Doc],
    *,
    corpus_name: str = "corpus",
    detector_version: str | None = None,
    stability_sample: int = 20,
    slice_by: tuple[str, ...] = (),
    fpr_caps: tuple[float, ...] = (0.005, 0.01, 0.05),
    seed: int = 0,
    progress=None,
) -> dict:
    """Score every document; report FPR by slice, stability, and (with AI docs) recall@FPR."""
    from .brief import _WORDS, _version

    human = [d for d in docs if d["label"] == "human"]
    ai = [d for d in docs if d["label"] == "ai"]
    if not human:
        raise ValueError("a report card needs human-labelled documents")

    rows = []
    for i, d in enumerate(docs):
        v = scorer.verdict(d["text"], d["id"])
        rows.append({"id": d["id"], "label": d["label"], "group": d.get("group", ""),
                     "author": d.get("author"), "words": len(_WORDS.findall(d["text"])),
                     "score": v.score, "flagged": v.flagged,
                     **({"meta": {k: d["meta"][k] for k in slice_by if k in d.get("meta", {})}}
                        if slice_by else {})})
        if progress:
            progress(i + 1, len(docs))

    hrows = [r for r in rows if r["label"] == "human" and r["flagged"] is not None]
    unscored = sum(1 for r in rows if r["flagged"] is None)

    def fpr_of(rs: list[dict]) -> dict:
        return _rate(sum(1 for r in rs if r["flagged"]), len(rs))

    by_group: dict[str, list] = defaultdict(list)
    by_len: dict[str, list] = defaultdict(list)
    by_author: dict[str, list] = defaultdict(list)
    for r in hrows:
        by_group[r["group"]].append(r)
        by_len[_bucket(r["words"])].append(r)
        if r["author"]:
            by_author[str(r["author"])].append(r)

    overall = fpr_of(hrows)
    card: dict = {
        "kind": "untell.report_card",
        "schema": 1,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "untell_version": _version(),
        "detector": {**scorer.describe(), "version": detector_version or scorer.version},
        "corpus": {"name": corpus_name, "fingerprint": corpus_fingerprint(docs),
                   "human": len(human), "ai": len(ai), "unscored": unscored},
        "false_positive_rate": {
            "overall": overall,
            "by_group": {g: fpr_of(rs) for g, rs in sorted(by_group.items())},
            "by_length": {name: fpr_of(by_len[name]) for _, _, name in LENGTH_BUCKETS
                          if by_len.get(name)},
        },
        "human_score_distribution": _quantiles([r["score"] for r in hrows if r["score"] is not None]),
    }
    if slice_by:
        by_meta: dict[str, dict] = {}
        for field in slice_by:
            vals: dict[str, list] = defaultdict(list)
            for r in hrows:
                v = (r.get("meta") or {}).get(field)
                if v:
                    vals[v].append(r)
            by_meta[field] = {v: fpr_of(rs) for v, rs in sorted(vals.items())}
        card["false_positive_rate"]["by_meta"] = by_meta

    if by_author:
        flagged_people = sum(1 for rs in by_author.values() if any(r["flagged"] for r in rs))
        card["per_person"] = {
            "writers": len(by_author),
            "mean_documents": sum(len(v) for v in by_author.values()) / len(by_author),
            "writers_flagged_at_least_once": _rate(flagged_people, len(by_author)),
        }
    if overall["rate"] is not None:
        upper = overall["ci95"][1]
        card["honest_writer_projection"] = {
            "fpr_used": upper, "basis": "upper end of the 95% CI on the overall rate",
            "table": S.honest_writer_table(upper),
        }

    # Stability on a reproducible sample of human documents.
    rng = random.Random(seed)
    sample = rng.sample(human, min(stability_sample, len(human))) if stability_sample else []
    stab_rows = []
    for d in sample:
        res = measure_stability(d["text"], scorer, tiers=("null",)).to_dict()
        s = res["summary"].get("null", {})
        stab_rows.append({"id": d["id"], "base_flagged": res["base"]["flagged"],
                          "flips": s.get("flips", 0), "scored": s.get("variants_scored", 0),
                          "spread": s.get("score_spread")})
    if stab_rows:
        flips = sum(r["flips"] for r in stab_rows)
        scored = sum(r["scored"] for r in stab_rows)
        any_flip = sum(1 for r in stab_rows if r["flips"])
        card["null_edit_stability"] = {
            "documents": len(stab_rows),
            "variant_flip_rate": _rate(flips, scored),
            "documents_with_any_flip": _rate(any_flip, len(stab_rows)),
            "median_score_spread": _quantiles([r["spread"] for r in stab_rows
                                               if r["spread"] is not None]).get("median"),
        }

    if ai:
        ai_scores = [r["score"] for r in rows if r["label"] == "ai"]
        h_scores = [r["score"] for r in rows if r["label"] == "human"]
        arows = [r for r in rows if r["label"] == "ai" and r["flagged"] is not None]
        card["detection"] = {
            "auroc": S.auroc(ai_scores, h_scores),
            "recall_at_shipped_threshold": _rate(sum(1 for r in arows if r["flagged"]), len(arows)),
            "recall_at_fpr": [S.recall_at_fpr(ai_scores, h_scores, c) for c in fpr_caps],
        }
    card["documents"] = rows
    return card


def _overlap(a: list | None, b: list | None) -> bool:
    return bool(a and b and a[0] <= b[1] and b[0] <= a[1])


def drift(old: dict, new: dict) -> dict:
    """What changed between two report cards for the same detector.

    A change is flagged as ``significant`` when the two 95% intervals do not overlap — a
    deliberately conservative test, so a reported drift is one worth believing.
    """
    out = {"same_corpus": old["corpus"]["fingerprint"] == new["corpus"]["fingerprint"],
           "old": {"generated_at": old["generated_at"], "version": old["detector"].get("version")},
           "new": {"generated_at": new["generated_at"], "version": new["detector"].get("version")},
           "changes": []}

    def cmp(label: str, a: dict | None, b: dict | None) -> None:
        if not a or not b or a.get("rate") is None or b.get("rate") is None:
            return
        out["changes"].append({
            "metric": label, "old": a["rate"], "new": b["rate"], "delta": b["rate"] - a["rate"],
            "old_ci95": a["ci95"], "new_ci95": b["ci95"],
            "significant": not _overlap(a["ci95"], b["ci95"]),
        })

    fo, fn = old["false_positive_rate"], new["false_positive_rate"]
    cmp("false positive rate (overall)", fo["overall"], fn["overall"])
    for g in sorted(set(fo["by_group"]) & set(fn["by_group"])):
        cmp(f"false positive rate [{g}]", fo["by_group"][g], fn["by_group"][g])
    for g in sorted(set(fo["by_length"]) & set(fn["by_length"])):
        cmp(f"false positive rate [{g}]", fo["by_length"][g], fn["by_length"][g])
    so, sn = old.get("null_edit_stability"), new.get("null_edit_stability")
    if so and sn:
        cmp("null-edit verdict flip rate", so["variant_flip_rate"], sn["variant_flip_rate"])

    # Per-document verdict changes on an identical corpus: the most direct drift evidence there is.
    if out["same_corpus"]:
        a = {r["id"]: r["flagged"] for r in old.get("documents", [])}
        changed = [r["id"] for r in new.get("documents", [])
                   if r["id"] in a and a[r["id"]] is not None and r["flagged"] is not None
                   and a[r["id"]] != r["flagged"]]
        out["documents_whose_verdict_changed"] = changed
    out["significant"] = any(c["significant"] for c in out["changes"]) or bool(
        out.get("documents_whose_verdict_changed"))
    return out


def _fmt_rate(r: dict | None) -> str:
    if not r or r.get("rate") is None:
        return "n/a"
    lo, hi = r["ci95"]
    return f"{100 * r['rate']:.1f}% ({r['k']}/{r['n']}; 95% CI {100 * lo:.1f}–{100 * hi:.1f}%)"


def render_report_card_markdown(c: dict) -> str:
    d, corp, f = c["detector"], c["corpus"], c["false_positive_rate"]
    thr = "calibrated (the detector's own verdict)" if d["threshold"] is None else d["threshold"]
    L = [f"# Report card: {d['name']}", "",
         f"*{c['generated_at']} · untell {c['untell_version']} · detector version "
         f"{d.get('version') or 'not recorded'} · threshold {thr}*", "",
         f"Corpus **{corp['name']}** — {corp['human']} human, {corp['ai']} AI documents"
         f" ({corp['unscored']} unscored) · fingerprint `{corp['fingerprint'][:16]}…`", "",
         "## False positives on human writing", "",
         f"**Overall:** {_fmt_rate(f['overall'])}", "",
         "| slice | false-positive rate |", "|---|---|"]
    for g, r in f["by_group"].items():
        L.append(f"| group: {g} | {_fmt_rate(r)} |")
    for g, r in f["by_length"].items():
        L.append(f"| length: {g} | {_fmt_rate(r)} |")
    for field, vals in (f.get("by_meta") or {}).items():
        for v, r in vals.items():
            L.append(f"| {field}: {v} | {_fmt_rate(r)} |")
    L.append("")
    if c.get("per_person"):
        pp = c["per_person"]
        L += [f"**Per person:** {_fmt_rate(pp['writers_flagged_at_least_once'])} of "
              f"{pp['writers']} writers (mean {pp['mean_documents']:.1f} documents each) were "
              "flagged at least once.", ""]
    if c.get("honest_writer_projection"):
        hp = c["honest_writer_projection"]
        L += [f"Projected for honest writers at {100 * hp['fpr_used']:.2f}% per document "
              f"({hp['basis']}):", "", "| documents | P(≥1 false flag) | per 1,000 writers |",
              "|---:|---:|---:|"]
        for r in hp["table"]:
            L.append(f"| {r['documents']} | {100 * r['p_at_least_one_false_flag']:.1f}% | "
                     f"{r['flagged_per_1000']:.0f} |")
        L.append("")
    st = c.get("null_edit_stability")
    if st:
        spread = st["median_score_spread"]
        spread_s = "n/a" if spread is None else f"{spread:.3f}"
        L += ["## Verdict stability under formatting-only edits", "",
              f"- variant-level flip rate: {_fmt_rate(st['variant_flip_rate'])}",
              f"- documents with at least one flip: {_fmt_rate(st['documents_with_any_flip'])}",
              f"- median score spread across a document's variants: {spread_s}", ""]
    det = c.get("detection")
    if det:
        auc = "n/a" if det["auroc"] is None else f"{det['auroc']:.3f}"
        L += ["## Detection (AI documents)", "", f"- AUROC: {auc}",
              f"- recall at the shipped threshold: {_fmt_rate(det['recall_at_shipped_threshold'])}"]
        for r in det["recall_at_fpr"]:
            rec = "n/a" if r["recall"] is None else f"{100 * r['recall']:.1f}%"
            L.append(f"- recall with false positives capped at {100 * r['max_fpr']:.1f}%: {rec}")
        L.append("")
    return "\n".join(L) + "\n"
