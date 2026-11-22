# Calibration v1: untell's full-tier verdict, refitted on held-out human text

**2026-11-22.** The full-tier verdict used to be `max(detector scores) >= 0.30`. Audited by
untell's own report card, it flagged 57% of 394 human essays and 92% of TOEFL essays by non-native
writers. The cause was in the per-detector scores: the five local detectors sit on different
scales, and MAGE gives the median pre-2022 human document a score of 1.000, so the max was decided
by whichever member was most miscalibrated for the register at hand.

## Method

- **Fit corpus:** 268 human documents committed before 2022-11-30 to five projects that appear in
  no evaluation set — rust-lang/book, pallets/flask, psf/requests, git/git and django/django
  (`untell capsule --limit 70`). Human by timestamp.
- **Rule:** each detector's score becomes its mid-rank percentile among the fit documents' scores
  for that detector (ties split, so a detector that gives most humans 1.000 maps 1.000 to a
  middling percentile). The aggregate is the highest percentile across detectors. The cut is the
  aggregate's 95th percentile on the fit corpus — a 5% target false-positive rate, chosen before any
  evaluation corpus was scored.
- **Evaluation:** the cut is applied, unchanged, to corpora the fit never saw.
- **Code:** [`untell/bench/calibrate_full.py`](../../untell/bench/calibrate_full.py); shipped table
  [`untell/detectors/calibration_full_v1.json`](../../untell/detectors/calibration_full_v1.json);
  full evaluation [`calibration-v1-evaluation.json`](calibration-v1-evaluation.json).

On the fit corpus itself the old rule flagged **84%** of human documents (226/268); the calibrated rule flags 4.5%.

Detector input is normalised for line wrapping and quote style before scoring (both were measured to move verdicts on identical words), and the fit and evaluation were run on that input.

## Held-out results

| corpus | label | old rule (max ≥ 0.30) | calibrated v1 |
|---|---|---:|---:|
| PEPs, pre-2022 | human | 52/80 (65.0%) | **0/80 (0.0%)**; 95% CI 0.0–4.6% |
| Stanford CS224N abstracts | human | 61/145 (42.1%) | **0/145 (0.0%)**; 95% CI 0.0–2.6% |
| US 8th-grade essays | human | 36/88 (40.9%) | **2/88 (2.3%)**; 95% CI 0.6–7.9% |
| US college admissions essays | human | 43/70 (61.4%) | **8/70 (11.4%)**; 95% CI 5.9–21.0% |
| TOEFL essays, non-native writers | human | 84/91 (92.3%) | **21/91 (23.1%)**; 95% CI 15.6–32.7% |
| GPT-3 college essays | AI | 31/31 (100.0%) | 31/31 (100.0%) |
| GPT-3 CS224N abstracts | AI | 145/145 (100.0%) | 109/145 (75.2%) |
| GPT-3 college essays, evasion-prompted | AI | 27/31 (87.1%) | 0/31 (0.0%) |
| GPT-3 CS224N abstracts, evasion-prompted | AI | 117/145 (80.7%) | 20/145 (13.8%) |

All AI text: recall **91% → 46%**. AUROC of the calibrated aggregate: 0.762.

## What it means

- **Far fewer false accusations.** On every human corpus the false-positive rate fell by a factor
  of four or more, and to zero on the two technical corpora.
- **Half the recall.** It now misses about half of GPT-3 text, and almost all of the text GPT-3 was
  prompted to make less detectable. The old rule's recall was bought with flagging most humans.
- **The bias is reduced, not removed.** TOEFL essays are flagged at 23%, about ten times the US
  8th-grade rate. A verdict from these models on a non-native writer remains weak evidence.
- **One fit register.** The fit corpus is technical documentation; it transfers well to technical
  text (0% on PEPs and abstracts) and less well to student essays. A fit on consented essay corpora
  is the next step ([roadmap](../../ROADMAP.md)).

The calibrated rule applies on the full tier at the default threshold. A caller who passes their
own `--threshold` is asking about the raw max and gets the old rule; `verdict_rule` in every score
result says which applied.
