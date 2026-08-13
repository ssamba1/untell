"""Build fixed corpus files, so a measurement can name the text it measured.

Two things this project has paid for twice. Detectors read only the first few hundred words,
which made every result a statement about openings rather than documents until windowed
scoring landed — and nothing re-checks that by length. And a detector's separation says
nothing about its false-positive rate: an audit once reported AUROC 0.999 while the shipped
threshold flagged 95% of HUMAN text.

Both need corpora the dataset loaders do not hand you: text bucketed by length, and human
text on its own. Written to disk so the same file can be measured again in a month and the
comparison means something.

    python .claude/corpus.py build --dataset hc3 --bucket long --n 10
    python .claude/corpus.py build --dataset hc3 --bucket human --n 20
    python .claude/corpus.py list
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".claude" / "corpora"
sys.path.insert(0, str(ROOT))

# The cut at 380 is not arbitrary: it is roughly where the detectors used to stop reading, so
# `long` is the bucket that can tell you whether windowed scoring actually holds.
BUCKETS = {
    "short": (60, 150, "openings only - what a detector sees of anything"),
    "medium": (150, 380, "inside the old truncation limit"),
    "long": (380, 10_000, "past where detectors used to stop reading"),
    "human": (60, 10_000, "human text alone, for the false-positive rate at the shipped bar"),
}


def build(dataset: str, bucket: str, n: int) -> int:
    from eval.datasets import load_pairs

    low, high, why = BUCKETS[bucket]
    # 40x the ask because the length buckets are thin: HC3 answers are mostly a few hundred
    # words, so `long` rejects most of what it is shown.
    pairs = load_pairs(dataset, n=max(n * 40, 200), min_words=low)
    side = 0 if bucket == "human" else 1
    texts, seen = [], set()
    for pair in pairs:
        text = pair[side].strip()
        words = len(text.split())
        if not (low <= words < high) or text in seen:
            continue
        seen.add(text)
        # Blank lines separate documents in the corpus format, so they cannot survive inside one.
        texts.append(" ".join(text.split()))
        if len(texts) >= n:
            break

    if not texts:
        sys.exit(f"REFUSED: no {dataset} text in the {bucket} range ({low}-{high} words). "
                 "The bucket is empty for this dataset - say so, do not substitute another.")
    path = OUT / f"{dataset}-{bucket}.txt"
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(texts) + "\n", encoding="utf-8")

    lengths = sorted(len(t.split()) for t in texts)
    print(f"wrote {path.relative_to(ROOT)}")
    print(f"  {len(texts)} of {n} requested   {why}")
    print(f"  words: min {lengths[0]}, median {lengths[len(lengths) // 2]}, max {lengths[-1]}")
    if len(texts) < n:
        # Reported, never padded. A corpus quietly topped up from a neighbouring bucket
        # answers a different question than the one on the label.
        print(f"  SHORT by {n - len(texts)}: this dataset does not hold that much text in "
              "this range. Quote the count you got, not the count you asked for.")
    return 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("build")
    b.add_argument("--dataset", default="hc3", choices=["hc3", "raid", "mage"])
    b.add_argument("--bucket", required=True, choices=sorted(BUCKETS))
    b.add_argument("--n", type=int, default=10)
    sub.add_parser("list")
    a = ap.parse_args()

    if a.cmd == "build":
        return build(a.dataset, a.bucket, a.n)
    if not OUT.exists():
        print("no corpora built yet")
        return 0
    for f in sorted(OUT.glob("*.txt")):
        docs = [d for d in f.read_text(encoding="utf-8").split("\n\n") if d.strip()]
        words = sorted(len(d.split()) for d in docs)
        print(f"{f.name:24} {len(docs):>3} docs   words {words[0]}-{words[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
