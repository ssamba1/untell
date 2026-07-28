# Free-GPU training runbook — the $0 path to the open-detector ceiling

Train untell's RL policy (the moat) for **$0**: no commercial detector keys, no paid API. Reward =
the **free weighted open-detector ensemble** (RoBERTa + Fast-DetectGPT + MAGE + RADAR), warm-started
by DPO on the **free HC3 human corpus**. This is the StealthRL regime that reached 97.6% ASR on open
detectors and transferred to held-out ones — reproducible on a free Kaggle T4 (30h/week) or Colab.

**What this buys / what it doesn't.** It reaches the *open-detector* ceiling and produces a trained
adapter that drops into `LocalPolicyRewriter` (single-pass, no key). It does **not** guarantee beating
GPTZero/Originality/Turnitin — that needs their APIs in the loop (paid), which you don't have. Measure
against free detectors + ZeroGPT (browser mode), and treat commercial transfer as unproven.

## Prereqerequisites (free)
- A free **Kaggle** account (Notebooks → GPU T4, 30h/week) or **Colab** (free T4).
- A free **Hugging Face** account + a write token (Kaggle: Add-ons → Secrets → `HF_TOKEN`). This is
  how the adapter survives a killed session — pushed to your private HF repo mid-run.

## Cell 1 — setup
```bash
git clone https://github.com/ssamba1/untell.git && cd untell
pip install -q -e ".[train,full,eval]"
python -m training.rl_humanizer --smoke   # MUST pass before spending GPU hours
```
`--smoke` runs a tiny model for 2 steps on the free lite reward — proves the pipeline works end-to-end.

## Cell 2 — DPO warm-start on the free human corpus (~20–30 min, no key)
```bash
python -m training.dpo_humanizer \
  --model Qwen/Qwen2.5-3B-Instruct \
  --use-human-corpus --n 500 \
  --load-4bit \
  --out out/dpo-humanizer \
  --hub-id YOUR_HF_USERNAME/untell-dpo-warm
```
`--use-human-corpus` builds preference pairs from HC3 (human answer preferred over the ChatGPT answer
on the same topic) — no teacher key. Adapter pushed to your HF repo on completion.

## Cell 3 — merge DPO into base (for the GRPO warm-start)
```python
import torch
from transformers import AutoModelForCausalLM
from peft import PeftModel
base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-3B-Instruct", torch_dtype=torch.bfloat16, device_map="auto")
PeftModel.from_pretrained(base, "out/dpo-humanizer").merge_and_unload().save_pretrained("out/dpo-merged")
```
(Or skip Cells 2–3 and GRPO from the raw base — DPO warm-start just needs fewer GRPO steps.)

## Cell 4 — incremental HF push (paste once; runs in the background)
Guards against the "trained 4h, session killed, lost everything" failure — uploads the latest
checkpoint every 10 min while training runs.
```python
import threading, time, subprocess
def _push(repo, folder, every=600):
    while True:
        time.sleep(every)
        subprocess.run(["huggingface-cli","upload",repo,folder,"--repo-type","model","--quiet"])
threading.Thread(target=_push, args=("YOUR_HF_USERNAME/untell-grpo","out/rl-humanizer"), daemon=True).start()
```

## Cell 5 — GRPO on the free ensemble (~4–8h; resume across sessions)
```bash
UNTELL_ENABLE_RADAR=1 \
python -m training.rl_humanizer \
  --model out/dpo-merged \
  --tier full --steps 150 --k 6 \
  --load-4bit \
  --reward-sim-floor 0.82 \
  --out out/rl-humanizer \
  --hub-id YOUR_HF_USERNAME/untell-grpo
```
- **No `UNTELL_SURROGATE_DIR`** → reward = the free weighted open-detector ensemble (the $0 path).
- `UNTELL_ENABLE_RADAR=1` includes the adversarially-trained RADAR detector (non-commercial license —
  fine for research training).
- **MAGE** (the hardest free detector) is now un-broken and carries the top reward weight (0.35).
- `--reward-sim-floor 0.82` = hard meaning gate; rewrites below it earn −1.0 (no quality collapse).
- Hits the 9h Kaggle wall? Next session, add `--resume out/rl-humanizer/checkpoint-125`.

You can also warm-start GRPO directly from the DPO adapter without the manual merge in Cell 3:
```bash
python -m training.rl_humanizer --model Qwen/Qwen2.5-3B-Instruct --dpo-init out/dpo-humanizer ...
```

## Cell 6 — deploy the adapter (local, no key)
Download the adapter from your HF repo, then point untell at it:
```bash
export UNTELL_POLICY_DIR=YOUR_HF_USERNAME/untell-grpo   # HF repo id works directly
python -m untell.scripts.run --rewriter auto "Furthermore, this underscores a transformative paradigm."
```
`get_rewriter()` auto-selects `LocalPolicyRewriter` when `UNTELL_POLICY_DIR` is set — the trained
policy rewrites in a single forward pass, no API, no loop.

## Measuring for free
- **A/B the policy vs the untuned base:** `python -m untell.scripts.run --rewriter base ...` on the
  same input, compare scores.
- **Free open-detector scores:** `python -m untell.scripts.score --tier full "<text>"`.
- **Real free web detector in the loop:** `--browser zerogpt` (needs `.[browser]` + `playwright
  install chromium`) — slow (~10s/check) but a genuine detector, no key.

## Budget
| Step | Time | GPU-h | Cost |
|---|---|---|---|
| smoke | ~2 min | — | $0 |
| DPO warm-start (500 pairs) | ~0.5 h | 0.5 | $0 |
| GRPO 150 steps | ~4.2 h | 4.2 | $0 |
| GRPO resume 151→250 | ~3.5 h | 3.5 | $0 |
| **Total** | **~8.5 h** | **~8.5** | **$0** (fits Kaggle 30h/week) |

The only thing this can't buy: a *proof* it beats GPTZero/Originality/Turnitin. That needs their paid
APIs in the loop. Everything up to the open-detector ceiling is free.
