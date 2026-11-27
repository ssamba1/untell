# Report card: sapling-2023

*2026-11-21T19:30:05+00:00 · untell 0.4.0 · detector version early 2023 (scores recorded by Liang et al.) · threshold 0.5*

Corpus **liang2023** — 394 human, 352 AI documents (145 unscored) · fingerprint `f9fde1550bccada2…`

## False positives on human writing

**Overall:** 26.9% (67/249; 95% CI 21.8–32.7%)

| slice | false-positive rate |
|---|---|
| group: toefl-non-native | 68.1% (62/91; 95% CI 58.0–76.8%) |
| group: us-8th-grade | 4.5% (4/88; 95% CI 1.8–11.1%) |
| group: us-college-admissions | 1.4% (1/70; 95% CI 0.3–7.7%) |
| length: <150 words | 67.4% (62/92; 95% CI 57.3–76.1%) |
| length: 150–299 | 9.1% (2/22; 95% CI 2.5–27.8%) |
| length: 300–599 | 3.6% (3/83; 95% CI 1.2–10.1%) |
| length: 600+ | 0.0% (0/52; 95% CI 0.0–6.9%) |

Projected for honest writers at 32.74% per document (upper end of the 95% CI on the overall rate):

| documents | P(≥1 false flag) | per 1,000 writers |
|---:|---:|---:|
| 1 | 32.7% | 327 |
| 5 | 86.2% | 862 |
| 10 | 98.1% | 981 |
| 20 | 100.0% | 1000 |
| 40 | 100.0% | 1000 |

## Detection (AI documents)

- AUROC: 0.512
- recall at the shipped threshold: 41.8% (147/352; 95% CI 36.7–47.0%)
- recall with false positives capped at 0.5%: 1.7%
- recall with false positives capped at 1.0%: 1.7%
- recall with false positives capped at 5.0%: 8.5%
