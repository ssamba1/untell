# Report card: hf:rasbt/ai-text-detector-modernbert

*2026-11-23T19:15:53+00:00 · untell 0.4.0 · detector version not recorded · threshold 0.5*

Corpus **liang2023+persuade-eval** — 1194 human, 352 AI documents (0 unscored) · fingerprint `1b95c5d1b67e55c0…`

## False positives on human writing

**Overall:** 0.6% (7/1194; 95% CI 0.3–1.2%)

| slice | false-positive rate |
|---|---|
| group: ell | 1.2% (5/400; 95% CI 0.5–2.9%) |
| group: non-ell | 0.2% (1/400; 95% CI 0.0–1.4%) |
| group: stanford-cs224n-abstracts | 0.7% (1/145; 95% CI 0.1–3.8%) |
| group: toefl-non-native | 0.0% (0/91; 95% CI 0.0–4.1%) |
| group: us-8th-grade | 0.0% (0/88; 95% CI 0.0–4.2%) |
| group: us-college-admissions | 0.0% (0/70; 95% CI 0.0–5.2%) |
| length: <150 words | 0.0% (0/148; 95% CI 0.0–2.5%) |
| length: 150–299 | 1.1% (4/377; 95% CI 0.4–2.7%) |
| length: 300–599 | 0.6% (3/528; 95% CI 0.2–1.7%) |
| length: 600+ | 0.0% (0/141; 95% CI 0.0–2.7%) |
| ell_status: No | 0.2% (1/400; 95% CI 0.0–1.4%) |
| ell_status: Yes | 1.2% (5/400; 95% CI 0.5–2.9%) |
| race_ethnicity: American Indian/Alaskan Native | 0.0% (0/3; 95% CI 0.0–56.1%) |
| race_ethnicity: Asian/Pacific Islander | 2.4% (2/84; 95% CI 0.7–8.3%) |
| race_ethnicity: Black/African American | 0.9% (1/112; 95% CI 0.2–4.9%) |
| race_ethnicity: Hispanic/Latino | 0.6% (2/351; 95% CI 0.2–2.1%) |
| race_ethnicity: Two or more races/Other | 0.0% (0/17; 95% CI 0.0–18.4%) |
| race_ethnicity: White | 0.4% (1/233; 95% CI 0.1–2.4%) |

Projected for honest writers at 1.21% per document (upper end of the 95% CI on the overall rate):

| documents | P(≥1 false flag) | per 1,000 writers |
|---:|---:|---:|
| 1 | 1.2% | 12 |
| 5 | 5.9% | 59 |
| 10 | 11.4% | 114 |
| 20 | 21.5% | 215 |
| 40 | 38.4% | 384 |

## Verdict stability under formatting-only edits

- variant-level flip rate: 0.0% (0/59; 95% CI 0.0–6.1%)
- documents with at least one flip: 0.0% (0/10; 95% CI 0.0–27.8%)
- median score spread across a document's variants: 0.000

## Detection (AI documents)

- AUROC: 0.944
- recall at the shipped threshold: 21.0% (74/352; 95% CI 17.1–25.6%)
- recall with false positives capped at 0.5%: 15.9%
- recall with false positives capped at 1.0%: 26.4%
- recall with false positives capped at 5.0%: 58.0%

