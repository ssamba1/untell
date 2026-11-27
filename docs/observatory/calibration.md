# Calibrating untell's full-tier verdict on held-out human text

**2026-11-22.** The full-tier verdict used to be `max(detector scores) >= 0.30`. Audited by
untell's own report card, it flagged 57% of 394 human essays and 92% of TOEFL essays by non-native
writers. The five local detectors sit on different scales, and MAGE gives the median pre-2022 human
document a score of 1.000, so the max was decided by whichever member was most miscalibrated for
the register at hand.

The shipped rule is **calibration v3** (`verdict_rule: "calibrated-v3"`, 2026-11-23): v2 plus a
sixth detector, ModernBERT ([`rasbt/ai-text-detector-modernbert`](open-detectors.md), Apache-2.0),
fitted the same way on the same 868 documents. The other five tables are v2's, unchanged; only the
new table and the cut differ. v1 (technical prose only) and v2 are kept below as the comparison.

ModernBERT was added because the [modern-essay recall check](modern-llm.md) found it was the only
audited open detector that caught a 2024 model's essays without flagging TOEFL writers. Those Qwen
essays chose it, so they are not a clean test of v3. Essays from a second 2024 model, SmolLM2, are
clean but did not separate the versions: v2 and v3 both caught all 60. A third, OLMo-2 (2025),
not used in any choice either: v2 32/60, v3 33/60 — one essay apart.

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
- **Fit corpus, v3:** v2's 868, with ModernBERT scored on each exactly as untell's `modernbert`
  detector scores at runtime (float32, its card's 8,192-token limit and temperature 1.5662,
  normalised input).
- **Evaluation:** every cut applied, unchanged, to corpora neither fit saw — including the TOEFL
  essays, which come from a different learner population than PERSUADE's.
- **Code and data:** [`untell/bench/calibrate_full.py`](../../untell/bench/calibrate_full.py);
  shipped table [`untell/detectors/calibration_full_v3.json`](../../untell/detectors/calibration_full_v3.json)
  (v2's: [`calibration_full_v2.json`](../../untell/detectors/calibration_full_v2.json));
  evaluations [`calibration-v1-evaluation.json`](calibration-v1-evaluation.json) (v1's fit, scored
  before the line-wrapping fix) [`calibration-v2-evaluation.json`](calibration-v2-evaluation.json) and
  [`calibration-v3-evaluation.json`](calibration-v3-evaluation.json) (its `old` column includes
  ModernBERT in the max; the old-rule column below does not).

Detector input is normalised for line wrapping and quote style before scoring; both were measured to
move verdicts on identical words.

## Held-out results

| corpus | label | old rule (max ≥ 0.30) | v1 | v2 | **v3 (shipped)** |
|---|---|---:|---:|---:|---:|
| PEPs, pre-2022 | human | 52/80 (65.0%) | 0/80 (0.0%) | 0/80 (0.0%) | **0/80 (0.0%)**; 95% CI 0.0–4.6% |
| Stanford CS224N abstracts | human | 61/145 (42.1%) | 0/145 (0.0%) | 0/145 (0.0%) | **0/145 (0.0%)**; 95% CI 0.0–2.6% |
| US 8th-grade essays | human | 36/88 (40.9%) | 2/88 (2.3%) | 0/88 (0.0%) | **0/88 (0.0%)**; 95% CI 0.0–4.2% |
| US college admissions essays | human | 43/70 (61.4%) | 8/70 (11.4%) | 5/70 (7.1%) | **5/70 (7.1%)**; 95% CI 3.1–15.7% |
| TOEFL essays, non-native writers | human | 84/91 (92.3%) | 21/91 (23.1%) | 18/91 (19.8%) | **14/91 (15.4%)**; 95% CI 9.4–24.2% |
| PERSUADE, English learners (held-out half) | human | 207/400 (51.7%) | 16/400 (4.0%) | 10/400 (2.5%) | **6/400 (1.5%)**; 95% CI 0.7–3.2% |
| PERSUADE, not English learners (held-out half) | human | 261/400 (65.2%) | 52/400 (13.0%) | 27/400 (6.8%) | **23/400 (5.8%)**; 95% CI 3.9–8.5% |
| GPT-3 college essays | AI | 31/31 (100.0%) | 31/31 (100.0%) | 31/31 (100.0%) | 31/31 (100.0%) |
| GPT-3 CS224N abstracts | AI | 145/145 (100.0%) | 109/145 (75.2%) | 107/145 (73.8%) | 100/145 (69.0%) |
| GPT-3 college essays, evasion-prompted | AI | 27/31 (87.1%) | 0/31 (0.0%) | 0/31 (0.0%) | 16/31 (51.6%) |
| GPT-3 CS224N abstracts, evasion-prompted | AI | 117/145 (80.7%) | 20/145 (13.8%) | 20/145 (13.8%) | 18/145 (12.4%) |
| Qwen2.5-1.5B essays, 2024 (chose ModernBERT; not clean) | AI | – | – | 9/60 (15.0%) | 28/60 (46.7%) |
| SmolLM2-1.7B essays, 2024 (clean; [results](modern-llm-smollm2.md)) | AI | – | – | 60/60 (100.0%) | 60/60 (100.0%); 95% CI 94.0–100% |
| OLMo-2-1B essays, 2025 (clean; [results](modern-llm-olmo2.md)) | AI | – | – | 32/60 (53.3%) | 33/60 (55.0%); 95% CI 42–67% |

AI recall across all GPT-3 text: old 90.9%, v1 45.5%, v2 44.9%, **v3 46.9%**. AUROC of the
calibrated aggregate on the Liang corpus: v1 0.762, v2 0.779, **v3 0.832**.

## By writer demographics (PERSUADE held-out half, n = 800)

False-positive rate by writer group under the old rule, v2 and v3, with 95% intervals (v1's
column is in the 2026-11-22 version of this page). Groups under 20 essays
are omitted.

```
## race_ethnicity
  Hispanic/Latino                    n=351  old  49.0% [44-54]   v2   3.4% [2-6]   v3   2.0% [1-4]
  White                              n=233  old  67.0% [61-73]   v2   7.3% [5-11]   v3   6.9% [4-11]
  Black/African American             n=112  old  59.8% [51-68]   v2   4.5% [2-10]   v3   3.6% [1-9]
  Asian/Pacific Islander             n= 84  old  72.6% [62-81]   v2   3.6% [1-10]   v3   2.4% [1-8]
## grade_level
  10.0                               n=268  old  48.1% [42-54]   v2   3.4% [2-6]   v3   3.4% [2-6]
  8.0                                n=231  old  62.8% [56-69]   v2   7.4% [5-11]   v3   4.8% [3-8]
  11.0                               n= 87  old  80.5% [71-87]   v2   2.3% [1-8]   v3   2.3% [1-8]
  unknown                            n= 84  old  59.5% [49-69]   v2   6.0% [3-13]   v3   3.6% [1-10]
  12.0                               n= 66  old  66.7% [55-77]   v2   4.5% [2-13]   v3   4.5% [2-13]
  9.0                                n= 40  old  55.0% [40-69]   v2   2.5% [0-13]   v3   2.5% [0-13]
  6.0                                n= 24  old  33.3% [18-53]   v2   0.0% [0-14]   v3   0.0% [0-14]
## economically_disadvantaged
  Economically disadvantaged         n=437  old  51.3% [47-56]   v2   3.4% [2-6]   v3   2.1% [1-4]
  Not economically disadvantaged     n=276  old  70.3% [65-75]   v2   6.5% [4-10]   v3   5.8% [4-9]
  unknown                            n= 87  old  57.5% [47-67]   v2   4.6% [2-11]   v3   4.6% [2-11]
## ell_status
  Yes                                n=400  old  51.8% [47-57]   v2   2.5% [1-5]   v3   1.5% [1-3]
  No                                 n=400  old  65.2% [60-70]   v2   6.8% [5-10]   v3   5.8% [4-8]
```

## What it means

- **Far fewer false accusations, everywhere tested.** The old rule flagged 49–73% of every race
  group in PERSUADE; v3 flags 2.0–6.9%. On technical prose and abstracts it flags none. Against v2,
  no held-out human group is flagged more often, and most are flagged less.
- **Still about half the recall on GPT-3 text** (46.9%), but v3 is the first version to catch
  evasion-prompted GPT-3 essays (16 of 31, against none for v1 and v2), and it catches about three
  times as many of a 2024 open model's essays as v2. On a second 2024 model's essays, the clean
  test, v2 and v3 both caught all 60, and on a third (OLMo-2) they differ by one essay (32 vs 33
  of 60). v3 has not lost recall on either clean test, and has not shown a gain on either.
- **TOEFL writers are still flagged most (15.4%).** ModernBERT lowered it from v2's 19.8%, and the
  intervals still overlap. TOEFL essays by adult learners are a different population from anything
  in the fit, so a verdict from these models on a non-native writer remains weak evidence.
- **Among US students the direction reverses.** PERSUADE's English learners are flagged less than
  their classmates under every rule, so "non-native" is not one population a single correction fixes.
- **If ModernBERT is unavailable** (no torch, or the model cannot be downloaded), the other five
  tables still apply against v3's cut (0.9851, v2's was 0.9826). That only makes the verdict
  slightly stricter than v2; it is never looser.

v3 applies on the full tier at the default threshold. A caller who passes their own `--threshold`
is asking about the raw max and gets the old rule; `verdict_rule` in every score result says which
applied.
