"""Generate topic-matched AI essays with a local open model, for recall on modern LLM text.

The held-out AI text in untell's audits was GPT-3 (2022). Modern models write differently, and
detectors trained on older text are known to miss them, so recall measured on GPT-3 likely
overstates today's. This writes essays answering exactly the PERSUADE 2.0 assignments the human
essays answer, with a 2024 instruction-tuned model run locally (no API), seeded and recorded so the
corpus can be regenerated.

    python -m untell.bench.generate_ai persuade_train.csv --model Qwen/Qwen2.5-1.5B-Instruct \\
        --per-prompt 8 --out modern-ai.jsonl
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys


def assignments(paths: list[str]) -> dict[str, str]:
    csv.field_size_limit(10**9)
    out: dict[str, str] = {}
    for p in paths:
        with open(p, encoding="utf-8", errors="replace", newline="") as fh:
            for r in csv.DictReader(fh):
                name, text = (r.get("prompt_name") or "").strip(), (r.get("assignment") or "").strip()
                if name and text and name not in out:
                    out[name] = text
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m untell.bench.generate_ai", description=__doc__.split("\n\n")[0])
    ap.add_argument("csv", nargs="+", help="PERSUADE 2.0 CSVs (for the assignment texts)")
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--per-prompt", type=int, default=8)
    ap.add_argument("--max-new-tokens", type=int, default=600)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype=torch.float32)
    model.eval()
    grades = ["6th", "8th", "10th", "11th", "12th"]
    rng = random.Random(args.seed)
    with open(args.out, "w", encoding="utf-8") as fh:
        for name, assignment in sorted(assignments(args.csv).items()):
            for i in range(args.per_prompt):
                grade = rng.choice(grades)
                seed = rng.randrange(1 << 30)
                torch.manual_seed(seed)
                msgs = [{"role": "user", "content":
                         f"You are a {grade}-grade student in the United States. Write an essay "
                         f"responding to this assignment. Write only the essay.\n\n{assignment}"}]
                enc = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt",
                                              return_dict=True)
                with torch.no_grad():
                    gen = model.generate(**enc, max_new_tokens=args.max_new_tokens, do_sample=True,
                                         temperature=0.8, top_p=0.95)
                prompt_len = enc["input_ids"].shape[1]
                text = tok.decode(gen[0, prompt_len:], skip_special_tokens=True).strip()
                fh.write(json.dumps({"id": f"modern:{name}:{i}", "text": text, "label": "ai",
                                     "group": "modern-llm-essays",
                                     "meta": {"prompt_name": name, "grade_persona": grade},
                                     "provenance": {"model": args.model, "seed": seed,
                                                    "temperature": 0.8, "top_p": 0.95}},
                                    ensure_ascii=False) + "\n")
                fh.flush()
                print(f"{name} {i + 1}/{args.per_prompt}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
