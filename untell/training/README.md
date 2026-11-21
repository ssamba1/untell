# Training — the GPU moat (RL-against-ensemble + alignment)

The one capability no other open repo combines with the rest of our stack: a small model RL-trained
to untell-by-default, so its paraphrases evade our **whole detector ensemble in a single forward
pass** (no inference loop) while preserving meaning. StealthRL (arXiv 2602.08934) shows such policies
**transfer to detectors they never trained on** — i.e. they beat detectors that don't exist yet.

## Files
- `reward.py` — `humanness_reward(original, candidate, tier=...)` = `(1 - max P(AI) across our
  ensemble) - meaning-drift penalty`. Pure-python over our own detectors; **testable on lite tier, no
  GPU** (covered in `tests/`).
- `rl_humanizer.py` — GRPO + LoRA trainer scaffold (trl/peft). **GPU only; not run in CI.**

## Run (GPU)
```bash
pip install -e ".[train,full]"            # trl + peft + transformers + torch + our detectors
python -m untell.training.rl_humanizer --model Qwen/Qwen2.5-3B-Instruct --tier full --steps 500
# stronger / transfer-robust: --tier commercial (real detector APIs as reward, AuthorMist style — costs credits)
```
LoRA on a 3-4B model fits ~16-24GB VRAM; StealthRL reports a usable policy from ~10K samples. After
training, use the saved policy as the rewriter backend (replaces the API loop; runs local, no key).

## The best stack (beyond plain GRPO) — staged, multi-objective

Plain GRPO-vs-one-detector is the floor. The strongest pipeline for us:

1. **Distill our own loop (the edge).** `python -m untell.training.distill --dataset raid --n 2000 --tier full`
   runs our Claude + detector-feedback loop (a strong teacher), keeps outputs that pass the ensemble +
   keep meaning, and writes SFT pairs. Most repos have no teacher this good.
2. **SFT** a small model (Qwen2.5-0.5B–3B) on that JSONL → a fast model that already untells well.
3. **GRPO / DPO refine** (`rl_humanizer.py`) against the **broad, hard** ensemble (RADAR + Binoculars +
   commercial) with the **multi-objective reward** (`reward.humanness_reward` = evasion + meaning +
   fluency) — the impossibility-triangle win competitors miss (they reward only evasion → quality rots).
4. **Keep the inference loop on top** for the hard cases.
5. **Adversarial curriculum (optional):** retrain detectors on the humanizer's outputs and repeat →
   stays ahead of *future* detectors (StealthRL's transfer property, amplified).

Why this beats StealthRL-as-is: (a) teacher distillation gives a strong init RL-from-scratch lacks,
(b) the reward is multi-objective (keeps quality, not just evasion), (c) the reward ensemble is the
broadest + hardest (incl. RADAR + commercial), maximizing transfer to unseen detectors.

## Variants (all in the literature, same reward plug)
- **StealthRL** — GRPO vs OSS-detector ensemble (RoBERTa/Fast-DetectGPT/Binoculars/MAGE). `--tier full`.
- **AuthorMist** — RL vs the *commercial* detectors via their APIs as reward. `--tier commercial`.
- **MASH** — style-SFT → DPO instead of GRPO; swap the trainer, keep the reward as the DPO preference.
