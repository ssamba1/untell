# Report card: hf:fakespot-ai/roberta-base-ai-text-detection-v1

*2026-11-22T22:43:34+00:00 · untell 0.4.0 · detector version not recorded · threshold 0.5*

Corpus **liang2023+persuade-eval** — 1194 human, 352 AI documents (0 unscored) · fingerprint `1b95c5d1b67e55c0…`

## False positives on human writing

**Overall:** 21.4% (255/1194; 95% CI 19.1–23.8%)

| slice | false-positive rate |
|---|---|
| group: ell | 1.5% (6/400; 95% CI 0.7–3.2%) |
| group: non-ell | 5.8% (23/400; 95% CI 3.9–8.5%) |
| group: stanford-cs224n-abstracts | 100.0% (145/145; 95% CI 97.4–100.0%) |
| group: toefl-non-native | 65.9% (60/91; 95% CI 55.7–74.8%) |
| group: us-8th-grade | 0.0% (0/88; 95% CI 0.0–4.2%) |
| group: us-college-admissions | 30.0% (21/70; 95% CI 20.5–41.5%) |
| length: <150 words | 77.7% (115/148; 95% CI 70.3–83.7%) |
| length: 150–299 | 20.7% (78/377; 95% CI 16.9–25.1%) |
| length: 300–599 | 7.2% (38/528; 95% CI 5.3–9.7%) |
| length: 600+ | 17.0% (24/141; 95% CI 11.7–24.1%) |
| ell_status: No | 5.8% (23/400; 95% CI 3.9–8.5%) |
| ell_status: Yes | 1.5% (6/400; 95% CI 0.7–3.2%) |
| race_ethnicity: American Indian/Alaskan Native | 0.0% (0/3; 95% CI 0.0–56.1%) |
| race_ethnicity: Asian/Pacific Islander | 3.6% (3/84; 95% CI 1.2–10.0%) |
| race_ethnicity: Black/African American | 1.8% (2/112; 95% CI 0.5–6.3%) |
| race_ethnicity: Hispanic/Latino | 1.4% (5/351; 95% CI 0.6–3.3%) |
| race_ethnicity: Two or more races/Other | 5.9% (1/17; 95% CI 1.0–27.0%) |
| race_ethnicity: White | 7.7% (18/233; 95% CI 4.9–11.9%) |

Projected for honest writers at 23.77% per document (upper end of the 95% CI on the overall rate):

| documents | P(≥1 false flag) | per 1,000 writers |
|---:|---:|---:|
| 1 | 23.8% | 238 |
| 5 | 74.3% | 743 |
| 10 | 93.4% | 934 |
| 20 | 99.6% | 996 |
| 40 | 100.0% | 1000 |

## Verdict stability under formatting-only edits

- variant-level flip rate: 0.0% (0/59; 95% CI 0.0–6.1%)
- documents with at least one flip: 0.0% (0/10; 95% CI 0.0–27.8%)
- median score spread across a document's variants: 0.002

## Detection (AI documents)

- AUROC: 0.984
- recall at the shipped threshold: 99.7% (351/352; 95% CI 98.4–99.9%)
- recall with false positives capped at 0.5%: 69.9%
- recall with false positives capped at 1.0%: 72.2%
- recall with false positives capped at 5.0%: 89.2%
