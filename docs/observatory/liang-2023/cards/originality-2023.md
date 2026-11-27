# Report card: originality-2023

*2026-11-21T19:30:05+00:00 · untell 0.4.0 · detector version early 2023 (scores recorded by Liang et al.) · threshold 0.5*

Corpus **liang2023** — 394 human, 352 AI documents (0 unscored) · fingerprint `f9fde1550bccada2…`

## False positives on human writing

**Overall:** 21.3% (84/394; 95% CI 17.6–25.6%)

| slice | false-positive rate |
|---|---|
| group: stanford-cs224n-abstracts | 7.6% (11/145; 95% CI 4.3–13.1%) |
| group: toefl-non-native | 75.8% (69/91; 95% CI 66.1–83.5%) |
| group: us-8th-grade | 1.1% (1/88; 95% CI 0.2–6.2%) |
| group: us-college-admissions | 4.3% (3/70; 95% CI 1.5–11.9%) |
| length: <150 words | 54.4% (80/147; 95% CI 46.4–62.3%) |
| length: 150–299 | 0.0% (0/96; 95% CI 0.0–3.8%) |
| length: 300–599 | 4.0% (4/99; 95% CI 1.6–9.9%) |
| length: 600+ | 0.0% (0/52; 95% CI 0.0–6.9%) |

Projected for honest writers at 25.63% per document (upper end of the 95% CI on the overall rate):

| documents | P(≥1 false flag) | per 1,000 writers |
|---:|---:|---:|
| 1 | 25.6% | 256 |
| 5 | 77.3% | 773 |
| 10 | 94.8% | 948 |
| 20 | 99.7% | 997 |
| 40 | 100.0% | 1000 |

## Detection (AI documents)

- AUROC: 0.640
- recall at the shipped threshold: 39.2% (138/352; 95% CI 34.2–44.4%)
- recall with false positives capped at 0.5%: 0.0%
- recall with false positives capped at 1.0%: 0.6%
- recall with false positives capped at 5.0%: 7.1%
