# Report card: hf:desklib/ai-text-detector-v1.01

*2026-11-22T23:46:15+00:00 · untell 0.4.0 · detector version not recorded · threshold 0.5*

Corpus **liang2023+persuade-eval** — 1194 human, 352 AI documents (0 unscored) · fingerprint `1b95c5d1b67e55c0…`

## False positives on human writing

**Overall:** 15.5% (185/1194; 95% CI 13.6–17.7%)

| slice | false-positive rate |
|---|---|
| group: ell | 5.0% (20/400; 95% CI 3.3–7.6%) |
| group: non-ell | 5.5% (22/400; 95% CI 3.7–8.2%) |
| group: stanford-cs224n-abstracts | 51.0% (74/145; 95% CI 43.0–59.0%) |
| group: toefl-non-native | 52.7% (48/91; 95% CI 42.6–62.7%) |
| group: us-8th-grade | 6.8% (6/88; 95% CI 3.2–14.1%) |
| group: us-college-admissions | 21.4% (15/70; 95% CI 13.4–32.4%) |
| length: <150 words | 52.0% (77/148; 95% CI 44.0–59.9%) |
| length: 150–299 | 17.5% (66/377; 95% CI 14.0–21.7%) |
| length: 300–599 | 6.1% (32/528; 95% CI 4.3–8.4%) |
| length: 600+ | 7.1% (10/141; 95% CI 3.9–12.6%) |
| ell_status: No | 5.5% (22/400; 95% CI 3.7–8.2%) |
| ell_status: Yes | 5.0% (20/400; 95% CI 3.3–7.6%) |
| race_ethnicity: American Indian/Alaskan Native | 33.3% (1/3; 95% CI 6.1–79.2%) |
| race_ethnicity: Asian/Pacific Islander | 3.6% (3/84; 95% CI 1.2–10.0%) |
| race_ethnicity: Black/African American | 6.2% (7/112; 95% CI 3.1–12.3%) |
| race_ethnicity: Hispanic/Latino | 6.0% (21/351; 95% CI 3.9–9.0%) |
| race_ethnicity: Two or more races/Other | 5.9% (1/17; 95% CI 1.0–27.0%) |
| race_ethnicity: White | 3.9% (9/233; 95% CI 2.0–7.2%) |

Projected for honest writers at 17.66% per document (upper end of the 95% CI on the overall rate):

| documents | P(≥1 false flag) | per 1,000 writers |
|---:|---:|---:|
| 1 | 17.7% | 177 |
| 5 | 62.1% | 621 |
| 10 | 85.7% | 857 |
| 20 | 97.9% | 979 |
| 40 | 100.0% | 1000 |

## Verdict stability under formatting-only edits

- variant-level flip rate: 8.5% (5/59; 95% CI 3.7–18.4%)
- documents with at least one flip: 30.0% (3/10; 95% CI 10.8–60.3%)
- median score spread across a document's variants: 0.301

## Detection (AI documents)

- AUROC: 0.984
- recall at the shipped threshold: 98.0% (345/352; 95% CI 96.0–99.0%)
- recall with false positives capped at 0.5%: 63.4%
- recall with false positives capped at 1.0%: 75.6%
- recall with false positives capped at 5.0%: 90.3%

