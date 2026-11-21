# Report card: quillbot-2023

*2026-11-21T19:30:05+00:00 · untell 0.4.0 · detector version early 2023 (scores recorded by Liang et al.) · threshold 0.5*

Corpus **liang2023** — 394 human, 352 AI documents (145 unscored) · fingerprint `f9fde1550bccada2…`

## False positives on human writing

**Overall:** 30.9% (77/249; 95% CI 25.5–36.9%)

| slice | false-positive rate |
|---|---|
| group: toefl-non-native | 74.7% (68/91; 95% CI 64.9–82.5%) |
| group: us-8th-grade | 9.1% (8/88; 95% CI 4.7–16.9%) |
| group: us-college-admissions | 1.4% (1/70; 95% CI 0.3–7.7%) |
| length: <150 words | 73.9% (68/92; 95% CI 64.1–81.8%) |
| length: 150–299 | 9.1% (2/22; 95% CI 2.5–27.8%) |
| length: 300–599 | 7.2% (6/83; 95% CI 3.4–14.9%) |
| length: 600+ | 1.9% (1/52; 95% CI 0.3–10.1%) |

Projected for honest writers at 36.92% per document (upper end of the 95% CI on the overall rate):

| documents | P(≥1 false flag) | per 1,000 writers |
|---:|---:|---:|
| 1 | 36.9% | 369 |
| 5 | 90.0% | 900 |
| 10 | 99.0% | 990 |
| 20 | 100.0% | 1000 |
| 40 | 100.0% | 1000 |

## Detection (AI documents)

- AUROC: 0.585
- recall at the shipped threshold: 38.6% (136/352; 95% CI 33.7–43.8%)
- recall with false positives capped at 0.5%: 0.0%
- recall with false positives capped at 1.0%: 1.7%
- recall with false positives capped at 5.0%: 2.8%

