"""False-positive rate against text that *cannot* be AI-generated, with intervals.

Every false-positive number this repo publishes rests on a corpus someone labelled human. Labels can
be wrong, and HC3's human side is 2022-era forum prose — one register, one era, n in the dozens.

There is a cleaner probe, and it comes from the literature. Bohler et al.
(`doi:10.1097/SCS.0000000000012366 <https://doi.org/10.1097/SCS.0000000000012366>`_) scored 659
manuscripts published in **2014** and found ZeroGPT calling **8.6%** of them AI-generated. Text
published before the model existed cannot contain its output, so **the detector's score on it is a
false-positive rate directly** — no labelling, no annotator agreement, nothing to dispute.

This module builds that corpus for free. The ACL Anthology publishes abstracts as XML in its own
GitHub repository, so pre-2022 volumes give thousands of human-written paragraphs in a technical
register — the register detectors are worst on, per Pratama's discipline breakdown.

**The cutoff is a judgement and is stated rather than hidden.** Volumes through 2021 predate ChatGPT
(November 2022) and the mainstreaming of LLM writing assistants. GPT-2 and GPT-3 existed, and
Grammarly-class tools predate both, so "no model touched this" is not provable for any corpus — only
progressively less likely the further back you go. ``--max-year`` moves the line; 2021 is the
default because it maximises corpus size at low risk, and it is the same cutoff Pratama used and
justified.

Reported with **Wilson score intervals**, because the point of a larger corpus is to stop quoting
point estimates: a 17% rate on n=30 carries a 95% interval of roughly 7-35%, which is a different
claim from 17%.

    python -m eval.pre_llm_fpr --download --n 200      # fetch volumes, score 200 abstracts
    python -m eval.pre_llm_fpr --n 200 --tier lite
    python -m eval.pre_llm_fpr --n 200 --json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from pathlib import Path

from eval.litreview import download, load_abstracts

# Anthology collections published before ChatGPT. Extend freely; a volume that does not exist is
# skipped rather than failing the run.
PRE_LLM_VOLUMES: tuple[str, ...] = (
    "2020.acl", "2020.emnlp", "2020.findings", "2020.lrec", "2020.coling",
    "2021.acl", "2021.emnlp", "2021.findings", "2021.naacl",
)

_YEAR = re.compile(r"^(\d{4})\.")


def pre_llm_abstracts(cache: Path, min_words: int = 60, max_year: int = 2021) -> list[str]:
    """Human-written abstracts from Anthology volumes published no later than ``max_year``.

    ``min_words`` matters more than it looks: the literature puts the floor for any reliable verdict
    at roughly 50-100 words, and this repo's own measurements show one ensemble member flagging 100%
    of human text at 40 words. Scoring short abstracts would measure that instead of the corpus.
    """
    out: list[str] = []
    for paper in load_abstracts(cache):
        match = _YEAR.match(paper["id"])
        if not match or int(match.group(1)) > max_year:
            continue
        if len(paper["abstract"].split()) >= min_words:
            out.append(paper["abstract"])
    return out


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion.

    Wilson rather than the normal approximation because the rates here are small and the samples are
    not always large, which is exactly where the normal interval misbehaves — it can run below zero
    and it understates uncertainty near the boundary.
    """
    if total <= 0:
        return (0.0, 1.0)
    p = successes / total
    denominator = 1.0 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def probe(texts: list[str], tier: str = "lite") -> dict:
    """Score known-human text and report the false-positive rate under each aggregation rule."""
    from untell.scripts.score import score_text

    per_detector: dict[str, list[int]] = {}
    rules = {"any": 0, "majority": 0, "unanimous": 0}
    scored = 0
    for text in texts:
        result = score_text(text, tier=tier)
        spread = result.get("agreement")
        if not spread:
            continue
        scored += 1
        for rule in rules:
            rules[rule] += int(bool(spread[rule]))
        threshold = result["verdict_threshold"]
        for name, value in result["detectors"].items():
            if isinstance(value, (int, float)):
                per_detector.setdefault(name, []).append(int(value >= threshold))

    def _rate(flagged: int, total: int) -> dict:
        low, high = wilson_interval(flagged, total)
        return {
            "flagged": flagged,
            "n": total,
            "fpr": round(flagged / total, 4) if total else None,
            "ci95": [round(low, 4), round(high, 4)],
        }

    return {
        "n_scored": scored,
        "tier": tier,
        # How many detectors were live decides whether the three rules mean anything. With one, they
        # are the same number three times, and printing them as agreement would be the most
        # flattering possible way to be wrong.
        "detectors_scoring": len(per_detector),
        "by_rule": {rule: _rate(count, scored) for rule, count in rules.items()},
        "by_detector": {
            name: _rate(sum(hits), len(hits)) for name, hits in sorted(per_detector.items())
        },
    }


def _render(report: dict) -> str:
    lines = [
        f"Pre-LLM human abstracts scored: {report['n_scored']} (tier={report['tier']})",
        "Every flag below is a FALSE positive: this text predates the models.",
        "",
        f"{'aggregation rule':<22} {'FPR':>8}   95% CI",
    ]
    for rule, row in report["by_rule"].items():
        if row["fpr"] is None:
            continue
        ci = f"[{row['ci95'][0]:.1%}, {row['ci95'][1]:.1%}]"
        lines.append(f"{rule:<22} {row['fpr']:>7.1%}   {ci}")
    if report.get("detectors_scoring", 0) < 2:
        lines.append("")
        lines.append("NOTE: one detector scored, so the three rules above are the same measurement "
                     "printed three times.")
        lines.append("      They are not agreement. Use --tier full for a real spread.")
    lines += ["", f"{'detector':<22} {'FPR':>8}   95% CI"]
    for name, row in report["by_detector"].items():
        if row["fpr"] is None:
            continue
        ci = f"[{row['ci95'][0]:.1%}, {row['ci95'][1]:.1%}]"
        lines.append(f"{name:<22} {row['fpr']:>7.1%}   {ci}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=Path(".anthology-cache"))
    parser.add_argument("--download", action="store_true", help="fetch pre-LLM volumes first")
    parser.add_argument("--n", type=int, default=100, help="how many abstracts to score")
    parser.add_argument("--tier", default="lite")
    parser.add_argument("--min-words", type=int, default=60)
    parser.add_argument("--max-year", type=int, default=2021)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    if args.download:
        print(f"{download(args.cache, PRE_LLM_VOLUMES)} volume(s) cached", file=sys.stderr)

    texts = pre_llm_abstracts(args.cache, args.min_words, args.max_year)
    if not texts:
        print(f"no pre-{args.max_year + 1} abstracts in {args.cache} — run with --download first",
              file=sys.stderr)
        return 1
    random.Random(args.seed).shuffle(texts)
    report = probe(texts[: args.n], tier=args.tier)
    print(json.dumps(report, indent=2) if args.as_json else _render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
