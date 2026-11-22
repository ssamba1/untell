# Report card: hf:PirateXX/AI-Content-Detector

*2026-11-22T23:12:10+00:00 · untell 0.4.0 · detector version not recorded · threshold 0.5*

Corpus **liang2023+persuade-eval** — 1194 human, 352 AI documents (0 unscored) · fingerprint `1b95c5d1b67e55c0…`

## False positives on human writing

**Overall:** 2.0% (24/1194; 95% CI 1.4–3.0%)

| slice | false-positive rate |
|---|---|
| group: ell | 0.5% (2/400; 95% CI 0.1–1.8%) |
| group: non-ell | 1.0% (4/400; 95% CI 0.4–2.5%) |
| group: stanford-cs224n-abstracts | 0.0% (0/145; 95% CI 0.0–2.6%) |
| group: toefl-non-native | 19.8% (18/91; 95% CI 12.9–29.1%) |
| group: us-8th-grade | 0.0% (0/88; 95% CI 0.0–4.2%) |
| group: us-college-admissions | 0.0% (0/70; 95% CI 0.0–5.2%) |
| length: <150 words | 12.2% (18/148; 95% CI 7.8–18.4%) |
| length: 150–299 | 0.3% (1/377; 95% CI 0.0–1.5%) |
| length: 300–599 | 0.8% (4/528; 95% CI 0.3–1.9%) |
| length: 600+ | 0.7% (1/141; 95% CI 0.1–3.9%) |
| ell_status: No | 1.0% (4/400; 95% CI 0.4–2.5%) |
| ell_status: Yes | 0.5% (2/400; 95% CI 0.1–1.8%) |
| race_ethnicity: American Indian/Alaskan Native | 0.0% (0/3; 95% CI 0.0–56.1%) |
| race_ethnicity: Asian/Pacific Islander | 1.2% (1/84; 95% CI 0.2–6.4%) |
| race_ethnicity: Black/African American | 0.0% (0/112; 95% CI 0.0–3.3%) |
| race_ethnicity: Hispanic/Latino | 0.9% (3/351; 95% CI 0.3–2.5%) |
| race_ethnicity: Two or more races/Other | 0.0% (0/17; 95% CI 0.0–18.4%) |
| race_ethnicity: White | 0.9% (2/233; 95% CI 0.2–3.1%) |

Projected for honest writers at 2.97% per document (upper end of the 95% CI on the overall rate):

| documents | P(≥1 false flag) | per 1,000 writers |
|---:|---:|---:|
| 1 | 3.0% | 30 |
| 5 | 14.0% | 140 |
| 10 | 26.1% | 261 |
| 20 | 45.3% | 453 |
| 40 | 70.1% | 701 |

## Verdict stability under formatting-only edits

- variant-level flip rate: 0.0% (0/59; 95% CI 0.0–6.1%)
- documents with at least one flip: 0.0% (0/10; 95% CI 0.0–27.8%)
- median score spread across a document's variants: 0.000

## Detection (AI documents)

- AUROC: 0.759
- recall at the shipped threshold: 8.8% (31/352; 95% CI 6.3–12.2%)
- recall with false positives capped at 0.5%: 0.9%
- recall with false positives capped at 1.0%: 4.3%
- recall with false positives capped at 5.0%: 16.8%

