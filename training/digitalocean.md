# Train the moat on a DigitalOcean GPU Droplet (one-time)

The RL/alignment moat needs a real GPU. A DigitalOcean **GPU Droplet** is ideal — Ubuntu Linux (torch
just works, unlike a broken-torch Windows box) with NVIDIA driver + CUDA preinstalled. Train once,
pull back a ~100MB adapter, destroy the droplet.

## 1. Create the droplet
- DigitalOcean → Create → **Droplet** → choose a **GPU Droplet**.
- GPU: **H100 80GB** is plenty (handles the full Qwen2.5-3B/4B GRPO recipe fast). Any GPU droplet with
  **≥24 GB VRAM** works. (Your local 6 GB Quadro is too small for 4B — that's why this is on DO.)
- Image: the **AI/ML-ready** image (NVIDIA driver + CUDA preinstalled). Ubuntu 22.04.
- Add your SSH key. Create. SSH in: `ssh root@<droplet-ip>`.

## 2. One-shot setup + train
```bash
# on the droplet:
curl -fsSL https://raw.githubusercontent.com/ssamba1/humanize/main/training/setup_gpu.sh -o setup_gpu.sh
# repo is PRIVATE -> either make it public briefly, or pass a GitHub token:
GITHUB_TOKEN=ghp_xxx bash setup_gpu.sh
```
Or do it manually (steps in `setup_gpu.sh`): `git clone` → `python3 -m venv .venv` →
`pip install -e ".[train,full]"` → `python -m training.rl_humanizer --tier full --steps 500`.

**Private-repo note:** the clone needs auth. Easiest: a GitHub **personal access token** (read-only,
repo scope) passed as `GITHUB_TOKEN`, or `scp -r` the repo up from your machine, or flip the repo public
for the clone then private again.

## 3. Pull the result back + destroy
```bash
# from your machine:
scp -r root@<droplet-ip>:~/humanize/out/rl-humanizer ./out/
```
Then **destroy the droplet** in the DO console (stops billing). The adapter in `out/rl-humanizer` is
your trained policy — use it as the rewriter backend (runs on CPU for inference).

## Time / scale
- H100 80GB: Qwen2.5-3B GRPO+LoRA, ~500 steps / ~10K samples ≈ a few hours.
- Want stronger / transfer-robust vs the commercial detectors (AuthorMist): `--tier commercial` (needs
  the detector API keys set on the droplet; costs detector credits per reward call — slower, pricier).
- Reward is `training.reward.humanness_reward` (evade our ensemble + keep meaning) — already tested.
