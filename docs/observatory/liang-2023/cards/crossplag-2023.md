# Report card: crossplag-2023

*2026-11-21T19:30:05+00:00 · untell 0.4.0 · detector version early 2023 (scores recorded by Liang et al.) · threshold 0.5*

Corpus **liang2023** — 394 human, 352 AI documents (0 unscored) · fingerprint `f9fde1550bccada2…`

## False positives on human writing

**Overall:** 16.0% (63/394; 95% CI 12.7–19.9%)

| slice | false-positive rate |
|---|---|
| group: stanford-cs224n-abstracts | 3.4% (5/145; 95% CI 1.5–7.8%) |
| group: toefl-non-native | 51.6% (47/91; 95% CI 41.5–61.6%) |
| group: us-8th-grade | 12.5% (11/88; 95% CI 7.1–21.0%) |
| group: us-college-admissions | 0.0% (0/70; 95% CI 0.0–5.2%) |
| length: <150 words | 34.0% (50/147; 95% CI 26.8–42.0%) |
| length: 150–299 | 5.2% (5/96; 95% CI 2.2–11.6%) |
| length: 300–599 | 8.1% (8/99; 95% CI 4.2–15.1%) |
| length: 600+ | 0.0% (0/52; 95% CI 0.0–6.9%) |

Projected for honest writers at 19.93% per document (upper end of the 95% CI on the overall rate):

| documents | P(≥1 false flag) | per 1,000 writers |
|---:|---:|---:|
| 1 | 19.9% | 199 |
| 5 | 67.1% | 671 |
| 10 | 89.2% | 892 |
| 20 | 98.8% | 988 |
| 40 | 100.0% | 1000 |

## Detection (AI documents)

- AUROC: 0.582
- recall at the shipped threshold: 23.9% (84/352; 95% CI 19.7–28.6%)
- recall with false positives capped at 0.5%: 3.1%
- recall with false positives capped at 1.0%: 6.8%
- recall with false positives capped at 5.0%: 15.1%
