# Calibrating untell's full-tier verdict on held-out human text

**2026-11-22.** The full-tier verdict used to be `max(detector scores) >= 0.30`. Audited by
untell's own report card, it flagged 57% of 394 human essays and 92% of TOEFL essays by non-native
writers. The five local detectors sit on different scales, and MAGE gives the median pre-2022 human
document a score of 1.000, so the max was decided by whichever member was most miscalibrated for
the register at hand.

The shipped rule is **calibration v2** (`verdict_rule: "calibrated-v2"`). v1, fitted the same
morning on technical prose alone, is kept below as the comparison.

## Method

- **Rule.** Each detector's score becomes its mid-rank percentile among that detector's scores on
  the fit corpus (ties split, so a detector that gives most humans 1.000 maps 1.000 to a middling
  percentile). The aggregate is the highest percentile across detectors. The cut is the aggregate's
  95th percentile on the fit corpus: a 5% target false-positive rate, chosen before any evaluation
  corpus was scored and not changed after.
- **Fit corpus, v1:** 268 human documents committed before 2022-11-30 to rust-lang/book,
  pallets/flask, psf/requests, git/git and django/django (`untell capsule --limit 70`).
- **Fit corpus, v2:** the same 268, plus 600 essays from the FIT half of PERSUADE 2.0 (US students,
  grades 6–12, written 2010–2020, CC BY 4.0): 300 by English learners and 300 not. The halves are
  assigned by a hash of the essay id ([`untell/bench/persuade.py`](../../untell/bench/persuade.py)),
  so no evaluation essay was ever in the fit.
- **Evaluation:** both cuts applied, unchanged, to corpora neither fit saw — including the TOEFL
  essays, which come from a different learner population than PERSUADE's.
- **Code and data:** [`untell/bench/calibrate_full.py`](../../untell/bench/calibrate_full.py);
  shipped table [`untell/detectors/calibration_full_v2.json`](../../untell/detectors/calibration_full_v2.json);
  evaluations [`calibration-v1-evaluation.json`](calibration-v1-evaluation.json) (v1's fit, scored
  before the line-wrapping fix) and [`calibration-v2-evaluation.json`](calibration-v2-evaluation.json).

Detector input is normalised for line wrapping and quote style before scoring; both were measured to
move verdicts on identical words.

## Held-out results

| corpus | label | old rule (max ≥ 0.30) | v1 | **v2 (shipped)** |
|---|---|---:|---:|---:|
| PEPs, pre-2022 | human | 52/80 (65.0%) | 0/80 (0.0%) | **0/80 (0.0%)**; 95% CI 0.0–4.6% |
| Stanford CS224N abstracts | human | 61/145 (42.1%) | 0/145 (0.0%) | **0/145 (0.0%)**; 95% CI 0.0–2.6% |
| US 8th-grade essays | human | 36/88 (40.9%) | 2/88 (2.3%) | **0/88 (0.0%)**; 95% CI 0.0–4.2% |
| US college admissions essays | human | 43/70 (61.4%) | 8/70 (11.4%) | **5/70 (7.1%)**; 95% CI 3.1–15.7% |
| TOEFL essays, non-native writers | human | 84/91 (92.3%) | 21/91 (23.1%) | **18/91 (19.8%)**; 95% CI 12.9–29.1% |
| PERSUADE, English learners (held-out half) | human | 207/400 (51.7%) | 16/400 (4.0%) | **10/400 (2.5%)**; 95% CI 1.4–4.5% |
| PERSUADE, not English learners (held-out half) | human | 261/400 (65.2%) | 52/400 (13.0%) | **27/400 (6.8%)**; 95% CI 4.7–9.6% |
| GPT-3 college essays | AI | 31/31 (100.0%) | 31/31 (100.0%) | 31/31 (100.0%) |
| GPT-3 CS224N abstracts | AI | 145/145 (100.0%) | 109/145 (75.2%) | 107/145 (73.8%) |
| GPT-3 college essays, evasion-prompted | AI | 27/31 (87.1%) | 0/31 (0.0%) | 0/31 (0.0%) |
| GPT-3 CS224N abstracts, evasion-prompted | AI | 117/145 (80.7%) | 20/145 (13.8%) | 20/145 (13.8%) |

AI recall across all GPT-3 text: old 90.9%, v1 45.5%, **v2 44.9%**. AUROC of the calibrated
aggregate: v1 0.762, v2 0.779.

## By writer demographics (PERSUADE held-out half, n = 800)

False-positive rate by writer group under each rule, with 95% intervals. Groups under 20 essays
are omitted.

```
## race_ethnicity
  Hispanic/Latino                    n=351  old  49.0% [44-54]   v1   4.6% [3-7]   v2   3.4% [2-6]
  White                              n=233  old  67.0% [61-73]   v1  14.6% [11-20]   v2   7.3% [5-11]
  Black/African American             n=112  old  59.8% [51-68]   v1   6.2% [3-12]   v2   4.5% [2-10]
  Asian/Pacific Islander             n= 84  old  72.6% [62-81]   v1  11.9% [7-21]   v2   3.6% [1-10]
## grade_level
  10.0                               n=268  old  48.1% [42-54]   v1   6.0% [4-9]   v2   3.4% [2-6]
  8.0                                n=231  old  62.8% [56-69]   v1   9.5% [6-14]   v2   7.4% [5-11]
  11.0                               n= 87  old  80.5% [71-87]   v1  18.4% [12-28]   v2   2.3% [1-8]
  unknown                            n= 84  old  59.5% [49-69]   v1   8.3% [4-16]   v2   6.0% [3-13]
  12.0                               n= 66  old  66.7% [55-77]   v1   9.1% [4-18]   v2   4.5% [2-13]
  9.0                                n= 40  old  55.0% [40-69]   v1   2.5% [0-13]   v2   2.5% [0-13]
  6.0                                n= 24  old  33.3% [18-53]   v1   0.0% [0-14]   v2   0.0% [0-14]
## economically_disadvantaged
  Economically disadvantaged         n=437  old  51.3% [47-56]   v1   5.5% [4-8]   v2   3.4% [2-6]
  Not economically disadvantaged     n=276  old  70.3% [65-75]   v1  14.1% [11-19]   v2   6.5% [4-10]
  unknown                            n= 87  old  57.5% [47-67]   v1   5.7% [2-13]   v2   4.6% [2-11]
## ell_status
  Yes                                n=400  old  51.8% [47-57]   v1   4.0% [2-6]   v2   2.5% [1-5]
  No                                 n=400  old  65.2% [60-70]   v1  13.0% [10-17]   v2   6.8% [5-10]
```

## What it means

- **Far fewer false accusations, everywhere tested.** The old rule flagged 49–73% of every race
  group in PERSUADE; v2 flags 3.4–7.3%. On technical prose and abstracts it flags none.
- **Half the recall.** It misses about half of GPT-3 text, and almost all of the GPT-3 text
  that was prompted to evade detection. The old rule's recall was bought with flagging most humans.
- **TOEFL writers are still flagged most (19.8%).** Adding US English learners to the fit helped
  them (2.5%) and helped TOEFL somewhat (23.1% → 19.8%), but TOEFL essays by adult learners are a
  different population. A verdict from these models on a non-native writer remains weak evidence.
- **Among US students the direction reverses.** PERSUADE's English learners are flagged less than
  their classmates under every rule, so "non-native" is not one population a single correction fixes.

v2 applies on the full tier at the default threshold. A caller who passes their own `--threshold`
is asking about the raw max and gets the old rule; `verdict_rule` in every score result says which
applied.
