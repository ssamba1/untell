"""DPO training of the humanizer — often more stable than GRPO on small GPUs. GPU-only, not run in CI.

Preference pairs: ``chosen`` = a humanized rewrite that passed our ensemble (from the loop, via
``training.distill``), ``rejected`` = the AI original. DPO teaches the model to prefer human-reading
text over AI text. Run distill first (needs a rewriter/teacher key), then DPO.

    pip install -e ".[train,full,api]" && export ANTHROPIC_API_KEY=...
    python -m training.dpo_humanizer --dataset raid --n 1000 --model Qwen/Qwen2.5-3B-Instruct
    python -m training.dpo_humanizer --smoke      # tiny model, 2 steps, synthetic pairs (no key) — proves it runs
"""

from __future__ import annotations

import argparse
import logging

SMOKE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
_PROMPT = "Rewrite the following text so it reads as natural human writing while preserving its exact meaning:\n\n{text}"


def build_pairs(dataset: str = "builtin", n: int = 200, tier: str = "full") -> dict:
    """chosen = the loop's humanized output (passed the ensemble), rejected = the AI source."""
    from training.distill import distill

    out = distill(dataset, n=n, tier=tier)
    pairs = [{"prompt": r["prompt"], "chosen": r["humanized"], "rejected": r["source"]} for r in out["rows"]]
    return {"pairs": pairs, "kept": out["kept"], "total": out["total"]}


def _smoke_pairs(n: int = 8) -> list[dict]:
    """Synthetic pairs (no loop/key) — just to prove the DPO training loop runs end-to-end."""
    from eval.datasets import load_samples

    return [
        {"prompt": _PROMPT.format(text=s), "chosen": "Plainly put: " + s[:60], "rejected": s}
        for s in load_samples("builtin", n)
    ]


def build_pairs_human(n: int = 500) -> list[dict]:
    """chosen = domain-matched HUMAN text, rejected = the AI answer on the SAME topic. NO API key.

    HC3 stores each question's ``human_answers`` alongside its ``chatgpt_answers``, so pairing the
    human answer (preferred) against the ChatGPT answer (rejected) yields naturally domain-matched DPO
    pairs that teach the policy to prefer *how humans actually wrote*. This is the free warm-start
    StealthRL/HIP run before RL — no teacher key, no loop, no cost. Falls back to the builtin smoke
    pairs when ``datasets`` or HC3 is unavailable, so it never hard-requires a download.
    """
    try:
        from datasets import load_dataset

        ds = load_dataset("Hello-SimpleAI/HC3", "all", split="train")
    except Exception:
        return _smoke_pairs(min(n, 8))
    pairs: list[dict] = []
    for row in ds:
        human = next((a for a in (row.get("human_answers") or []) if a and len(a.split()) > 30), None)
        ai = next((a for a in (row.get("chatgpt_answers") or []) if a and len(a.split()) > 30), None)
        if human and ai:
            pairs.append({"prompt": _PROMPT.format(text=ai), "chosen": human.strip(), "rejected": ai.strip()})
        if len(pairs) >= n:
            break
    return pairs or _smoke_pairs(min(n, 8))


def train(
    model_id: str = "Qwen/Qwen2.5-3B-Instruct",
    dataset: str = "builtin",
    n: int = 1000,
    tier: str = "full",
    out: str = "out/dpo-humanizer",
    smoke: bool = False,
    load_4bit: bool = False,
    use_human_corpus: bool = False,
    hub_id: str | None = None,
    resume: str | None = None,
):
    """LoRA DPO. Heavy deps imported here so the module stays importable without a GPU.

    ``use_human_corpus`` = the FREE path: preference pairs from HC3 (human answer preferred over the
    ChatGPT answer on the same topic), no teacher key. ``hub_id`` pushes the adapter to HF after save
    so an ephemeral GPU host can't lose it. ``resume`` continues from a checkpoint dir.
    """
    import os
    import pathlib

    import torch  # noqa: F401
    from datasets import Dataset
    from peft import LoraConfig
    from trl import DPOConfig, DPOTrainer

    from training.model_utils import load_model

    if smoke:
        model_id, out = SMOKE_MODEL, "out/dpo-smoke"
        pairs = _smoke_pairs()
        resume = None
    elif use_human_corpus:
        pairs = build_pairs_human(n=n)  # free: HC3 human vs AI, no key
    else:
        pairs = build_pairs(dataset, n=n, tier=tier)["pairs"]  # loop-distilled (needs a teacher key)

    # Fail FAST on a bad Hub token: validate auth and create the repo BEFORE the multi-hour train.
    if hub_id and not smoke:
        from huggingface_hub import HfApi

        who = HfApi().whoami()  # raises 401 immediately if the token is bad/missing
        HfApi().create_repo(hub_id, repo_type="model", exist_ok=True, private=True)
        print(f"HF auth OK as {who['name']} -> will push DPO adapter to {hub_id} after training")

    model = load_model(model_id, load_4bit)

    dataset_obj = Dataset.from_list(pairs)
    cfg = DPOConfig(
        output_dir=out,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=5e-6,
        bf16=True,
        max_steps=2 if smoke else -1,
        num_train_epochs=1,
        logging_steps=10,
        beta=0.1,
        # Checkpoint mid-run so a killed session (Kaggle/Colab wall) still leaves a usable adapter.
        save_strategy="steps",
        save_steps=25,
        save_total_limit=3,
        resume_from_checkpoint=resume,
    )
    lora = LoraConfig(r=16, lora_alpha=32, target_modules="all-linear", task_type="CAUSAL_LM")
    trainer = DPOTrainer(model=model, args=cfg, train_dataset=dataset_obj, peft_config=lora)
    # Always attempt the final save even if training dies mid-way — a partial adapter beats nothing.
    try:
        trainer.train()
    finally:
        try:
            trainer.save_model(out)
        except Exception as exc:  # noqa: BLE001
            import logging as _logging

            _logging.getLogger(__name__).warning("trainer.save_model failed: %s: %s", type(exc).__name__, exc)

    # Verify the FINAL adapter is a real (>=1MB) LoRA, not a misfired KiB-scale save.
    out_dir = pathlib.Path(out)
    adapter = next(
        (out_dir / nm for nm in ("adapter_model.safetensors", "adapter_model.bin") if (out_dir / nm).exists()),
        None,
    )
    size_mb = adapter.stat().st_size / 1e6 if adapter else 0.0
    print(f"saved DPO policy -> {os.path.abspath(out)}  (adapter {size_mb:.1f} MB on disk)")

    if hub_id and not smoke:
        from huggingface_hub import HfApi

        HfApi().upload_folder(folder_path=out, repo_id=hub_id, repo_type="model")
        print(f"pushed DPO adapter -> https://huggingface.co/{hub_id}")
    return out


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(prog="training.dpo_humanizer", description=__doc__)
    parser.add_argument("--model", default="Qwen/Qwen2.5-3B-Instruct")
    parser.add_argument("--dataset", default="builtin")
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--tier", default="full", choices=["lite", "full", "heavy", "commercial"])
    parser.add_argument("--out", default="out/dpo-humanizer")
    parser.add_argument("--smoke", action="store_true", help="tiny model + 2 steps + synthetic pairs (proves it runs)")
    parser.add_argument("--load-4bit", action="store_true", help="QLoRA 4-bit load so 3B fits a free 16GB T4")
    parser.add_argument(
        "--use-human-corpus",
        action="store_true",
        help="FREE warm-start: preference pairs from HC3 (human answer preferred over the ChatGPT "
        "answer on the same topic) — no teacher key, no cost. The recommended $0 DPO path.",
    )
    parser.add_argument("--hub-id", help="push the adapter to this HF Hub repo after save (needs HF_TOKEN)")
    parser.add_argument("--resume", default=None, help="resume from this checkpoint directory")
    args = parser.parse_args(argv)
    from untell._env import load_env

    load_env()
    path = train(
        model_id=args.model, dataset=args.dataset, n=args.n, tier=args.tier, out=args.out,
        smoke=args.smoke, load_4bit=args.load_4bit, use_human_corpus=args.use_human_corpus,
        hub_id=args.hub_id, resume=args.resume,
    )
    print(f"saved DPO policy -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
