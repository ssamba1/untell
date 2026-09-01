"""The arm where detectors actually fail: human text an LLM polished, scored per subgroup.

Every false-positive measurement in this repo scores *unedited* human writing. The published
evidence says that is the easy case and not the one people are accused over.

Pratama (*PeerJ CS*, `doi:10.7717/peerj-cs.2953 <https://doi.org/10.7717/peerj-cs.2953>`_) scored
three detectors on 72 abstracts in three conditions. On clean human-vs-AI, GPTZero reached **97.22%
accuracy at 0.00% false positives**. On the *same authors' abstracts after an LLM improved the
readability* it became the **most biased** of the three, over-detecting **25% of non-native authors
against 11% of native ones** (Welch's t = -2.115, p = 0.036). A detector can be flawless on the
benchmark everyone runs and unfair on the only case that matters, and an audit that stops at
human-vs-AI cannot see it.

This module runs that arm here. The dataset is the author's own, MIT-licensed, fetched on demand
rather than vendored:

    https://github.com/ahmadrpratama/ai-text-detection-bias

It carries, for each of 72 articles published in **2021** — before ChatGPT, so the originals are
human by construction — the original abstract, two fully AI-generated versions, and two
**AI-assisted** versions where an LLM was asked only to improve clarity and readability. Authors are
stratified 36 native / 36 non-native by institutional country, across three discipline groups.

⚠️ **The subgroup label is a proxy, and a criticised one.** ``Status`` is assigned from the authors'
institutional country, so it separates "affiliated in an Anglosphere country" from "affiliated
elsewhere" — not native from non-native speakers. Du & Koga
(`doi:10.1016/j.jdin.2025.10.017 <https://doi.org/10.1016/j.jdin.2025.10.017>`_) name exactly this
substitution as a defect: "many U.S.-affiliated authors trained or grew up in non-English
environments, affiliation alone may not capture language background," and they ask for a
pre-specified sampling frame instead. Every subgroup number this module prints inherits that
misclassification. It is reported rather than hidden, and a corpus with self-reported language
background would be strictly better evidence.

Two things this reports that a single verdict cannot:

* **Over-detection on assisted text, per subgroup.** A human wrote it; an assistant polished it.
  Every flag is a false accusation of a person who did the work.
* **The gap between subgroups**, with Wilson intervals, because a difference inside the noise is not
  a finding — and with 36 per group the noise is wide.

    python -m eval.assisted_fairness --download
    python -m eval.assisted_fairness --n 24 --tier lite
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.request
from pathlib import Path

from eval.pre_llm_fpr import wilson_interval

DATA_URL = ("https://raw.githubusercontent.com/ahmadrpratama/"
            "ai-text-detection-bias/main/abstracts.csv")
RESULTS_URL = ("https://raw.githubusercontent.com/ahmadrpratama/"
               "ai-text-detection-bias/main/results.csv")

# A tool's own verdict, as it labelled it. "mixed" counts as a flag: an author told their abstract is
# partly AI has still been accused, and the published FAR of 44.44% only reproduces when it is
# counted — see `published_spread`.
FLAG_LABELS = ("ai", "mixed")

# Column -> arm name. The originals predate ChatGPT; the assisted columns are the same human text
# after an LLM improved its readability, which is the condition this module exists to score.
ARMS: dict[str, str] = {
    "Abstract": "human",
    "AI-Assisted ChatGPT": "assisted_chatgpt",
    "AI-Assisted Gemini": "assisted_gemini",
    "AI-Generated ChatGPT": "generated_chatgpt",
    "AI-Generated Gemini": "generated_gemini",
}

# Arms where a flag is a false accusation of a human author rather than a correct detection.
HUMAN_AUTHORED = ("human", "assisted_chatgpt", "assisted_gemini")


def fetch(cache: Path) -> Path:
    """Download the MIT-licensed dataset if it is not already cached. Returns the file path."""
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / "pratama_abstracts.csv"
    if target.exists() and target.stat().st_size > 1000:
        return target
    with urllib.request.urlopen(DATA_URL, timeout=180) as response:  # noqa: S310
        target.write_bytes(response.read())
    return target


def load_rows(path: Path) -> list[dict[str, str]]:
    """Rows that carry an author status and a usable original abstract."""
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [r for r in rows if (r.get("Status") or "").strip() and (r.get("Abstract") or "").strip()]


def evaluate(rows: list[dict[str, str]], tier: str = "lite") -> dict:
    """Flag rates per arm, split by author status, with intervals."""
    from untell.scripts.score import score_text

    tally: dict[tuple[str, str], list[int]] = {}
    for row in rows:
        status = row["Status"].strip()
        for column, arm in ARMS.items():
            text = (row.get(column) or "").strip()
            if len(text.split()) < 50:
                continue
            result = score_text(text, tier=tier)
            if not result.get("agreement"):
                continue
            tally.setdefault((arm, status), []).append(int(bool(result["flagged"])))

    def _rate(hits: list[int]) -> dict:
        low, high = wilson_interval(sum(hits), len(hits))
        return {"flagged": sum(hits), "n": len(hits),
                "rate": round(sum(hits) / len(hits), 4) if hits else None,
                "ci95": [round(low, 4), round(high, 4)]}

    arms: dict[str, dict] = {}
    for (arm, status), hits in tally.items():
        arms.setdefault(arm, {})[status] = _rate(hits)
    for arm, by_status in arms.items():
        pooled = [h for (a, _), hs in tally.items() if a == arm for h in hs]
        by_status["all"] = _rate(pooled)
    return {"tier": tier, "arms": arms,
            "false_accusation_arms": list(HUMAN_AUTHORED)}


def published_spread(results_csv: Path, text_type: str = "original") -> dict:
    """The aggregation spread on three real detectors, from the study's own per-tool scores.

    This repo's ensemble cannot demonstrate the spread wherever its ML detectors are unavailable:
    with one detector live, union, majority and unanimity are the same number. The published data
    can, because it carries GPTZero, ZeroGPT and DetectGPT verdicts on all 72 abstracts.

    On ``text_type="original"`` — human abstracts published in 2021 — this reproduces Pratama's
    reported **FAR 44.44%** and **MFAR 4.17%** exactly, which is what makes it a check on
    :func:`untell.scripts.score.agreement` rather than a restatement of it.

    The result it produces is the argument for reporting a spread at all: the union rule accuses
    **32 of 72** authors, and requiring all three tools to agree accuses **none**.
    """
    with results_csv.open(encoding="utf-8", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("text") == text_type]
    by_article: dict[str, list[bool]] = {}
    for row in rows:
        label = (row.get("label") or "").strip().lower()
        by_article.setdefault(row["article"], []).append(label in FLAG_LABELS)
    articles = [v for v in by_article.values() if v]
    n = len(articles)
    counts = {
        "any": sum(1 for v in articles if any(v)),
        "majority": sum(1 for v in articles if sum(v) * 2 > len(v)),
        "unanimous": sum(1 for v in articles if all(v)),
    }
    out = {"text_type": text_type, "n_articles": n, "rules": {}}
    for rule, flagged in counts.items():
        low, high = wilson_interval(flagged, n)
        out["rules"][rule] = {"flagged": flagged, "n": n,
                              "rate": round(flagged / n, 4) if n else None,
                              "ci95": [round(low, 4), round(high, 4)]}
    return out


def _render(report: dict) -> str:
    lines = [
        f"Author-stratified flag rates (tier={report['tier']}).",
        "Originals are 2021 abstracts — pre-ChatGPT — so on the human and assisted arms",
        "every flag is a false accusation of the person who wrote it.",
        "Native/Non-Native here is INSTITUTIONAL COUNTRY, not language background — a proxy the",
        "literature criticises (doi:10.1016/j.jdin.2025.10.017). Read subgroup rows accordingly.",
        "",
        f"{'arm':<20} {'group':<12} {'n':>4} {'flagged':>8}   95% CI",
    ]
    for arm in ARMS.values():
        rows = report["arms"].get(arm)
        if not rows:
            continue
        marker = "  <- false accusations" if arm in report["false_accusation_arms"] else ""
        lines.append(f"{arm}{marker}")
        for group in ("Native", "Non-Native", "all"):
            row = rows.get(group)
            if not row or row["rate"] is None:
                continue
            ci = f"[{row['ci95'][0]:.1%}, {row['ci95'][1]:.1%}]"
            lines.append(f"{'':<20} {group:<12} {row['n']:>4} {row['rate']:>7.1%}   {ci}")
    lines.append("")
    lines.append("Overlapping intervals between groups mean the gap is not established at this n.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path(".fairness-cache"))
    parser.add_argument("--download", action="store_true", help="fetch the dataset first")
    parser.add_argument("--n", type=int, default=24, help="how many articles to score")
    parser.add_argument("--tier", default="lite")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    path = args.cache / "pratama_abstracts.csv"
    if args.download or not path.exists():
        try:
            path = fetch(args.cache)
        except Exception as exc:  # noqa: BLE001
            print(f"could not fetch the dataset: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
    rows = load_rows(path)
    if not rows:
        print(f"no usable rows in {path}", file=sys.stderr)
        return 1
    report = evaluate(rows[: args.n], tier=args.tier)
    print(json.dumps(report, indent=2) if args.as_json else _render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
