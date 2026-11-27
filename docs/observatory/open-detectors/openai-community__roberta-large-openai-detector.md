# Report card: hf:openai-community/roberta-large-openai-detector

*2026-11-22T23:03:37+00:00 · untell 0.4.0 · detector version not recorded · threshold 0.5*

Corpus **liang2023+persuade-eval** — 1194 human, 352 AI documents (0 unscored) · fingerprint `1b95c5d1b67e55c0…`

## False positives on human writing

**Overall:** 2.8% (33/1194; 95% CI 2.0–3.9%)

| slice | false-positive rate |
|---|---|
| group: ell | 1.0% (4/400; 95% CI 0.4–2.5%) |
| group: non-ell | 1.5% (6/400; 95% CI 0.7–3.2%) |
| group: stanford-cs224n-abstracts | 3.4% (5/145; 95% CI 1.5–7.8%) |
| group: toefl-non-native | 15.4% (14/91; 95% CI 9.4–24.2%) |
| group: us-8th-grade | 4.5% (4/88; 95% CI 1.8–11.1%) |
| group: us-college-admissions | 0.0% (0/70; 95% CI 0.0–5.2%) |
| length: <150 words | 11.5% (17/148; 95% CI 7.3–17.6%) |
| length: 150–299 | 2.1% (8/377; 95% CI 1.1–4.1%) |
| length: 300–599 | 1.5% (8/528; 95% CI 0.8–3.0%) |
| length: 600+ | 0.0% (0/141; 95% CI 0.0–2.7%) |
| ell_status: No | 1.5% (6/400; 95% CI 0.7–3.2%) |
| ell_status: Yes | 1.0% (4/400; 95% CI 0.4–2.5%) |
| race_ethnicity: American Indian/Alaskan Native | 0.0% (0/3; 95% CI 0.0–56.1%) |
| race_ethnicity: Asian/Pacific Islander | 2.4% (2/84; 95% CI 0.7–8.3%) |
| race_ethnicity: Black/African American | 0.9% (1/112; 95% CI 0.2–4.9%) |
| race_ethnicity: Hispanic/Latino | 1.7% (6/351; 95% CI 0.8–3.7%) |
| race_ethnicity: Two or more races/Other | 0.0% (0/17; 95% CI 0.0–18.4%) |
| race_ethnicity: White | 0.4% (1/233; 95% CI 0.1–2.4%) |

Projected for honest writers at 3.86% per document (upper end of the 95% CI on the overall rate):

| documents | P(≥1 false flag) | per 1,000 writers |
|---:|---:|---:|
| 1 | 3.9% | 39 |
| 5 | 17.8% | 178 |
| 10 | 32.5% | 325 |
| 20 | 54.5% | 545 |
| 40 | 79.3% | 793 |

## Verdict stability under formatting-only edits

- variant-level flip rate: 0.0% (0/59; 95% CI 0.0–6.1%)
- documents with at least one flip: 0.0% (0/10; 95% CI 0.0–27.8%)
- median score spread across a document's variants: 0.002

## Detection (AI documents)

- AUROC: 0.770
- recall at the shipped threshold: 16.2% (57/352; 95% CI 12.7–20.4%)
- recall with false positives capped at 0.5%: 0.9%
- recall with false positives capped at 1.0%: 4.8%
- recall with false positives capped at 5.0%: 31.2%
