# Issue #40 — calibration design: per-detector FPR curves at sentence granularity

Status: closes issue #40 (slice 9, wave 5) — curves measured at HEAD `127e782`
(`.claude/probes/evidence/sentence_calibration_20260817_062512.json`; wave-4 run
`sentence_calibration_20260816_110405.json` reproduced at 3dp), ensemble simulation in
`.claude/probes/ensemble_calib_sim.py`, recommendation queued in
`.claude/human-queue.md`. **No thresholds changed** (RED — this document and the queue
entry only).

## Why sentence granularity is a separate calibration problem

The rewrite loop targets sentences, not documents. `untell/rewriter/targeted.py` scores each
sentence in isolation (`score_text(body, tier=tier)`) and flags it when
`selection_key(...)[0] >= min_score` with `min_score = 0.30` — the same `DEFAULT_THRESHOLD`
the document-level path uses. Paragraph- and sentence-length inputs are different regimes
for every detector here:

- `perplexity_burstiness` is half burstiness, and burstiness is undefined on one sentence
  (the audit found AUROC 0.000 on sentence probes for an old implementation — perfectly
  inverted — while passing the paragraph audit).
- `mage` saturates at exactly 1.0 on AI prose and is non-monotonically bad on short HUMAN
  text (measured in `score.py`: 20w 57%, 40w 100%, 80w 63%, 160w 27% — a sentence-length
  human fragment is mage's worst input).
- The ensemble aggregates with `max`, so one miscalibrated detector sets the sentence
  targeting floor for every tier that includes it — the same spreading mechanism the
  paragraph audit documents, at the granularity the loop actually consumes.

Slice 11 (20260815_204928-11.md) measured the headline: at shipped 0.30, 4 of 5 detectors
fire on 33–57% of human sentences (roberta_openai 0.40, hc3_roberta 0.3667, fast_detectgpt
0.3333, mage 0.5667; n=30/class). The curves below are the calibration data for fixing that.

## Measured curves (this run)

`python .claude/probes/calibration_sweep.py --pairs 40 --max-sentences 60`
(HC3, layout collapsed, sentences >= 10 words, n=60/class; evidence JSON holds the full
t=0.01..0.99 grid plus every raw sentence score). AUROC is threshold-free; FPR/TPR at
shipped 0.30 is what the loop experiences; `cut(FPR<=0.20)` is the least-damaging cut
(smallest t >= 0.30 meeting the budget) with its FPR/TPR; `t_largest` is the sweep's
conservative alternative (largest such t).

| detector | AUROC | FPR@0.30 | TPR@0.30 | cut(FPR<=.20) | FPR@cut | TPR@cut | t_largest |
|---|---|---|---|---|---|---|---|
| perplexity_burstiness | 0.8464 | 0.100 | 0.500 | 0.300 | 0.100 | 0.500 | 0.5337 |
| roberta_openai | 0.7950 | 0.533 | 0.933 | 0.736 | 0.200 | 0.617 | 0.9983 |
| hc3_roberta | 0.9614 | 0.383 | 1.000 | 0.994 | 0.200 | 0.950 | 0.9992 |
| fast_detectgpt | 0.8606 | 0.317 | 0.850 | 0.371 | 0.200 | 0.850 | 0.9988 |
| mage | 0.8801 | 0.717 | 1.000 | 1.000 | 0.000 | 0.000 | 1.0000 |

(Re-run at HEAD 127e782, `sentence_calibration_20260817_062512.json`, reproduced every
number at 3dp — the sweep and the loader are deterministic on CPU.)

## Reading the curves

- AUROC is threshold-free: it says whether the detector ranks AI > human at sentence
  granularity at all. FPR/TPR at a chosen threshold is what the loop actually experiences.
- A detector can have perfect AUROC and still be unusable at 0.30 (all five are near 1.0 at
  paragraph level; four are miscalibrated at sentence level) — the curve, not the AUROC, is
  the calibration artifact.
- The `cut(FPR<=0.20)` column is the smallest threshold >= shipped with at most 20% of
  human sentences flagged (ties handled by enumerating candidates between distinct scores),
  and `TPR@cut` is the AI-recall cost of moving there. `t_largest` is the most conservative
  cut (just below the top human score); for the three wide-overlap detectors it is
  effectively 0.998–1.0 and would destroy AI recall — the least-damaging cut is the one the
  design uses.
- mage's row is the important one: no cut below 1.0 exists with FPR <= 0.20 (its human
  sentence scores occupy a mode at 0.7–1.0), and at cut 1.0 its TPR is 0.000 — mage cannot
  be calibrated into a sentence-level detector at this budget; it must be excluded from
  sentence targeting (see Design, point 3).

## Design: per-detector sentence-granularity threshold table

The recommendation (queued, RED — a human applies it) is a per-detector, per-granularity
cut applied where sentence scores enter the ensemble, NOT a global threshold move:

1. **Where.** `_score_with_detectors_uncached` in `untell/scripts/score.py` aggregates
   per-detector scores; `targeted.py`'s `min_score` and the loop's `batch_score_texts`
   pass consume the result. A sentence-mode cut belongs at the aggregation layer (one
   place, inherited by every consumer), as a per-detector monotonic map
   `sentence_cut[detector]` applied to the clamped score, or — minimal-diff — as a
   per-detector `min_score` table consulted by `targeted.py` only.
2. **The mechanism has precedent.** `_verdict_threshold` already carries a mode-aware cut
   (stdlib 0.45 vs gpt2 0.30 for `perplexity_burstiness`) — same shape, new axis
   (granularity instead of mode).
3. **Values.** One row per detector from the measured curves at the chosen operating FPR
   (0.20 mirrors the audit's MAX_FPR; the queue entry states the numbers). Paragraph-level
   thresholds stay untouched — the document path is separately calibrated and separately
   documented in `untell/references/thresholds.md`.
   - perplexity_burstiness: 0.30 (already FPR 0.10 — no move)
   - roberta_openai: 0.74 (FPR 0.20, TPR 0.62) — or exclude at sentence level; its sentence
     AUROC 0.795 is the weakest ranker and its overlap is structural
   - hc3_roberta: 0.99 (FPR 0.20, TPR 0.95)
   - fast_detectgpt: 0.37 (FPR 0.20, TPR 0.85)
   - mage: exclude from sentence targeting (no cut below 1.0 meets the budget; document
     level only)
4. **Ensemble effect (simulated).** `.claude/probes/ensemble_calib_sim.py` on the raw
   sentence scores: the shipped ensemble (`max >= 0.30`) flags **90% of human sentences**
   (FPR 0.9000, TPR 1.0000, n=60). With the per-detector cuts above applied
   (`OR_d score_d >= cut_d`, every cut >= 0.30 so the shipped floor is never loosened):
   **FPR 0.4667, TPR 0.9833** — targeting FPR nearly halved at 1.7% TPR cost. A stricter
   0.10 per-detector budget moves the cuts to (roberta 0.83 / hc3 0.998 / fdg 0.48) and the
   simulated ensemble to **FPR 0.2833, TPR 0.9667** (same sim, `--target 0.10`). Note the
   union bound: per-detector FPR budgets do not add up to an ensemble FPR budget — the OR of
   five 0.20-budget detectors lands at 0.467, and tightening to 0.10 buys ~18 points
   (0.467 -> 0.283) at 1.7% additional TPR cost because mage's exclusion dominates the
   improvement.
5. **Global moves are the wrong shape (measured).** Same sim, global floor raised:
   `max >= 0.50` still FPR 0.8167 with TPR 1.0000 — mage's human mode sits at 0.7–1.0, so a
   global raise pays nothing until it clears mage entirely, and then it also clears
   roberta_openai's/fast_detectgpt's genuine AI sentences (AI means 0.74/0.64). This is
   why the fix must be per-detector.
6. **Validation protocol.** After any change, re-run this sweep (`.claude/probes/
   calibration_sweep.py`) and require: FPR <= 0.20 at sentence granularity per detector,
   TPR held within a stated margin, and the paragraph audit
   (`-m eval.detector_audit --pairs 20 --dataset hc3 --json`) unchanged.
7. **Scoping risks.** mage's sentence scores are bimodal (a mode at ~1.0 on some human
   sentences); excluding it from sentence targeting trades its 71.7% sentence FPR for a
   sentence-TPR contribution of 0 (its sentence TPR at any usable cut is 0). And the sweep
   is HC3-only — corpus-scoped like every FPR figure in this repo; a RAID sentence sweep is
   the follow-up before shipping a table as the default.
