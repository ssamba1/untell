#!/usr/bin/env bash
# One-shot setup + train on a fresh GPU box (DigitalOcean GPU Droplet, Ubuntu, NVIDIA driver+CUDA).
# Usage:  GITHUB_TOKEN=ghp_xxx bash setup_gpu.sh        (private repo)
#    or:  REPO_URL=https://github.com/you/humanize.git bash setup_gpu.sh
set -euo pipefail

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
  URL="https://${GITHUB_TOKEN}@github.com/ssamba1/humanize.git"
else
  URL="https://github.com/ssamba1/humanize.git"
fi

[ -d humanize ] || git clone "$URL" humanize
cd humanize

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[train,full]"

echo "== train (model=$MODEL tier=$TIER steps=$STEPS) =="
python -m training.rl_humanizer --model "$MODEL" --tier "$TIER" --steps "$STEPS" --out "$OUT"

echo "== done =="
echo "Adapter at: $(pwd)/$OUT"
echo "Pull it back:  scp -r root@<droplet-ip>:$(pwd)/$OUT ./out/   — then destroy the droplet."
