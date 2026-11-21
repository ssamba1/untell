# Train on a FREE online GPU (Colab / Kaggle)

Free 16GB T4 GPUs are enough to train the moat — no DigitalOcean, no cost. **Kaggle is the best free
option** (30 GPU-hrs/week, reliable); Colab is easiest but flakier.

## VRAM → model choice (free GPUs are 16GB T4)
| Model | Fits 16GB? | Flag |
|---|---|---|
| Qwen2.5-1.5B + LoRA | ✅ comfortable | (default LoRA) |
| **Qwen2.5-3B + QLoRA (4-bit)** | ✅ tight, works | `--load-4bit` |
| Qwen2.5-3B + full LoRA | ❌ OOM on 16GB | use `--load-4bit` |

## Kaggle (recommended — 30 GPU-hrs/week)
1. kaggle.com → Create → **Notebook** → Settings → **Accelerator: GPU T4 x2** (or P100). Internet: **On**.
2. In a cell:
```python
!git clone https://github.com/ssamba1/untell.git    # private repo: use a token URL or upload a zip
%cd untell
!pip install -q -e ".[train,full,eval]"
!python -m untell.training.rl_humanizer --smoke               # free dry-run, proves the loop works (~minutes)

# STEP 0 — the part that actually matters. Training against our LOCAL ensemble does NOT transfer to
# GPTZero/Originality (measured: RADAR 0.008 vs GPTZero 100% on the same humanized text). So first
# build a SURROGATE of the target detector — a small local model that mimics it — and make THAT the
# reward. Free path: public HC3/RAID. Targeted path: a CSV of (text, gptzero_score) from the API.
!python -m untell.training.surrogate --dataset hc3 --n 3000 --out out/surrogate     # ~minutes on a T4
# (targeted, once you've collected GPTZero labels:)
# !python -m untell.training.surrogate --dataset gptzero_labels.csv --out out/surrogate

# real train with REWARD = the surrogate (set UNTELL_SURROGATE_DIR — this is the whole point).
# With a surrogate the local detector tier is irrelevant to the reward, so --tier lite saves VRAM/time.
import os; os.environ["UNTELL_SURROGATE_DIR"] = "out/surrogate"
!python -m untell.training.rl_humanizer --model Qwen/Qwen2.5-3B-Instruct --tier lite --steps 150 --load-4bit
# or DPO (often steadier): !python -m untell.training.dpo_humanizer --model Qwen/Qwen2.5-3B-Instruct --tier lite --load-4bit
```
3. Download `out/rl-humanizer` from the notebook's Output. Done — $0. The trainer checkpoints every
   25 steps, so a session killed at the wall still leaves a usable adapter (`out/rl-humanizer/checkpoint-*`).
4. **Validate transfer:** run the trained model's output through real GPTZero (paste a few into the web
   tool, or the commercial API). If the surrogate-evading text also dents GPTZero, the surrogate
   transferred — collect more GPTZero labels and retrain the surrogate to push further. If a *general*
   (HC3/RAID) surrogate moves nothing, that's the signal to spend on a GPTZero-labeled surrogate.

## Google Colab (easiest)
- colab.research.google.com → Runtime → Change runtime type → **T4 GPU**.
- Same cells as above. Save `out/...` to Google Drive (`from google.colab import drive; drive.mount('/content/drive')`)
  because Colab wipes the VM on disconnect.
- Free Colab has session/idle limits (~12h, disconnects) — checkpoint to Drive; Colab Pro ($10/mo) gives
  L4/A100 + longer runs if you want headroom.

## Notes
- Private repo: pass a GitHub token in the clone URL (`https://TOKEN@github.com/ssamba1/untell.git`),
  or upload the repo as a dataset/zip.
- `--tier full` reward downloads the OSS detectors (RADAR/Binoculars optional) on first run; `--tier
  lite` is faster but a weaker reward. `--tier commercial` needs detector API keys set in the notebook.
- Always run `--smoke` first — it surfaces any trl/peft version drift in minutes before the real train.
