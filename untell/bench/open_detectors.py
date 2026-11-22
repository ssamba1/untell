"""Audit the open AI-text detectors people install from Hugging Face.

For each model: a report card on a corpus (false positives by writer group with 95% intervals,
recall, AUROC, null-edit stability on a sample) and the trailing-space test, each model run as its
model card says (``hf:<model>``: raw text, truncated at the model's limit).

    python -m untell.bench.open_detectors corpus.jsonl --out docs/observatory/open-detectors \\
        --model fakespot-ai/roberta-base-ai-text-detection-v1 --model desklib/ai-text-detector-v1.01
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from untell.bench.trailing_space import measure, summarise
from untell.evidence.corpus import load_corpus
from untell.evidence.report_card import render_report_card_markdown, run_report_card
from untell.evidence.scorers import resolve_scorer


def slug(model: str) -> str:
    return model.replace("/", "__")


def audit(model: str, docs: list[dict], out: Path, corpus_name: str, stability_sample: int,
          trailing_groups: set[str] | None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    sc = resolve_scorer(f"hf:{model}", 0.5)

    def prog(i: int, n: int) -> None:
        if i % 100 == 0 or i == n:
            print(f"  {model}: card {i}/{n}", file=sys.stderr, flush=True)

    card = run_report_card(sc, docs, corpus_name=corpus_name, stability_sample=stability_sample,
                           progress=prog)
    (out / f"{slug(model)}.json").write_text(json.dumps(card, separators=(",", ":")) + "\n",
                                             encoding="utf-8")
    (out / f"{slug(model)}.md").write_text(render_report_card_markdown(card), encoding="utf-8")
    tdocs = [d for d in docs if not trailing_groups or d.get("group") in trailing_groups]
    rows = measure(tdocs, f"hf:{model}", 0.5,
                   lambda det, i, n: (i % 100 == 0 or i == n)
                   and print(f"  {model}: trailing {i}/{n}", file=sys.stderr, flush=True))
    trailing = {"summary": summarise(rows), "documents": rows}
    (out / f"{slug(model)}.trailing-space.json").write_text(
        json.dumps(trailing, separators=(",", ":")) + "\n", encoding="utf-8")
    return {"card": card, "trailing": trailing["summary"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m untell.bench.open_detectors",
                                 description=__doc__.split("\n\n")[0])
    ap.add_argument("corpus")
    ap.add_argument("--model", action="append", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", default="corpus")
    ap.add_argument("--stability-sample", type=int, default=15)
    ap.add_argument("--trailing-group", action="append",
                    help="groups to run the trailing-space test on (default: all)")
    args = ap.parse_args(argv)
    docs = load_corpus(args.corpus)
    for m in args.model:
        res = audit(m, docs, Path(args.out), args.name, args.stability_sample,
                    set(args.trailing_group) if args.trailing_group else None)
        print(f"DONE {m} overall FPR {res['card']['false_positive_rate']['overall']['rate']:.3f}",
              flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
