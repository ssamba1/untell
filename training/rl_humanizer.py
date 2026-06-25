"""StealthRL-style GRPO + LoRA training of a humanize-by-default rewriter (THE GPU MOAT).

⚠️ RUN ON GPU ONLY. Not run in CI. This is the scaffold for the one capability no other open repo
combines with the rest of our stack: a small instruct model RL-trained so its paraphrases evade our
whole detector ensemble *in a single forward pass* (no inference loop), while preserving meaning.
StealthRL (2602.08934) shows this transfers to detectors it never trained on.

Setup:
    pip install -e ".[train,full]"          # trl + peft + transformers + torch + our detectors
    python -m training.rl_humanizer --model Qwen/Qwen2.5-3B-Instruct --tier full --steps 500

Design: GRPO samples K paraphrases per source; the reward (training.reward.humanness_reward) =
(1 - max P(AI) across the ensemble) - meaning-drift penalty. The policy learns to humanize. Train
against ``--tier full`` (free OSS detectors incl. RADAR) or ``--tier commercial`` (real APIs, AuthorMist
style — costs credits) for the strongest, transfer-robust policy.
"""

from __future__ import annotations

import argparse

from training.reward import humanness_reward

DEFAULT_MODEL = "Qwen/Qwen2.5-3B-Instruct"
_PROMPT = "Rewrite the following text so it reads as natural human writing while preserving its exact meaning:\n\n{text}"


def build_dataset(name: str = "builtin", n: int = 2000):
    """Build {prompt, source} rows from AI-text samples to humanize (RAID/MAGE/HC3 via eval.datasets)."""
    from eval.datasets import load_samples

    samples = load_samples(name, n)
    return [{"prompt": _PROMPT.format(text=s), "source": s} for s in samples]


def train(model_id: str = DEFAULT_MODEL, tier: str = "full", steps: int = 500, k: int = 6, out: str = "out/rl-humanizer"):
    """GRPO-train the policy. Heavy deps imported here so this module stays importable without a GPU."""
    import torch  # noqa: F401  (fail loudly here if the env can't do training)
    from datasets import Dataset
    from peft import LoraConfig
    from trl import GRPOConfig, GRPOTrainer

    rows = build_dataset()
    source_by_prompt = {r["prompt"]: r["source"] for r in rows}
    dataset = Dataset.from_list([{"prompt": r["prompt"]} for r in rows])

    def reward_fn(prompts, completions, **_):
        # GRPO calls with batched prompts/completions; score each against our ensemble.
        return [humanness_reward(source_by_prompt.get(p, p), c, tier=tier) for p, c in zip(prompts, completions)]

    cfg = GRPOConfig(
        output_dir=out,
        num_generations=k,
        max_steps=steps,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=8,
        learning_rate=1e-5,
        bf16=True,
        logging_steps=10,
    )
    lora = LoraConfig(r=32, lora_alpha=64, target_modules="all-linear", task_type="CAUSAL_LM")
    trainer = GRPOTrainer(model=model_id, reward_funcs=reward_fn, args=cfg, train_dataset=dataset, peft_config=lora)
    trainer.train()
    trainer.save_model(out)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="training.rl_humanizer", description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--tier", default="full", choices=["lite", "full", "heavy", "commercial"])
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--k", type=int, default=6)
    parser.add_argument("--out", default="out/rl-humanizer")
    args = parser.parse_args(argv)
    path = train(model_id=args.model, tier=args.tier, steps=args.steps, k=args.k, out=args.out)
    print(f"saved policy -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
