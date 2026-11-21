# Train the moat on a DigitalOcean GPU Droplet (one-time)

The RL/alignment moat needs a real GPU. A DigitalOcean **GPU Droplet** is ideal — Ubuntu Linux (torch
just works, unlike a broken-torch Windows box) with NVIDIA driver + CUDA preinstalled. Train once,
pull back a ~100MB adapter, destroy the droplet.

## 0. Request access first
GPU Droplets are gated — the create page shows "Request Access / Increase your limit" until DO approves
your account. Do that first. Also: GPU Droplets are **not free** (~$3.44/GPU/hr for H200) unless you
have credits — pick the smallest GPU and **destroy the droplet right after training**.

## 1. Create the droplet
- DigitalOcean → Create → **GPU Droplet**. Region: **NYC2** (AMS3 often shows GPUs unavailable).
- Image: **AI/ML Ready · Ubuntu** (NVIDIA driver + CUDA preinstalled).
- Add your **SSH key** (required). Create. SSH in: `ssh root@<droplet-ip>`.
- **GPU plan** — our job (Qwen2.5-3B + LoRA) needs only ~16–24 GB VRAM, so don't overpay:

  | DO plan | VRAM | Use it? |
  |---|---|---|
  | **RTX 6000 Ada** | 48 GB | ✅ best value — comfortable for 3B/4B LoRA |
  | RTX 4000 Ada | 20 GB | ✅ cheapest — tight; run `--model Qwen/Qwen2.5-1.5B-Instruct` |
  | L40S | 48 GB | ✅ great, similar to RTX 6000 Ada |
  | H100 / H200 | 80 / 141 GB | ✅ overkill but fastest (~1 hr); only if that's the easy single-GPU |

## 2. One-shot setup + train
```bash
# on the droplet:
curl -fsSL https://raw.githubusercontent.com/ssamba1/untell/main/training/setup_gpu.sh -o setup_gpu.sh
# repo is PRIVATE -> either make it public briefly, or pass a GitHub token:
GITHUB_TOKEN=ghp_xxx bash setup_gpu.sh
```
Or do it manually (steps in `setup_gpu.sh`): `git clone` → `python3 -m venv .venv` →
`pip install -e ".[train,full]"` → `python -m untell.training.rl_humanizer --tier full --steps 500`.

**Private-repo note:** the clone needs auth. Easiest: a GitHub **personal access token** (read-only,
repo scope) passed as `GITHUB_TOKEN`, or `scp -r` the repo up from your machine, or flip the repo public
for the clone then private again.

## 3. Pull the result back + destroy
```bash
# from your machine:
scp -r root@<droplet-ip>:~/untell/out/rl-humanizer ./out/
```
Then **destroy the droplet** in the DO console (stops billing). The adapter in `out/rl-humanizer` is
your trained policy — use it as the rewriter backend (runs on CPU for inference).

## Time / scale
- H100 80GB: Qwen2.5-3B GRPO+LoRA, ~500 steps / ~10K samples ≈ a few hours.
- Want stronger / transfer-robust vs the commercial detectors (AuthorMist): `--tier commercial` (needs
  the detector API keys set on the droplet; costs detector credits per reward call — slower, pricier).
- Reward is `untell.training.reward.humanness_reward` (evade our ensemble + keep meaning) — already tested.
