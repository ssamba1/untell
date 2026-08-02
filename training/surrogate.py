"""Train a SURROGATE AI-detector — a local model that mimics a target detector's score.

**Why this exists.** Optimizing a rewriter against our local ensemble does NOT transfer to commercial
detectors (measured: RADAR rated a humanized sample 0.008 while GPTZero rated the same text 100% AI).
To actually move GPTZero you have to put GPTZero's signal in the loop. A surrogate distills that signal
into a small local model the RL trainer (`reward.py`) can query millions of times for free.

Two data paths:

* **Free / general** (`--dataset hc3` or `raid`): train on a public AI-vs-human corpus → a *general*
  AI-detector surrogate. Cheap ($0), weaker transfer to a *specific* commercial detector. The honest
  first probe: if a general surrogate moves GPTZero at all, a targeted one is worth paying for.
* **Targeted** (`--dataset path/to/labels.csv`): train on a CSV of `text,score` you collected from the
  GPTZero API (score = GPTZero's P(AI) in [0,1]) → a surrogate that mimics GPTZero specifically.
  Stronger transfer. Costs API budget (~one month of GPTZero Professional for a few thousand labels).

The trained surrogate exposes ``score(text) -> P(AI) in [0,1]`` (the `Detector` protocol), so
`reward.py` (set `UNTELL_SURROGATE_DIR`) or the ensemble can use it as a drop-in target.

    python -m training.surrogate --dataset hc3 --n 3000 --out out/surrogate     # free, ~minutes on a GPU
    python -m training.surrogate --dataset gptzero_labels.csv --out out/surrogate # targeted (paid labels)
    python -m training.surrogate --smoke                                          # tiny CPU dry-run

Then point RL training at it:

    UNTELL_SURROGATE_DIR=out/surrogate python -m training.rl_humanizer --model Qwen/Qwen2.5-3B-Instruct
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import random

logger = logging.getLogger(__name__)
DEFAULT_BASE = "FacebookAI/roberta-base"
SMOKE_BASE = "distilroberta-base"

# Tiny labeled fallback so `--smoke` and no-`datasets` boxes still exercise the full path.
_BUILTIN_AI = [
    "Artificial intelligence has fundamentally transformed numerous industries. Moreover, it streamlines "
    "operations and improves efficiency across various sectors. Overall, its impact continues to grow.",
    "Climate change represents one of the most pressing challenges of our time. Furthermore, it poses "
    "significant risks to ecosystems. In conclusion, addressing it requires coordinated global action.",
    "Effective communication plays a crucial role in any organization. Additionally, it fosters "
    "collaboration. Overall, organizations that prioritize communication achieve better outcomes.",
]
_BUILTIN_HUMAN = [
    "i grabbed coffee on the way in and the line was way too long for a tuesday. spilled half of it "
    "getting out the door, classic. some mornings just go like that and you roll with it.",
    "honestly the meeting could have been an email. we went in circles for an hour and nobody wrote "
    "anything down, so next week we'll probably have the exact same conversation again.",
    "my dad still calls every sunday even though we mostly just talk about the weather and his garden. "
    "the tomatoes did bad this year, too much rain he says, but he keeps trying anyway.",
]


def _builtin_labeled(n: int) -> list[tuple[str, float]]:
    """``n`` samples, alternating AI and human so every prefix is as balanced as n allows.

    The classes used to be concatenated — all AI, then all human — and then sliced to ``[:n]``.
    With three of each that gave zero human samples for n <= 3 and 9 AI to 7 human at the
    ``--smoke`` default of 16, while ``load_labeled`` documented its return as balanced. A
    surrogate trained on one class cannot separate the two, and it reports no error while failing:
    it just learns to answer "AI" and scores a perfect training loss doing it.

    Odd ``n`` necessarily leaves one extra AI sample; that is the only imbalance possible now.
    """
    if n <= 0:
        return []
    ai = [(t, 1.0) for t in _BUILTIN_AI]
    human = [(t, 0.0) for t in _BUILTIN_HUMAN]
    out: list[tuple[str, float]] = []
    i = 0
    while len(out) < n:
        out.append(ai[i % len(ai)])
        if len(out) < n:
            out.append(human[i % len(human)])
        i += 1
    return out


def _load_csv(path: str) -> list[tuple[str, float]]:
    """Load (text, score) from a CSV with `text` and `score` columns (GPTZero-labeled path)."""
    rows: list[tuple[str, float]] = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            txt = (r.get("text") or "").strip()
            try:
                score = float(r.get("score"))
            except (TypeError, ValueError):
                continue
            if txt and len(txt.split()) >= 5:
                rows.append((txt, max(0.0, min(1.0, score))))
    return rows


def load_labeled(dataset: str = "hc3", n: int = 2000, seed: int = 0) -> list[tuple[str, float]]:
    """Return balanced [(text, label)] — label 1.0 = AI, 0.0 = human (or a continuous score from a CSV).

    Falls back to a tiny built-in set if `datasets` isn't installed or the load fails, so the trainer
    always runs (the surrogate it produces is then only a toy — for the real thing install `.[eval]`).
    """
    name = dataset.lower()
    rng = random.Random(seed)

    if name.endswith(".csv") or os.path.isfile(dataset):
        rows = _load_csv(dataset)
        rng.shuffle(rows)
        # `rows[:n] if n else rows` read n=0 as "no limit" and returned the entire CSV. n is a
        # sample count, so 0 means none — a caller using it as a dry-run sentinel got the full
        # dataset instead. Negative values clamp to 0 rather than slicing from the end.
        return rows[:max(0, n)]

    try:
        from datasets import load_dataset
    except Exception:
        logger.warning("dataset load failed; falling back to built-in samples.")
        return _builtin_labeled(n)

    rows = []
    try:
        if name == "hc3":
            ds = load_dataset("Hello-SimpleAI/HC3", "all", split="train")
            for row in ds:
                for a in (row.get("human_answers") or []):
                    if a and len(a.split()) > 30:
                        rows.append((a.strip(), 0.0))
                        break
                for a in (row.get("chatgpt_answers") or []):
                    if a and len(a.split()) > 30:
                        rows.append((a.strip(), 1.0))
                        break
                if len(rows) >= n * 1.3:
                    break
        elif name == "raid":
            ds = load_dataset("liamdugan/raid", split="train", streaming=True)
            for row in ds:
                gen = row.get("generation") or row.get("text")
                if not gen or len(gen.split()) < 30:
                    continue
                rows.append((gen.strip(), 0.0 if row.get("model", "human") == "human" else 1.0))
                if len(rows) >= n * 1.3:
                    break
        else:
            logger.warning("unknown dataset '%s'; using builtin.", dataset)
            return _builtin_labeled(n)
    except Exception as exc:
        logger.warning("dataset load failed (%s); using builtin.", type(exc).__name__)
        return _builtin_labeled(n)

    # Balance the two classes so the surrogate isn't biased by corpus skew.
    if n <= 0:
        return []  # same reading of n as the CSV branch: a count, not a sentinel
    ai = [r for r in rows if r[1] >= 0.5]
    hu = [r for r in rows if r[1] < 0.5]
    k = min(len(ai), len(hu), max(1, n // 2))
    if k == 0:
        return _builtin_labeled(n)
    bal = ai[:k] + hu[:k]
    rng.shuffle(bal)
    return bal


def train_surrogate(
    out_dir: str = "out/surrogate",
    *,
    dataset: str = "hc3",
    base: str = DEFAULT_BASE,
    n: int = 2000,
    epochs: int = 2,
    lr: float = 2e-5,
    batch: int = 8,
    seed: int = 0,
    smoke: bool = False,
) -> str:
    """Fine-tune a small classifier to predict P(AI). Regression head + BCE works for both binary
    (0/1) labels and soft GPTZero scores. Returns the output dir."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if smoke:
        base, n, epochs, batch = SMOKE_BASE, 16, 1, 4

    data = load_labeled(dataset, n=n, seed=seed)
    if not data:
        raise SystemExit("no training data loaded")

    tok = AutoTokenizer.from_pretrained(base)
    model = AutoModelForSequenceClassification.from_pretrained(base, num_labels=1)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).train()
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    lossfn = torch.nn.BCEWithLogitsLoss()
    rng = random.Random(seed)

    for ep in range(epochs):
        rng.shuffle(data)
        total, steps = 0.0, 0
        for i in range(0, len(data), batch):
            chunk = data[i : i + batch]
            texts = [t for t, _ in chunk]
            labels = torch.tensor([[s] for _, s in chunk], dtype=torch.float, device=device)
            enc = tok(texts, return_tensors="pt", truncation=True, max_length=512, padding=True).to(device)
            logits = model(**enc).logits
            loss = lossfn(logits, labels)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += float(loss)
            steps += 1
        logger.info("epoch %d/%d  loss %.4f  (n=%d)", ep + 1, epochs, total / max(steps, 1), len(data))

    os.makedirs(out_dir, exist_ok=True)
    model.save_pretrained(out_dir)
    tok.save_pretrained(out_dir)
    return out_dir


class SurrogateDetector:
    """Loads a trained surrogate and scores text like any other detector: ``score(text) -> P(AI)``."""

    name = "surrogate"
    tier = "full"

    def __init__(self, model_dir: str):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self._tok = AutoTokenizer.from_pretrained(model_dir)
        self._model = AutoModelForSequenceClassification.from_pretrained(model_dir).eval()

    def available(self) -> bool:
        return True

    def score(self, text: str) -> float | None:
        from untell.detectors.base import clamp01

        if not text or not text.strip():
            # None means "no signal" and is excluded from the ensemble (untell/detectors/base.py).
            # Returning 0.5 made empty text a real vote: a text every other detector scored 0.05
            # came out at 0.5 max, purely from a detector that had nothing to look at.
            return None
        enc = self._tok(text, return_tensors="pt", truncation=True, max_length=512)
        with self._torch.no_grad():
            p = self._torch.sigmoid(self._model(**enc).logits)[0, 0].item()
        return clamp01(float(p))


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    ap = argparse.ArgumentParser(
        prog="untell-surrogate",
        description="Train a local surrogate of a target AI detector (the RL reward's real target).",
    )
    ap.add_argument("--dataset", default="hc3", help="hc3 | raid | path/to/labels.csv (text,score)")
    ap.add_argument("--out", default="out/surrogate")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--smoke", action="store_true", help="tiny CPU dry-run (bert-tiny, 16 samples).")
    a = ap.parse_args(argv)

    out = train_surrogate(
        a.out, dataset=a.dataset, base=a.base, n=a.n, epochs=a.epochs, lr=a.lr, batch=a.batch, smoke=a.smoke
    )
    print(f"surrogate saved -> {out}")
    print(f"use it as the RL reward target:  UNTELL_SURROGATE_DIR={out} python -m training.rl_humanizer ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
