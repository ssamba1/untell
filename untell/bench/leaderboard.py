"""Build the open-detector leaderboard page from the report cards in a folder.

    python -m untell.bench.leaderboard docs/observatory/open-detectors --out docs/observatory/open-detectors.md

Every number on the page is read from a card or a trailing-space result in that folder; nothing is
typed by hand, so the page cannot drift from the data it summarises.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _pct(r: dict | None) -> str:
    if not r or r.get("rate") is None:
        return "—"
    return f"{100 * r['rate']:.1f}% ({r['k']}/{r['n']})"


def _pct_plain(x: float | None) -> str:
    return "—" if x is None else f"{100 * x:.1f}%"


def build(folder: Path) -> str:
    cards = []
    for p in sorted(folder.glob("*.json")):
        if p.name.endswith(".trailing-space.json"):
            continue
        card = json.loads(p.read_text(encoding="utf-8"))
        ts_path = p.with_name(p.stem + ".trailing-space.json")
        ts = json.loads(ts_path.read_text(encoding="utf-8"))["summary"] if ts_path.exists() else None
        cards.append((p.stem, card, ts))

    L = ["# Open AI-text detectors, audited", "",
         "Each detector run as its Hugging Face model card says (`hf:<model>`: raw text, truncated at "
         "the model's limit), flagged at its default 0.5, on human writing from before 2022 and on "
         "GPT-3 text. Every figure is read from the report cards in "
         f"[`{folder.name}/`]({folder.name}/) by `untell/bench/leaderboard.py`.", "",
         "## False positives on human writing", "",
         "| detector | all human | TOEFL, non-native | US 8th grade | US college | CS224N abstracts "
         "| PERSUADE: English learners | PERSUADE: others |",
         "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for _name, c, _ in cards:
        g = c["false_positive_rate"]["by_group"]
        L.append(f"| `{c['detector']['name'].removeprefix('hf:')}` | "
                 f"{_pct(c['false_positive_rate']['overall'])} | {_pct(g.get('toefl-non-native'))} | "
                 f"{_pct(g.get('us-8th-grade'))} | {_pct(g.get('us-college-admissions'))} | "
                 f"{_pct(g.get('stanford-cs224n-abstracts'))} | {_pct(g.get('ell'))} | "
                 f"{_pct(g.get('non-ell'))} |")
    L += ["", "## Detection, stability and one trailing space", "",
          "| detector | AUROC | recall at 0.5 | recall, FPR ≤ 1% | formatting-only flips "
          "| trailing space: TOEFL flags cleared | trailing space: GPT-3 flags cleared |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for _name, c, ts in cards:
        det = c.get("detection") or {}
        at1 = next((r for r in det.get("recall_at_fpr", []) if r["max_fpr"] == 0.01), {})
        st = (c.get("null_edit_stability") or {}).get("variant_flip_rate")

        def cleared(group: str, ts: dict | None = ts) -> str:
            s = (ts or {}).get("groups", {}).get(group)
            if not s or not s["flagged_original"]:
                return "—"
            return (f"{s['flagged_original'] - s['flagged_with_trailing_space']} of "
                    f"{s['flagged_original']}")

        auc = det.get("auroc")
        L.append(f"| `{c['detector']['name'].removeprefix('hf:')}` | "
                 f"{'—' if auc is None else f'{auc:.3f}'} | {_pct(det.get('recall_at_shipped_threshold'))} | "
                 f"{_pct_plain(at1.get('recall'))} | {_pct(st)} | {cleared('toefl-non-native')} | "
                 f"{cleared('gpt3-cs224n-abstracts')} |")
    L += ["", "## By race (PERSUADE held-out half, US students)", ""]
    races = sorted({r for _, c, _ in cards
                    for r in c["false_positive_rate"].get("by_meta", {}).get("race_ethnicity", {})})
    if races:
        L += ["| detector | " + " | ".join(races) + " |", "|---|" + "---:|" * len(races)]
        for _name, c, _ in cards:
            by = c["false_positive_rate"].get("by_meta", {}).get("race_ethnicity", {})
            L.append(f"| `{c['detector']['name'].removeprefix('hf:')}` | "
                     + " | ".join(_pct(by.get(r)) for r in races) + " |")
    L += ["", "Rates on the 'all human' column pool corpora of different sizes and registers; read the "
          "per-corpus columns. 'Flags cleared' counts texts flagged as written and not flagged once one "
          "space is appended (identical words). Card details, including 95% intervals for every rate, "
          "are in each detector's `.md` card.", ""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m untell.bench.leaderboard")
    ap.add_argument("folder")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    Path(args.out).write_text(build(Path(args.folder)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
