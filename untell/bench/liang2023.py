"""Import Liang et al. (2023)'s recorded detector scores as untell corpora and report cards.

Liang, Yuksekgonul, Mao, Wu & Zou, "GPT detectors are biased against non-native English
writers", Patterns 4(7), 2023 — data at https://github.com/Weixin-Liang/ChatGPT-Detector-Bias
(MIT licence). The repository records, for every essay, the score seven detectors gave it in
early 2023: GPTZero, Originality.ai, ZeroGPT, Sapling, Crossplag, Quillbot and the OpenAI
RoBERTa detector hosted on Hugging Face.

Those recorded scores are exactly what untell's ``manual:`` scorer reads, so this module turns
the dataset into one corpus (``corpus.jsonl``) and one score sheet per detector
(``scores/<detector>.csv``, keyed by document id), then runs a report card per detector. The
result is a dated, reproducible audit of seven commercial detectors' 2023 versions, split by
writer population — the slices where detectors are known to fail.

The 2023 scores do not describe these detectors today. They are a baseline: re-scoring the same
essays against today's versions (``untell report-card --detector gptzero``) and running
``untell drift`` against these cards measures what changed.

    python -m untell.bench.liang2023 /path/to/ChatGPT-Detector-Bias --out docs/observatory/liang-2023
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# folder -> (group name, label). Human-written essays edited by GPT (the paper's interventions,
# `TOEFL_gpt4polished_91` and `HewlettStudentEssay_GPTsimplify_88`) are neither human nor AI
# authored, so they are left out of both sides rather than forced into one.
GROUPS: dict[str, tuple[str, str]] = {
    "Human_Data/TOEFL_real_91": ("toefl-non-native", "human"),
    "Human_Data/HewlettStudentEssay_real_88": ("us-8th-grade", "human"),
    "Human_Data/CollegeEssay_real_70": ("us-college-admissions", "human"),
    "Human_Data/CS224N_real_145": ("stanford-cs224n-abstracts", "human"),
    "GPT_Data/CS224N_gpt3_145": ("gpt3-cs224n-abstracts", "ai"),
    "GPT_Data/CS224N_gpt3PromptEng_145": ("gpt3-cs224n-abstracts-prompted", "ai"),
    "GPT_Data/CollegeEssay_gpt3_31": ("gpt3-college-essays", "ai"),
    "GPT_Data/CollegeEssay_gpt3PromptEng_31": ("gpt3-college-essays-prompted", "ai"),
}

# file stem in the dataset -> untell's name for the detector
DETECTORS: dict[str, str] = {
    "GPTZero": "gptzero-2023",
    "OriginalityAI": "originality-2023",
    "ZeroGPT": "zerogpt-2023",
    "Sapling": "sapling-2023",
    "Crossplag": "crossplag-2023",
    "Quil": "quillbot-2023",
    "HFOpenAI": "openai-roberta-2023",
}

SOURCE = "https://github.com/Weixin-Liang/ChatGPT-Detector-Bias"


def build(repo: str | Path, out: str | Path) -> dict:
    """Write ``corpus.jsonl`` and ``scores/<detector>.csv`` under ``out``; return a summary."""
    base = Path(repo) / "Data_and_Results"
    if not base.is_dir():
        raise FileNotFoundError(f"{repo} does not look like ChatGPT-Detector-Bias (no Data_and_Results/)")
    out = Path(out)
    (out / "scores").mkdir(parents=True, exist_ok=True)
    docs: list[dict] = []
    sheets: dict[str, list[tuple[str, float]]] = {name: [] for name in DETECTORS.values()}
    orphans: dict[str, int] = {}
    for folder, (group, label) in GROUPS.items():
        d = base / folder
        data = json.loads((d / "data.json").read_text(encoding="utf-8"))
        ids = [f"{d.name}/{i:03d}" for i in range(len(data))]
        for doc_id, rec in zip(ids, data):
            docs.append({"id": doc_id, "text": rec["document"], "label": label, "group": group,
                         "source": SOURCE})
        for stem, name in DETECTORS.items():
            f = d / f"{stem}.json"
            if not f.exists():
                continue
            scores = json.loads(f.read_text(encoding="utf-8"))
            if len(scores) != len(data):
                raise ValueError(f"{f}: {len(scores)} scores for {len(data)} documents")
            # Score files are NOT always in data.json's order (CS224N's GPTZero file differs from
            # position 3 on), so align by the document text each score records. Every score must
            # match exactly one document, or the whole file is refused.
            # The TOEFL set contains duplicate essays, so a text can map to several ids: each
            # score goes to the next unclaimed id with that text (identical text, identical input).
            by_text: dict[str, list[str]] = {}
            for doc_id, rec in zip(ids, data):
                by_text.setdefault(" ".join(rec["document"].split()), []).append(doc_id)
            # A score whose recorded text matches no essay is dropped and counted, not guessed:
            # in CS224N, six GPTZero scores were recorded for the placeholder "Project summaries
            # unavailable" rather than for an abstract. Those essays are left unscored.
            for s in scores:
                pending = by_text.get(" ".join(str(s.get("document", "")).split()))
                if not pending:
                    orphans[name] = orphans.get(name, 0) + 1
                    continue
                doc_id = pending.pop(0)
                if s.get("score") is not None:
                    sheets[name].append((doc_id, float(s["score"])))
    with open(out / "corpus.jsonl", "w", encoding="utf-8") as fh:
        for d in docs:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    for name, rows in sheets.items():
        with open(out / "scores" / f"{name}.csv", "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "score"])
            w.writerows(rows)
    texts = [" ".join(d["text"].split()) for d in docs]
    return {"documents": len(docs), "duplicate_texts": len(texts) - len(set(texts)),
            "scored": {k: len(v) for k, v in sheets.items()},
            "scores_matching_no_document": orphans}


def run_cards(out: str | Path, threshold: float = 0.5) -> list[dict]:
    """A report card per detector over the built corpus, written as ``cards/<detector>.{json,md}``."""
    from untell.evidence.corpus import load_corpus
    from untell.evidence.report_card import render_report_card_markdown, run_report_card
    from untell.evidence.scorers import resolve_scorer

    out = Path(out)
    docs = load_corpus(out / "corpus.jsonl")
    (out / "cards").mkdir(exist_ok=True)
    cards = []
    for name in DETECTORS.values():
        sheet = out / "scores" / f"{name}.csv"
        scorer = resolve_scorer(f"manual:{sheet}", threshold)
        scorer.name = name
        card = run_report_card(scorer, docs, corpus_name="liang2023", detector_version="early 2023 "
                               "(scores recorded by Liang et al.)", stability_sample=0)
        card["detector"]["source"] = SOURCE
        (out / "cards" / f"{name}.json").write_text(json.dumps(card, separators=(",", ":")) + "\n", encoding="utf-8")
        (out / "cards" / f"{name}.md").write_text(render_report_card_markdown(card), encoding="utf-8")
        cards.append(card)
    return cards


def summary_table(cards: list[dict]) -> str:
    """Markdown: false-positive rate per detector per human group, with 95% intervals."""
    groups = [g for g, lab in GROUPS.values() if lab == "human"]
    head = "| detector | " + " | ".join(groups) + " | AUROC |"
    lines = [head, "|---|" + "---|" * len(groups) + "---:|"]
    for c in cards:
        cells = []
        for g in groups:
            r = c["false_positive_rate"]["by_group"].get(g)
            if not r or r.get("rate") is None:
                cells.append("—")
                continue
            lo, hi = r["ci95"]
            cells.append(f"**{100 * r['rate']:.0f}%** ({r['k']}/{r['n']}; {100 * lo:.0f}–{100 * hi:.0f})")
        auc = (c.get("detection") or {}).get("auroc")
        lines.append(f"| {c['detector']['name']} | " + " | ".join(cells)
                     + f" | {'—' if auc is None else f'{auc:.3f}'} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m untell.bench.liang2023", description=__doc__.split("\n\n")[0])
    ap.add_argument("repo", help="a clone of github.com/Weixin-Liang/ChatGPT-Detector-Bias")
    ap.add_argument("--out", default="liang-2023", help="output folder")
    ap.add_argument("--threshold", type=float, default=0.5)
    args = ap.parse_args(argv)
    info = build(args.repo, args.out)
    print(f"{info['documents']} documents ({info['duplicate_texts']} duplicate texts); "
          f"scores per detector: {info['scored']}; dropped (text matched no essay): "
          f"{info['scores_matching_no_document']}", file=sys.stderr)
    cards = run_cards(args.out, args.threshold)
    table = summary_table(cards)
    (Path(args.out) / "summary.md").write_text(table, encoding="utf-8")
    sys.stdout.write(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
