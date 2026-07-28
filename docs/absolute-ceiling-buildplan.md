# untell → absolute ceiling: the execution plan

Companion to [`absolute-ceiling-plan.md`](absolute-ceiling-plan.md) (the *what* and *why*). This is the
*how*: an execution-ready, code-grounded build plan produced by four architects reading the actual
`untell` modules. Every task cites `file:line`, states current reality, the concrete change, the test
that proves it, and a time estimate. Reality check up front: **untell is more built-out than a naive
plan assumes** — a large fraction of "Phase 1" already exists. The plan below separates *already done*
from *genuine gap* and only builds the gaps.

## Dependency graph

```
Phase 1 (inference, no GPU) ──┐
                              ├──> ships value immediately, unblocks nothing downstream
Phase 2 (surrogate distill) ──┼──> gptzero_surrogate feeds Phase 3 reward
                              │        ⤷ needs commercial API keys ($45–105 one-time)
Phase 3 (RL policy, GPU) ─────┘──> needs Phase 2 surrogate + MAGE-fix; fills LocalPolicyRewriter
Phase 4 (honest eval) ────────────> parallel to all; gates every number as credible
```

Critical path to the ceiling: **P2 → P3**. P1 and P4 run in parallel and independently.

## Effort & cost summary

| Phase | Code | Runtime | Cost | GPU |
|---|---|---|---|---|
| 1 — inference wins | ~11 h | — | $0 | none |
| 2 — surrogate distillation | ~7.5 h | ~24 h (rate-limited harvest) | $45–105 API | none |
| 3 — RL policy | ~16 h | ~9 h train | ~$1 spot-checks | free Colab/Kaggle T4 |
| 4 — honest eval harness | ~3.5 days | — | <$5 API | none |

---

# Phase 1 — Inference-time wins (no training)

**Reality:** the closed loop in [`run.py`](../untell/scripts/run.py) `untell_text()` already has `max_iters`,
`margin`, `confirm`, `polish`, best-of-N with detector-min selection (run.py:168–193), stall detection,
sentinel enforcement (run.py:185), and sentence-level targeted feedback. A `back_translation.py` MT
pivot already exists in [`attacks/`](../untell/attacks/back_translation.py). So most of the naive Phase-1
list is **done**. The genuine gaps:

| # | Task | File:line | Change | Test | Time |
|---|---|---|---|---|---|
| 1 | **Fix CompositeRewriter browser-tier scoring bug** | [composite.py:43-46](../untell/rewriter/composite.py) | In `--browser` mode `score_result["tier"]` = `"browser:zerogpt"`, fails the membership test, silently falls back to lite — so internal best-of optimizes the *wrong* signal. Skip internal scoring for non-scoreable tiers. | `test_composite_non_scoreable_tier_does_not_crash` | 1 h |
| 2 | **Zero-rewrite pre-flight exit** + `--max-rounds` alias + **per-detector thresholds** | [run.py:84-203](../untell/scripts/run.py) | Loop reports `iterations=1` even when input already passed. Add `already_passed` (iters=0). Add `detector_thresholds: dict` so you can require e.g. `mage<0.40 AND roberta<0.25` (only genuinely new semantic — current `_passed` is one global float). | `test_already_passed_exits_with_zero_iterations`, `test_per_detector_threshold_blocks_pass` | 2 h |
| 3 | **MT-pivot rewriter** (watermark path) | new [`rewriter/mt_pivot.py`](../untell/rewriter/mt_pivot.py); wire [base.py:121](../untell/rewriter/base.py), [run.py:309](../untell/scripts/run.py) | Wrap existing `BackTranslator`. Sentinels break MarianMT → swap `⟦HZ0000⟧`→`SENT0` (ALLCAPS survives MT), translate, restore, verify; drop-back to original if any sentinel lost (run.py:185 is the second net). Deps already in `.[full]`. | `TestMTPivotRewriter` (5 cases incl. sentinel survival + loss-fallback) | 4 h |
| 4 | **BERTScore quality gate** (upgrade, not replace) | [quality.py:27-96](../untell/scripts/quality.py), pyproject `[quality]` extra | Current gate = MiniLM cosine (0.76 bar) w/ token-overlap fallback. Add BERTScore-F1 as top-tier backend (bar 0.88): its *recall* catches propositional drift in prose that cosine misses. Sentinel lock already covers facts/numbers. | `test_bertscore_paraphrase_above_bar`, `test_bertscore_semantic_drift_below_bar` (skip if pkg absent) | 3 h |
| 5 | **`--rewriter base` mode** | [run.py:309](../untell/scripts/run.py), [local_policy.py:116](../untell/rewriter/local_policy.py) | `LocalPolicyRewriter(use_adapter=False)` already exists for base-vs-adapter A/B; just expose it in CLI + `UNTELL_POLICY_NO_SYSTEM=1`. Hosted LLM rewriters already send no system prompt — no change there. | `test_cli_rewriter_base_errors_without_policy_base` | 1 h |

**Exit criteria (measurable):** all 5 tests green; `pytest tests/ -x` no regressions; browser-mode composite no longer calls `score_text` internally; MT-pivot preserves 100% of sentinels under identity mock and falls back on loss; average `iterations` not increased on `eval/ceiling.py` fixtures.

---

# Phase 2 — Surrogate distillation (the highest-ROI lever)

**Reality:** [`surrogate.py`](../training/surrogate.py) already trains RoBERTa on soft `text,score` CSV with
`BCEWithLogitsLoss` — **no label-format mismatch** (GPTZero's `class_probabilities.ai` is already [0,1],
commercial.py:114). [`reward.py`](../training/reward.py) already routes to a surrogate via
`UNTELL_SURROGATE_DIR`. [`commercial.py`](../untell/detectors/commercial.py) adapters + `_retry` backoff
exist. Gaps: single-name surrogate, single-slot reward, no proactive rate limit, no harvest script, and
**no adversarial-transfer guard.**

### The one critical risk: adversarial-transfer brittleness
Optimizing against a RoBERTa surrogate can find rewrites that game *the surrogate's* decision boundary
while real GPTZero stays at 0.90+ (the `reward.py:3` note already measured RADAR 0.008 vs GPTZero 100%).
**Guard = in-loop, not post-hoc.** Two mitigations, both in the plan: (a) train **two** surrogates per
detector on different 80% subsets, reward = max of the two (halves exploitation speed); (b) a real-API
spot-check every 50 GRPO steps that aborts if `mean_real − mean_surrogate > 0.20` (Phase 3, Task 5).

| # | Task | File | Change | Time / Cost |
|---|---|---|---|---|
| 1 | **`scripts/harvest_labels.py`** (new) | imports `commercial.py` adapters | 4000 texts/detector (HC3 human+AI, RAID) → `text,score` CSV. Token-bucket throttle (GPTZero 6.5s, Originality 1.1s, Sapling 2.1s) on top of `_retry` backoff. SHA256 resumability + dedup. | 2 h + 6–14 h run, $40–100 |
| 2 | **`surrogate.py` `--detector-name`** | [surrogate.py:229](../training/surrogate.py) | Named checkpoints (`out/surrogates/gptzero/`); write `detector_name.txt`; `SurrogateDetector.name` self-restores (currently hardcoded `"surrogate"` at :204). Loss/format unchanged. | 1 h |
| 3 | **Multi-detector ensemble reward** | [reward.py:24-39](../training/reward.py) | `UNTELL_SURROGATE_DIRS=gptzero:...,originality:...` + `_WEIGHTS` (0.4/0.35/0.25) + `_AGG=mean\|max`. Backward-compatible with single `UNTELL_SURROGATE_DIR`. | 1.5 h |
| 4 | **`scripts/validate_surrogate.py`** (new) | — | Spearman ρ + AUROC of surrogate vs live API on 20% held-out. **Go/no-go: ρ≥0.85 AND AUROC≥0.90.** Fail → do not train. Consider Platt scaling if compressed. | 1 h |
| 5 | **`scripts/check_surrogate_drift.py`** (new) | — | Monthly: 50 texts, real-API-now vs surrogate; alert if ρ<0.80 (commercial detector retrained → re-harvest). | 0.5 h |

**Exit criteria:** 3 CSVs ≥3000 rows with **non-bimodal** score spread (needs partially-humanized mid-range texts); fidelity gate passes for all three; 300-step RL run drives surrogate ≤0.25 **and** a 30-text real-GPTZero spot-check ≤0.40 (the true transfer check); adversarial guard triggered ≤1×.

---

# Phase 3 — RL policy (GPU, the ceiling-raiser)

**Reality:** [`rl_humanizer.py`](../training/rl_humanizer.py) is a working GRPO trainer (Qwen2.5-3B, LoRA r=32,
`--smoke`, `--load-4bit`, `--hub-id`, `--resume`; the `--steps` dup is fixed). [`dpo_humanizer.py`](../training/dpo_humanizer.py)
exists but lacks checkpoint/resume/hub flags. [`local_policy.py`](../untell/rewriter/local_policy.py) integration
is **already correct** — set `UNTELL_POLICY_DIR` and `get_rewriter()` picks it up (base.py:135), HF-Hub IDs work directly.

**Confirmed blocker:** [`mage.py`](../untell/detectors/mage.py) is **dead in this env** (`_dead=True` at :63) — numpy 2.5.0 + transformers 5.12.1 reject MAGE's int-keyed `id2label` via `pipeline()`. Since MAGE is the single hardest detector (AUROC 0.89 floor) and the highest-value reward addition, fixing it is Task 1.

| # | Task | File:line | Change | Time |
|---|---|---|---|---|
| 1 | **Un-break MAGE** | [mage.py:36-63](../untell/detectors/mage.py) | Bypass `pipeline()`; `AutoModelForSequenceClassification.from_pretrained()` + patch `id2label` to str keys + direct softmax inference. Eliminates the numpy-C-API path that breaks. | 2 h |
| 2 | **Multi-detector weighted reward + hard gate** | [reward.py:51-75](../training/reward.py) | `R = Σwᵢ(1−Pᵢ) − λ_tells·tells_per_100w − λ_burst·low_burstiness`; **hard return −1.0** if MiniLM sim<0.82 or len<0.5×orig (DEPO-style, prevents StealthRL's 2.5/5 quality collapse). Weights: gptzero_surrogate .40, mage .22, radar .18, hc3 .10, fastdetect .07, ppl .03. Replace gameable bigram `fluency()` with `score_tells()`. | 5 h |
| 3 | **DPO human-corpus warm-start + prod flags** | [dpo_humanizer.py:21-79](../training/dpo_humanizer.py) | `build_pairs_human()`: HC3 `human_answers`=chosen, `chatgpt_answers`=rejected (natural domain match, **no API key**). Add `save_steps=25`, `resume`, `hub_id`, finally-guard, size check (parity w/ rl_humanizer). | 4 h |
| 4 | **DPO→GRPO bridge `--dpo-init`** | [rl_humanizer.py:118](../training/rl_humanizer.py) | `PeftModel.from_pretrained(base, dpo_dir).merge_and_unload()` then fresh r=32 LoRA on top. VRAM peak ~12GB on merge (tight on T4). | 3 h |
| 5 | **Wire reward + real-API guard + `--reward-sim-floor`** | [rl_humanizer.py:123](../training/rl_humanizer.py) | Reward call site backward-compatible; add the every-50-step real-API abort guard (Phase 2 risk). `UNTELL_ENABLE_RADAR=1` in runbook. | 2 h |
| 6 | **Deploy checkpoint** | env only | `UNTELL_POLICY_DIR=out/rl-humanizer` (or HF-Hub id). No code change. | 0.5 h |

### Free-GPU runbook (Kaggle T4, two ≤9h sessions, <30h/week)
```
pip install -e ".[train,full,eval]"; python -m training.rl_humanizer --smoke   # verify first
python -m training.surrogate --dataset hc3 --n 3000 --out out/surrogate --epochs 2   # ~30m
python -m training.dpo_humanizer --dataset hc3 --n 500 --load-4bit --out out/dpo --hub-id USER/untell-dpo
#   merge dpo→base (merge_and_unload) → out/dpo-merged
UNTELL_SURROGATE_DIR=out/surrogate UNTELL_ENABLE_RADAR=1 \
python -m training.rl_humanizer --model out/dpo-merged --tier full --steps 150 --k 6 \
  --load-4bit --out out/rl-humanizer --hub-id USER/untell-grpo   # ~4.2h; resume next session with --resume
```
**Incremental HF push** (avoid the "trained 4h, push 401'd" loss at rl_humanizer.py:110): background `huggingface-cli upload` thread every 10 min, or add a `--push-interval-steps` flag.

**Guards:** reward-hacking → real-API spot-check + tells penalty + MAGE(.22)/RADAR(.18) diversity so no single-detector overfit; quality collapse → hard sim gate 0.82 + length gate + `untell-tells`<5 post-check; forgetting → LoRA (frozen base) + `max_grad_norm=0.3` (already set) + DPO warm-start cuts steps to 250.

**Exit criteria:** on 200 held-out — full-tier max P(AI)<0.30 on ≥60% of samples; MiniLM sim≥0.80; tells_per_100w<6; burstiness CV≥0.35; **+25pp bypass vs untuned base** (`--vs-base`); manual 20-text real-GPTZero ≥12/20 bypass (else re-harvest surrogate).

---

# Phase 4 — Honest eval (the credibility backbone)

**Reality:** the current harness commits every sin that makes the field's numbers uncredible —
[`eval_policy.py:13`](../eval/eval_policy.py) literally confesses the circularity (loop key == eval key);
[`report.py:6`](../eval/report.py) reports bypass at an uncalibrated 0.30; single-query despite detector
non-determinism; discards GPTZero's `ai_paraphrase` anti-humanizer sub-label; no Pareto; no overlap guard.

| # | Task | File | Change | Time |
|---|---|---|---|---|
| 1 | **Eval-key isolation** | new `eval/held_out_detectors.py`, [commercial.py:57](../untell/detectors/commercial.py) | `EvalGPTZeroDetector` reads `GPTZERO_EVAL_KEY` (never the training key). `require_eval_keys()` guard at eval entry → exit 1 if absent. Extract `KEY_VAR` constants for clean subclassing. | 4 h |
| 2 | **Human calibration corpus** | [datasets.py:68](../eval/datasets.py) | `load_human_calibration_samples()` from HC3 `human_answers` + builtin fallback; provably disjoint from AI eval samples. | 3 h |
| 3 | **Multi-query averaging** | new `eval/multi_query.py` | 3× per sample, mean±std, `noisy` if std>0.10; noisy samples reported separately, not in headline. | 4 h |
| 4 | **Counter-detection stratum** | [commercial.py:112](../untell/detectors/commercial.py), report.py | `GPTZeroDetector.score_full()` surfaces `ai_paraphrase`; a "pass" with `ai_paraphrase>0.30` is flagged `counter_detected`. Turnitin bypasser stub column (N/A until institutional key). | 4 h |
| 5 | **TPR@1%FPR / @5%FPR** | new `eval/calibrate.py`, report.py | Threshold calibrated to ≤1%/5% FPR on the human corpus; report TPR there **alongside** the legacy 0.30 number. | 4 h |
| 6 | **Pareto sweep** | [benchmark.py:34](../eval/benchmark.py) | `--lambda-sweep` over BERTScore 0.75→0.95; ASR-vs-quality curve; Pareto-dominance flag vs baselines. Makes cherry-picking one quality level structurally impossible. | 5 h |
| 7 | **Train/eval overlap guard** | new `eval/overlap_guard.py` | SHA256 fingerprints; assert zero eval texts in any training/harvest CSV; exit non-zero on contamination. | 3 h |

### The credible-number checklist (all 8 required to publish a %)
1. eval key ≠ training key · 2. threshold calibrated to ≤1% FPR on held-out humans · 3. 3× queried, noisy (std>0.1) excluded · 4. `ai_paraphrase`/bypasser surfaced · 5. named BERTScore bar ≥0.87 + full Pareto shown · 6. zero train/eval fingerprint overlap · 7. n≥100 unique AI texts · 8. Wilson 95% CI reported.

**The one number the field lacks (and this produces):** *TPR of detection on untell-humanized text, at a threshold calibrated to ≤1% human FPR, measured by a commercial detector absent from the optimization loop, on texts whose fingerprints appear in no training CSV, 3×-queried with noisy samples excluded.*

---

# Master timeline, risks, go/no-go

**Sequencing:** P1 + P4-key-isolation week 1 (ship + credibility) → P2 harvest+distill week 2 (gated on ρ≥0.85) → P3 train week 3 (gated on MAGE-fix + P2) → P4 full harness measures P3. P4 tasks slot into any idle GPU/API wait.

**Global risk register:**
| Risk | Likelihood | Mitigation | Owner phase |
|---|---|---|---|
| Surrogate doesn't transfer to real API | High | dual-surrogate max + in-loop real-API abort guard; go/no-go ρ gate | P2/P3 |
| Quality collapse (StealthRL 2.5/5) | Medium | hard sim gate 0.82 + length gate + tells penalty + post-check | P3 |
| Commercial detector retrains → surrogate stale | Certain (6–12mo) | drift monitor + periodic re-harvest (standing task) | P2 |
| Kaggle session dies mid-train | Medium | incremental HF push + `--resume` | P3 |
| MAGE fix breaks under next transformers bump | Low | direct-load path pinned; test asserts it loads | P3 |
| Reported number is an in-loop artifact | High if unguarded | Phase 4 key isolation + calibration + overlap guard | P4 |

**Go/no-go gates:** (G1) P2 fidelity ρ≥0.85 & AUROC≥0.90 → else fix corpus/base before any GPU spend. (G2) P3 real-GPTZero spot-check ≥12/20 → else re-harvest, don't ship. (G3) P4 credible-number checklist 8/8 → else the % is not publishable.

**Hard ceiling this plan reaches** (from [`absolute-ceiling-plan.md`](absolute-ceiling-plan.md)): ~75–82% held-out
ASR at BERTScore≥0.87 on a mixed open+current-commercial panel, decaying to ~65% as detectors retrain.
Open statistical detectors → ~2–8% TPR@1%FPR. Not beaten by any phase: MAGE unless in-reward (Task P3-1
addresses it), Turnitin multi-doc baselining, the Sadasivan quality wall, autoregressive entropy floor.

**Total: ~4 weeks, ~35 h coding + ~33 h runtime, ~$50–110, one free GPU.**
```
Order of operations: P1-task-1 (composite bug) → P1 rest → P4 key-isolation → P2 → P3 → P4 measure.
```
