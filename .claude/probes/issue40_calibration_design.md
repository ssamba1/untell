# Issue #40 — calibration design: per-detector FPR curves at sentence granularity

Status: evidence measured (see `evidence/sentence_calibration_*.json`); recommendation queued in
`.claude/human-queue.md`. **No thresholds changed** (RED — this document only).

## Why sentence granularity is a separate calibration problem

The rewrite loop targets sentences, not documents. `untell/rewriter/targeted.py` scores each
sentence in isolation (`score_text(body, tier=tier)`) and flags it when
`selection_key(...)[0] >= min_score` with `min_score = 0.30` — the same `DEFAULT_THRESHOLD`
the document-level path uses. Paragraph- and sentence-length inputs are different regimes for
every detector here:

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

See the evidence JSON for the full grid (t = 0.01..0.99 plus shipped 0.30) and every raw
sentence score. Table: AUROC, FPR/TPR at shipped 0.30, and the threshold that would bring
FPR to 0.20 (matching the audit's MAX_FPR) with the TPR kept there.

(TO BE FILLED FROM THE RUN)

## Reading the curves

- AUROC is threshold-free: it says whether the detector ranks AI > human at sentence
  granularity at all. FPR/TPR at a chosen threshold is what the loop actually experiences.
- A detector can have perfect AUROC and still be unusable at 0.30 (all five are near 1.0 at
  paragraph level; four are miscalibrated at sentence level) — the curve, not the AUROC, is
  the calibration artifact.
- The `t for FPR <= 0.20` column is the largest threshold with at most 20% of human
  sentences flagged (ties handled by enumerating candidates between distinct scores), and
  `TPR at t` is the AI-recall cost of moving there.

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
4. **Validation protocol.** After any change, re-run this sweep (`.claude/probes/
   calibration_sweep.py`) and require: FPR <= 0.20 at sentence granularity per detector,
   TPR held within a stated margin, and the paragraph audit
   (`-m eval.detector_audit --pairs 20 --dataset hc3 --json`) unchanged.
5. **Scoping risks.** mage's sentence scores are bimodal (a mode at ~1.0 on some human
   sentences); a threshold cut will trade a hard ceiling of FPR for a TPR loss whose size
   the curve states. And the sweep is HC3-only — corpus-scoped like every FPR figure in
   this repo; a RAID sentence sweep is the follow-up before shipping a table as the
   default.
