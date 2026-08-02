"""StealthRL-style GRPO + LoRA training of a untell-by-default rewriter (THE GPU MOAT).

⚠️ RUN ON GPU ONLY. Not run in CI. This is the scaffold for the one capability no other open repo
combines with the rest of our stack: a small instruct model RL-trained so its paraphrases evade our
whole detector ensemble *in a single forward pass* (no inference loop), while preserving meaning.
StealthRL (2602.08934) shows this transfers to detectors it never trained on.

Setup:
    pip install -e ".[train,full]"          # trl + peft + transformers + torch + our detectors
    python -m training.rl_humanizer --model Qwen/Qwen2.5-3B-Instruct --tier full --steps 500

Design: GRPO samples K paraphrases per source; the reward (training.reward.humanness_reward) =
(1 - max P(AI) across the ensemble) - meaning-drift penalty. The policy learns to untell. Train
against ``--tier full`` (free OSS detectors incl. RADAR) or ``--tier commercial`` (real APIs, AuthorMist
style — costs credits) for the strongest, transfer-robust policy.
"""

from __future__ import annotations

import argparse
import logging
import os

from training.model_utils import load_model as _load_model
from training.reward import humanness_reward

logger = logging.getLogger(__name__)

# Single source of truth for the rewrite instruction: the LOCAL inference path (LocalPolicyRewriter)
# must feed the trained model the EXACT prompt it was trained on, or every inference is
# out-of-distribution. Import it here so the two can never silently diverge. (untell is always
# installed when training runs — reward.py already imports it.)
from untell.rewriter.local_policy import _TRAIN_PROMPT as _PROMPT  # noqa: E402

DEFAULT_MODEL = "Qwen/Qwen2.5-3B-Instruct"
SMOKE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"


def build_dataset(name: str = "builtin", n: int = 2000):
    """Build {prompt, source} rows from AI-text samples to untell (RAID/MAGE/HC3 via eval.datasets)."""
    from eval.datasets import load_samples

    samples = load_samples(name, n)
    return [{"prompt": _PROMPT.format(text=s), "source": s} for s in samples]


def _normalise(s: str) -> str:
    return " ".join(s.split())


def _source_resolver(source_by_prompt: dict[str, str]):
    """Return ``prompt -> source text``, or None when it genuinely cannot be recovered.

    The old code was ``source_by_prompt.get(p, p)``: on a lookup miss it passed the PROMPT as the
    original. A prompt is the instruction wrapper plus the source, so it fails the similarity gate
    and usually the length gate too — every candidate scores -1.0. That is the worst possible
    failure for GRPO: a group whose rewards are all identical carries no advantage signal, so
    training runs to completion at full GPU cost and learns nothing, with no error to show for it.

    Exact match first, then whitespace-normalised (a tokenize/decode round-trip inside the trainer
    can renormalise the string), then strip the known prompt prefix. If all three miss, return None
    — humanness_reward treats that as an unusable candidate and returns -1.0, which is at least the
    honest answer, and the warning below says it is happening.
    """
    by_norm = {_normalise(k): v for k, v in source_by_prompt.items()}
    prefix = _PROMPT.split("{text}")[0]
    warned = False

    def resolve(p: str) -> str | None:
        nonlocal warned
        src = source_by_prompt.get(p)
        if src is not None:
            return src
        src = by_norm.get(_normalise(p))
        if src is not None:
            return src
        if p.startswith(prefix):
            return p[len(prefix):].strip() or None
        if not warned:
            warned = True
            logger.warning(
                "reward: could not map a prompt back to its source text; those candidates score "
                "-1.0. If this is every prompt, the reward carries no signal and the run is wasted."
            )
        return None

    return resolve


def train(
    model_id: str = DEFAULT_MODEL,
    tier: str = "full",
    steps: int = 300,
    k: int = 6,
    out: str = "out/rl-humanizer",
    smoke: bool = False,
    load_4bit: bool = False,
    hub_id: str | None = None,
    resume: str | None = None,
    dpo_init: str | None = None,
    reward_sim_floor: float = 0.76,
):
    """GRPO-train the policy. Heavy deps imported here so this module stays importable without a GPU.

    ``load_4bit`` = QLoRA: load the base model in 4-bit so a 3B model fits a free 16GB T4 (Colab/Kaggle).
    ``hub_id`` = push the adapter to this HF Hub repo right after saving (needs ``HF_TOKEN`` /
    ``huggingface-cli login``). Use it so an ephemeral GPU host can die without losing the weights.
    """
    # Pre-flight: check peft + torchao compatibility (common Kaggle/Colab mismatch).
    import warnings

    import torch  # noqa: F401  (fail loudly here if the env can't do training)
    if not torch.cuda.is_available() and not smoke:
        raise RuntimeError("CUDA is required for training. No GPU detected.")
    from datasets import Dataset
    from peft import LoraConfig
    from trl import GRPOConfig, GRPOTrainer

    # Suppress the harmless "cpp extensions" torch warning that scares users.
    warnings.filterwarnings("ignore", message=".*cpp extensions.*incompatible torch.*")

    try:
        from peft.import_utils import is_torchao_available
    except ImportError:
        pass  # older peft version doesn't have this check
    else:
        try:
            is_torchao_available()
        except ImportError as exc:
            logger.warning(
                "PRE-FLIGHT FAILURE: %s\n"
                "Fix with:  pip install -q 'torchao>=0.16.0'\n"
                "Or:        pip install -q 'peft<0.14'  (older peft, no torchao check)",
                exc,
            )
            raise SystemExit(1) from None

    if smoke:  # prove the pipeline runs: tiny model, 2 steps, cheap lite reward, few samples
        model_id, tier, steps, k, out = SMOKE_MODEL, "lite", 2, 4, "out/rl-smoke"
        resume = None  # never resume in smoke mode

    # Free-path note (not a warning): without a surrogate the reward is the FREE weighted open-detector
    # ensemble — the intended $0 path. It reaches the open-detector ceiling (StealthRL-style) and
    # transfers to held-out OPEN detectors, but does NOT *guarantee* beating commercial detectors. To
    # target those, distill a surrogate (training.surrogate, needs paid keys) and set UNTELL_SURROGATE_DIR.
    if not smoke and not os.environ.get("UNTELL_SURROGATE_DIR"):
        logger.info(
            "No UNTELL_SURROGATE_DIR -> reward = FREE weighted open-detector ensemble (tier=%s). $0 "
            "path: reaches the open-detector ceiling and transfers to held-out open detectors; does not "
            "guarantee commercial (GPTZero/Originality) transfer. Set UNTELL_SURROGATE_DIR to target those.",
            tier,
        )

    # Fail FAST on a bad/missing Hub token: validate auth and create the repo BEFORE the multi-hour
    # train, not after. A 401 discovered at push time is useless once the ephemeral disk is already
    # wiped — the exact failure that lost a completed run (trained 4h, push 401'd, session reset).
    if hub_id:
        from huggingface_hub import HfApi

        who = HfApi().whoami()  # raises 401 immediately if the token is bad/missing
        HfApi().create_repo(hub_id, repo_type="model", exist_ok=True, private=True)
        print(f"HF auth OK as {who['name']} -> will push adapter to {hub_id} after training")

    model = _load_model(model_id, load_4bit)

    # Optional DPO warm-start: merge a DPO LoRA into the base before GRPO wraps a fresh LoRA on top,
    # so RL starts from a semantically better policy (fewer steps, less quality drift). merge_and_unload
    # produces a full-precision copy — on a 16GB T4 the merge peaks ~12GB, feasible but tight.
    if dpo_init and not smoke:
        import transformers
        from peft import PeftModel

        base = model if not isinstance(model, str) else transformers.AutoModelForCausalLM.from_pretrained(
            model, torch_dtype="auto", device_map="auto"
        )
        model = PeftModel.from_pretrained(base, dpo_init).merge_and_unload()
        logger.info("merged DPO adapter %s into base before GRPO", dpo_init)

    rows = build_dataset(n=16 if smoke else 2000)
    source_by_prompt = {r["prompt"]: r["source"] for r in rows}
    dataset = Dataset.from_list([{"prompt": r["prompt"]} for r in rows])
    resolve_source = _source_resolver(source_by_prompt)

    def reward_fn(prompts, completions, **_):
        # GRPO calls with batched prompts/completions; score each against the (free ensemble) reward.
        return [
            humanness_reward(resolve_source(p), c, tier=tier, sim_floor=reward_sim_floor)
            for p, c in zip(prompts, completions)
        ]

    cfg = GRPOConfig(
        output_dir=out,
        num_generations=k,
        max_steps=steps,
        per_device_train_batch_size=2,
        # trl requires generation_batch_size (= per_device_batch * grad_accum) to be divisible by
        # num_generations (=k). Tie grad_accum to k so any k stays valid (else: ValueError at init).
        gradient_accumulation_steps=k,
        learning_rate=1e-5,
        warmup_steps=20,
        bf16=torch.cuda.is_available(),  # bf16 needs a GPU; on CPU (no accelerator) fall back to fp32
        logging_steps=10,
        # 128 tokens ~60s/step on T4 with Qwen2.5-3B + k=6. At ~100s/step, 300 steps = 8.3h
        # (fits Kaggle's 9h GPU limit). 192 tokens was pushing to ~14h which gets killed.
        max_completion_length=64 if smoke else 128,
        max_grad_norm=0.3,
        optim="adamw_torch",
        # Checkpoint mid-run so a session that hits the GPU-host wall (Kaggle/Colab cap) still
        # leaves a usable adapter on disk. Without this a killed run produces nothing.
        save_strategy="steps",
        save_steps=25,
        save_total_limit=3,
        # Allow resuming from a checkpoint directory.
        resume_from_checkpoint=resume,
    )
    lora = LoraConfig(r=32, lora_alpha=64, target_modules="all-linear", task_type="CAUSAL_LM")
    trainer = GRPOTrainer(model=model, reward_funcs=reward_fn, args=cfg, train_dataset=dataset, peft_config=lora)
    # Always attempt the final save, even if training dies mid-way (OOM, KeyboardInterrupt, or the
    # GPU-host wall-clock cap) — a partially-trained adapter on disk beats nothing. The save is itself
    # guarded so a save failure can't mask the original training error.
    try:
        trainer.train()
    finally:
        try:
            trainer.save_model(out)
        except Exception as exc:  # noqa: BLE001
            logger.warning("trainer.save_model failed: %s: %s", type(exc).__name__, exc)

    # Verify the FINAL adapter specifically. A real LoRA adapter is ~100MB+; a KiB-scale number means
    # the save misfired (the trap that produced a useless 76KiB tarball last run). Measure only the
    # adapter file in `out` — NOT a recursive sum, which would count the out/checkpoint-*/ dirs and let
    # the guard pass even when the final save never ran.
    import pathlib

    abs_out = os.path.abspath(out)
    out_dir = pathlib.Path(out)
    adapter = next(
        (out_dir / n for n in ("adapter_model.safetensors", "adapter_model.bin") if (out_dir / n).exists()),
        None,
    )
    size_mb = adapter.stat().st_size / 1e6 if adapter else 0.0
    print(f"saved policy -> {abs_out}  (adapter {size_mb:.1f} MB on disk)")
    if adapter is None or size_mb < 1.0:
        logger.warning(
            "no final LoRA adapter (adapter_model.safetensors/.bin) >=1MB in the output dir — "
            "the save likely misfired or training never reached it. Do not trust this run; use the "
            "latest out/checkpoint-* instead if one exists."
        )

    if hub_id:  # auth + repo were validated up-front, so this only fails on a real network/disk error
        from huggingface_hub import HfApi

        HfApi().upload_folder(folder_path=out, repo_id=hub_id, repo_type="model")
        print(f"pushed adapter -> https://huggingface.co/{hub_id}")
    return out


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(prog="training.rl_humanizer", description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--tier", default="full", choices=["lite", "full", "heavy", "commercial"])
    parser.add_argument("--k", type=int, default=6)
    parser.add_argument("--out", default="out/rl-humanizer")
    parser.add_argument("--smoke", action="store_true", help="tiny model + 2 steps + lite reward (proves it runs)")
    parser.add_argument("--load-4bit", action="store_true", help="QLoRA 4-bit load so 3B fits a free 16GB T4")
    parser.add_argument("--hub-id", help="push the adapter to this HF Hub repo after save (needs HF_TOKEN) so an ephemeral host can't lose it")
    parser.add_argument("--resume", default=None, help="resume from this checkpoint directory (e.g. out/rl-humanizer/checkpoint-125)")
    parser.add_argument("--steps", type=int, default=300, help="training steps (default 300 to fit Kaggle 9h GPU limit; each step ~100s on T4)")
    parser.add_argument("--dpo-init", default=None, help="path to a DPO LoRA adapter to merge into the base before GRPO (warm-start)")
    parser.add_argument("--reward-sim-floor", type=float, default=0.76, help="hard meaning gate: rewrites below this similarity earn -1.0 (default 0.76)")
    args = parser.parse_args(argv)
    path = train(
        model_id=args.model, tier=args.tier, steps=args.steps, k=args.k, out=args.out,
        smoke=args.smoke, load_4bit=args.load_4bit, hub_id=args.hub_id, resume=args.resume,
        dpo_init=args.dpo_init, reward_sim_floor=args.reward_sim_floor,
    )
    print(f"saved policy -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
