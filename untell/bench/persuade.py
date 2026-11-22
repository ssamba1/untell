"""PERSUADE 2.0 as untell corpora: US student essays (grades 6-12) with writer demographics.

Crossley, Baffour, Tian, Franklin, Benner & Boser, "A large-scale corpus for assessing written
argumentation: PERSUADE 2.0", Assessing Writing 61 (2024); data CC BY 4.0
(https://github.com/scrosseye/persuade_corpus_2.0). 25,996 argumentative essays written
2010-2020, before any tool that could have written them, each with the writer's English-learner
status, grade, race/ethnicity and economic status.

Every essay is assigned to the FIT or EVAL half by a hash of its id, so a calibration fitted on
one half can never have seen an essay it is evaluated on. Samples are drawn per English-learner
status so both groups are represented whatever their share of the corpus.

    python -m untell.bench.persuade train.csv validation.csv test.csv --out persuade \\
        --fit-per-group 300 --eval-per-group 400
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from pathlib import Path

SOURCE = "https://github.com/scrosseye/persuade_corpus_2.0"
META = ("ell_status", "grade_level", "race_ethnicity", "economically_disadvantaged",
        "student_disability_status", "gender", "task", "prompt_name")


def half(essay_id: str) -> str:
    return "fit" if hashlib.sha256(essay_id.encode()).digest()[0] < 128 else "eval"


def load(paths: list[str]) -> list[dict]:
    csv.field_size_limit(10**9)
    seen: dict[str, dict] = {}
    for p in paths:
        with open(p, encoding="utf-8", errors="replace", newline="") as fh:
            for r in csv.DictReader(fh):
                eid = (r.get("essay_id_comp") or "").strip()
                text = (r.get("full_text") or "").strip()
                ell = (r.get("ell_status") or "").strip()
                if not eid or not text or ell not in ("Yes", "No") or eid in seen:
                    continue
                seen[eid] = {
                    "id": f"persuade:{eid}", "text": text, "label": "human",
                    "group": "ell" if ell == "Yes" else "non-ell", "source": SOURCE,
                    "meta": {k: (r.get(k) or "").strip() for k in META},
                }
    return list(seen.values())


def sample(docs: list[dict], which: str, per_group: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    out = []
    for g in ("ell", "non-ell"):
        pool = sorted((d for d in docs if d["group"] == g and half(d["id"]) == which),
                      key=lambda d: d["id"])
        out += rng.sample(pool, min(per_group, len(pool)))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m untell.bench.persuade", description=__doc__.split("\n\n")[0])
    ap.add_argument("csv", nargs="+", help="PERSUADE 2.0 CSV files (with demographic columns)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fit-per-group", type=int, default=300)
    ap.add_argument("--eval-per-group", type=int, default=400)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    docs = load(args.csv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for which, n in (("fit", args.fit_per_group), ("eval", args.eval_per_group)):
        rows = sample(docs, which, n, args.seed)
        with open(out / f"persuade-{which}.jsonl", "w", encoding="utf-8") as fh:
            for d in rows:
                fh.write(json.dumps(d, ensure_ascii=False) + "\n")
        print(f"{which}: {len(rows)} essays", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
