#!/usr/bin/env bash
# One-shot setup + train on a fresh GPU box (DigitalOcean GPU Droplet, Ubuntu, NVIDIA driver+CUDA).
# Usage:  GITHUB_TOKEN=ghp_xxx bash setup_gpu.sh        (private repo)
#    or:  REPO_URL=https://github.com/you/untell.git bash setup_gpu.sh
set -euo pipefail

# Model: Qwen2.5-3B fits >=24GB VRAM (RTX 6000 Ada / L40S / H100). On a 20GB RTX 4000 Ada, run with
# MODEL=Qwen/Qwen2.5-1.5B-Instruct. Smoke-test the pipeline first: STEPS=2 MODEL=Qwen/Qwen2.5-0.5B-Instruct
MODEL="${MODEL:-Qwen/Qwen2.5-3B-Instruct}"
TIER="${TIER:-full}"
STEPS="${STEPS:-500}"
OUT="${OUT:-out/rl-humanizer}"

echo "== GPU check =="
nvidia-smi || { echo "No GPU / driver. Use a GPU Droplet with the AI/ML image."; exit 1; }

echo "== deps =="
sudo apt-get update -y && sudo apt-get install -y python3-venv git

# Resolve repo URL (inject token for a private repo).
if [ -n "${REPO_URL:-}" ]; then
  URL="$REPO_URL"
elif [ -n "${GITHUB_TOKEN:-}" ]; then
  URL="https://${GITHUB_TOKEN}@github.com/ssamba1/untell.git"
else
  URL="https://github.com/ssamba1/untell.git"
fi

[ -d untell ] || git clone "$URL" untell
cd untell

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[train,full]"

echo "== smoke test (proves the pipeline runs: tiny model, 2 steps) =="
python -m untell.training.rl_humanizer --smoke || { echo "smoke failed — fix before the full run"; exit 1; }

echo "== train (model=$MODEL tier=$TIER steps=$STEPS) =="
python -m untell.training.rl_humanizer --model "$MODEL" --tier "$TIER" --steps "$STEPS" --out "$OUT"
# DPO alternative (often more stable): python -m untell.training.dpo_humanizer --model "$MODEL" --tier "$TIER"

echo "== done =="
echo "Adapter at: $(pwd)/$OUT"
echo "Pull it back:  scp -r root@<droplet-ip>:$(pwd)/$OUT ./out/   — then destroy the droplet."
