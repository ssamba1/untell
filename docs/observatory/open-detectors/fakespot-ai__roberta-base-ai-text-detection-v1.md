# Report card: hf:fakespot-ai/roberta-base-ai-text-detection-v1

*2026-11-22T21:10:47+00:00 · untell 0.4.0 · detector version not recorded · threshold 0.5*

Corpus **liang2023** — 394 human, 352 AI documents (0 unscored) · fingerprint `f9fde1550bccada2…`

## False positives on human writing

**Overall:** 57.4% (226/394; 95% CI 52.4–62.1%)

| slice | false-positive rate |
|---|---|
| group: stanford-cs224n-abstracts | 100.0% (145/145; 95% CI 97.4–100.0%) |
| group: toefl-non-native | 65.9% (60/91; 95% CI 55.7–74.8%) |
| group: us-8th-grade | 0.0% (0/88; 95% CI 0.0–4.2%) |
| group: us-college-admissions | 30.0% (21/70; 95% CI 20.5–41.5%) |
| length: <150 words | 78.2% (115/147; 95% CI 70.9–84.1%) |
| length: 150–299 | 77.1% (74/96; 95% CI 67.7–84.4%) |
| length: 300–599 | 23.2% (23/99; 95% CI 16.0–32.5%) |
| length: 600+ | 26.9% (14/52; 95% CI 16.8–40.3%) |

Projected for honest writers at 62.15% per document (upper end of the 95% CI on the overall rate):

| documents | P(≥1 false flag) | per 1,000 writers |
|---:|---:|---:|
| 1 | 62.1% | 621 |
| 5 | 99.2% | 992 |
| 10 | 100.0% | 1000 |
| 20 | 100.0% | 1000 |
| 40 | 100.0% | 1000 |

## Verdict stability under formatting-only edits

- variant-level flip rate: 6.2% (5/81; 95% CI 2.7–13.6%)
- documents with at least one flip: 33.3% (5/15; 95% CI 15.2–58.3%)
- median score spread across a document's variants: 0.025

## Detection (AI documents)

- AUROC: 0.954
- recall at the shipped threshold: 99.7% (351/352; 95% CI 98.4–99.9%)
- recall with false positives capped at 0.5%: 64.5%
- recall with false positives capped at 1.0%: 68.8%
- recall with false positives capped at 5.0%: 75.6%

