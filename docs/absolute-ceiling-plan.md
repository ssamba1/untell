# The absolute ceiling of a closed-loop AI humanizer — and the plan to reach it

Synthesised from a 25-agent research sweep (12 evasion-lever families, each web-grounded then
adversarially verified) over the 2023–2026 literature. Every number is tagged in-loop vs held-out
and peer-reviewed vs preprint vs vendor. This is the maximum-effort successor to
[`free-ceiling-report.md`](free-ceiling-report.md) and [`free-ceiling-measured.md`](free-ceiling-measured.md):
it drops the $0 constraint and asks what the *highest* reachable ceiling is, with all levers on the table.

## TL;DR

- **Theoretical ceiling** (Sadasivan, TMLR 2024, arXiv:2303.11156): the best detector that can ever
  exist has `AUROC ≤ ½ + TV(M,H) − TV(M,H)²/2`. As an LLM's distribution approaches human, TV→0 and
  detection → a coin flip. Undetectability is provable — **but only at TV→0, which requires abandoning
  meaning.** Quality preservation is structurally incompatible with the theoretical floor.
- **Defensible, quality-preserving, held-out ceiling with the full stack (BERTScore ≥ 0.87):**
  - Open-source statistical detectors (Binoculars, Fast-DetectGPT, RoBERTa): **~2–8% TPR@1%FPR** — effectively defeated.
  - Current commercial classifiers (GPTZero, Originality): **~65–78% ASR** held-out, decaying to ~65% as they retrain.
  - Mixed panel (open + current commercial, no MAGE/Turnitin): **~75–82% ASR**.
  - Adversarially-trained MAGE-class: **AUROC ~0.89 floor** unless added to the training reward.
  - Turnitin multi-document baselining: **no published held-out attack exists** — out of reach of any single-document method.
- **The single highest-leverage move for untell** (I×F = 72): **surrogate distillation** — query the
  commercial detectors once (~$15–30), distill a local proxy, then optimise against it offline for free.
  It is the only lever that makes the detectors untell "can't put in the loop for free" optimisable.
  untell already ships the pieces (`training/surrogate.py`, `untell/detectors/commercial.py`) — it is wiring, not research.

## 1. The lever board (12 families, adversarially scored)

`I` = impact on the *real* ceiling (commercial, held-out, quality-preserving). `F` = feasibility in untell now. Ranked I×F.

| Rank | Lever | I | F | Verdict | Attack surface | untell gap |
|---|---|---|---|---|---|---|
| 1 | **Surrogate-distilled commercial proxy** | 8 | 9 | KEEP | GPTZero / Originality / Sapling | wire `surrogate.py` + `commercial.py`; harvest labels |
| 2 | **Test-time compute** (iterative depth + best-of-N + quality gate) | 7 | 9 | KEEP | statistical zero-shot + watermarks | multi-round mode; BERTScore gate |
| 3 | **Multi-detector GRPO reward** | 8 | 7 | KEEP | statistical + RoBERTa-family | reward ensemble in `rl_humanizer.py` |
| 4 | **Corpus-seeded SFT/DPO warm-start** | 7 | 8 | KEEP | domain-shift residuals | domain-matched human corpus in `dpo_humanizer.py` |
| 5 | **Base-model generation mode** | 7 | 6 | KEEP | RLHF-artifact detectors | strip chat template for open-weight sources |
| 6 | **Author-exemplar style conditioning** | 6 | 7 | KEEP | single-doc stylometric | style-transfer pass |
| 7 | **Strongest paraphraser model** (DIPPER-class) | 7 | 5 | KEEP | statistical + trained classifiers | replace surgical/structural rewriter |
| 8 | **RL reward-ensemble design** | 6 | 6 | KEEP | cross-architecture transfer | which mix generalises to held-out |
| 9 | **MT-pivot preprocessing** | 5 | 8 | KEEP (watermark path only) | KGW / Unigram / SIR watermarks | new `mt_pivot.py`, watermark-only |
| 10 | **Generator-side DPO/RL** | 7 | 4 | KEEP | RLHF artifacts at the source | only if you control generation |
| 11 | ~~RAG grounding~~ | 3 | 7 | DOWNGRADE | content only — leaves syntactic/RLHF signature | not worth a stage |
| 12 | ~~Honest eval~~ | — | — | (prerequisite) | measurement, not a ceiling-pusher | still required — Phase 4 |

Killed overclaims: HIP's "GPTZero 0%→100% human" (arXiv:2605.19516) is likely **stale** against
GPTZero's Paraphraser Shield (retrained on 12+ humanizer tools). AuthorMist's GPTZero 88%→12%
(arXiv:2503.08716) is **in-loop, not transfer**. Homoglyph/unicode attacks (96% ASR) are
**trivially normalised away** — untell correctly *scrubs* them rather than relying on them.

## 2. The stacked pipeline (one inference request)

Layers are additive because they attack **orthogonal** detector families.

```
[input text]
 0. Base-model check      — strip chat template if source is open-weight (arXiv:2605.19516)
 1. MT-pivot              — watermarked input only: EN→pivot→EN (OPUS-MT); detector check; else skip
 2. Corpus-seeded DPO rewriter  — warm-started on domain-matched human corpus
 3. Iterative adversarial loop  — max_rounds=5, BERTScore≥0.87 gate, early-exit on threshold
       └ per round: best-of-N=8, scored by surrogate ensemble + open detectors
 4. Stylometric conditioning    — if an author exemplar is available
 5. Surrogate-ensemble final score → one GRPO-policy pass if still above threshold
```

## 3. The ceiling, per detector family (with the binding constraint)

| Detector family | Held-out quality-preserving ceiling | Binding constraint | Evidence |
|---|---|---|---|
| Open statistical (Binoculars, Fast-DetectGPT, RoBERTa) | **TPR@1%FPR ~2–8%**, AUROC ~0.30–0.43 | quality gate stops the loop before the theoretical floor | StealthRL (arXiv:2602.08934); Adversarial Paraphrasing NeurIPS 2025 (arXiv:2506.07001) |
| Current commercial (GPTZero, Originality) | **~65–78% ASR** | GPTZero Paraphraser Shield; Originality residual AUROC 0.80–0.95 | GradEscape USENIX 2025 (arXiv:2506.08188): 78.5% Scribbr, 57.8% Sapling |
| Adversarially-retrained (MAGE, Turnitin AIR-1) | **AUROC ~0.80–0.89** | must be *in the training reward* to move | StealthRL: MAGE holds at 0.891 after full RL |
| Watermarks (KGW, Unigram, XSIR) | **TPR@1%FPR ~8–15%** | cross-lingual-hardened XSIR still falls to AUROC 0.53 | Sadasivan TMLR 2024: DIPPER-5-round drives watermark TPR 99.8%→9.7% |

**Single number:** against a mixed panel of open + currently-deployed commercial detectors (excluding
MAGE and Turnitin), the full stack reaches **~75–82% ASR at BERTScore ≥ 0.87**, decaying toward ~65%
over 6–12 months as commercial detectors retrain on humanizer corpora.

## 4. Four-phase build (tied to untell modules)

### Phase 1 — Inference-time quick wins (~1–2 days, no training)
- `--max-rounds N` early-exit loop in [`run.py`](https://github.com/ssamba1/untell/blob/main/untell/scripts/run.py) (default 3).
- BERTScore quality gate in [`rewriter/base.py`](https://github.com/ssamba1/untell/blob/main/untell/rewriter/base.py): reject + resample if `BERTScore < 0.87`.
- Confirm best-of-N is wired to detector-min selection (scaffolded at run.py:170–193); default N=5.
- New `untell/rewriter/mt_pivot.py`: OPUS-MT EN→DE→EN, invoked only under `--watermark-input`.
- `--no-system-prompt` base-model mode for open-weight sources.
- **Verify:** held-out Binoculars/Fast-DetectGPT at 3 rounds vs 1; BERTScore distribution; watermark TPR pre/post pivot.

### Phase 2 — Surrogate distillation (~1 week, highest ROI)
- New `scripts/harvest_labels.py`: query [`detectors/commercial.py`](https://github.com/ssamba1/untell/blob/main/untell/detectors/commercial.py) (GPTZero, Originality, Sapling) on 3–5k texts (HC3 + RAID + CC-news human) → `text,score` CSV. ~$15–30.
- Extend [`training/surrogate.py`](https://github.com/ssamba1/untell/blob/main/training/surrogate.py) with `--detector-name` → named checkpoints.
- Multi-detector ensemble in [`training/reward.py`](https://github.com/ssamba1/untell/blob/main/training/reward.py): `R = 0.4·gptzero + 0.35·originality + 0.25·sapling`.
- New `scripts/check_surrogate_drift.py`: weekly Spearman ρ vs live API; alert if ρ < 0.75.
- **Verify:** surrogate fidelity ρ ≥ 0.85 on held-out 500; ASR on commercial targets pre/post surrogate-guided selection.

### Phase 3 — RL policy training (~1–2 weeks, GPU)
- Multi-detector GRPO reward in [`training/rl_humanizer.py`](https://github.com/ssamba1/untell/blob/main/training/rl_humanizer.py): `R = R_det + 0.1·R_sem`, `R_det = 0.5·RoBERTa + 0.3·FastDetectGPT + 0.2·gptzero_surrogate`; DEPO-style Lagrangian rejects updates with BERTScore < 0.85.
- Corpus-seeded DPO warm-start in [`training/dpo_humanizer.py`](https://github.com/ssamba1/untell/blob/main/training/dpo_humanizer.py): chosen = domain-matched human, rejected = detector-failed outputs.
- **Add MAGE to the reward ensemble (weight 0.2)** — the single highest-value change to move the MAGE floor. It is open-source ([`detectors/mage.py`](https://github.com/ssamba1/untell/blob/main/untell/detectors/mage.py)), so in-loop is feasible.
- Trained checkpoint → drop-in for `LocalPolicyRewriter` ([`rewriter/local_policy.py`](https://github.com/ssamba1/untell/blob/main/untell/rewriter/local_policy.py)). Target: Binoculars AUROC < 0.45, BERTScore ≥ 0.87 on 200 held-out.
- **Verify:** per-detector AUROC pre/post; BERTScore; PPL vs human; 200-text held-out unseen in training.

### Phase 4 — Honest eval harness (~3 days, parallel)
- Separate read-only eval keys (`GPTZERO_EVAL_KEY`, …) never set in training env, in [`eval/eval_policy.py`](https://github.com/ssamba1/untell/blob/main/eval/eval_policy.py).
- TPR@1%FPR / TPR@5%FPR with thresholds calibrated on a held-out human set, in [`eval/report.py`](https://github.com/ssamba1/untell/blob/main/eval/report.py).
- Query each commercial detector 3× per sample; report mean ± std; flag std > 0.1.
- Track GPTZero "AI-paraphrase" sub-label and Turnitin bypasser flag as a separate column.
- `--lambda-sweep` Pareto curve (BERTScore 0.75→0.95) in [`eval/benchmark.py`](https://github.com/ssamba1/untell/blob/main/eval/benchmark.py).
- **Verify:** report shows TPR@1%FPR per detector on held-out text with calibrated thresholds and counter-detection rates; zero train/eval overlap.

## 5. Hard limits nobody beats

1. **MAGE-class adversarially-trained classifiers** — AUROC ~0.89 floor; only moves if MAGE is *in* the reward (Phase 3).
2. **Turnitin multi-document baselining** — uses submission history; multi-doc stylometry re-separates even after style-SFT+DPO (arXiv:2505.14608). No single-document attack touches it; no published held-out experiment exists for *any* lever.
3. **The Sadasivan bound needs exact distribution match** — AUROC→0.5 requires `TV→0`, incompatible with BERTScore ≥ 0.87. The gap between ~2–8% TPR@1%FPR and the 0% floor is not closeable without breaking meaning.
4. **Commercial retraining cadence** — surrogates decay in 6–12 months; requires the Phase 2 staleness monitor and periodic re-harvest. No static solution.
5. **Lexical-entropy floor of autoregressive sampling** (arXiv:2603.29454) — survives rewriting unless the *sampler* is changed; the GRPO policy in Phase 3 shifts it but does not eliminate it.

## The honest bottom line

The absolute ceiling is not one number — it is a Pareto frontier between **evasion** and **meaning/quality**.
- Willing to trash quality? → near-100% evasion of any text-only detector, today, free (temperature ≥1.1, recursive paraphrase, RL). The Sadasivan bound guarantees it.
- Insisting on readable, meaning-preserving output? → **~75–82% held-out ASR against a mixed open+commercial panel** with the full stack, and the frontier itself (MASH-class: ~94% ASR at PPL ~19) is the real wall.
- The two things no method beats: **out-of-band signals** (Turnitin keystroke/draft-history/baselining) and **adversarially-retrained detectors added to your own training loop after you ship**.

untell's loop is already the right shape. Its ceiling is gated by its *rewriter* (weak) and its *target*
(local proxies that don't predict commercial). Phases 1–3 fix both; Phase 4 keeps every number honest.
