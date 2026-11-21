# Report card: gptzero-2023

*2026-11-21T19:30:04+00:00 · untell 0.4.0 · detector version early 2023 (scores recorded by Liang et al.) · threshold 0.5*

Corpus **liang2023** — 394 human, 352 AI documents (6 unscored) · fingerprint `f9fde1550bccada2…`

## False positives on human writing

**Overall:** 12.6% (49/388; 95% CI 9.7–16.3%)

| slice | false-positive rate |
|---|---|
| group: stanford-cs224n-abstracts | 0.7% (1/139; 95% CI 0.1–4.0%) |
| group: toefl-non-native | 51.6% (47/91; 95% CI 41.5–61.6%) |
| group: us-8th-grade | 0.0% (0/88; 95% CI 0.0–4.2%) |
| group: us-college-admissions | 1.4% (1/70; 95% CI 0.3–7.7%) |
| length: <150 words | 33.3% (48/144; 95% CI 26.2–41.4%) |
| length: 150–299 | 0.0% (0/93; 95% CI 0.0–4.0%) |
| length: 300–599 | 1.0% (1/99; 95% CI 0.2–5.5%) |
| length: 600+ | 0.0% (0/52; 95% CI 0.0–6.9%) |

Projected for honest writers at 16.30% per document (upper end of the 95% CI on the overall rate):

| documents | P(≥1 false flag) | per 1,000 writers |
|---:|---:|---:|
| 1 | 16.3% | 163 |
| 5 | 58.9% | 589 |
| 10 | 83.1% | 831 |
| 20 | 97.2% | 972 |
| 40 | 99.9% | 999 |

## Detection (AI documents)

- AUROC: 0.748
- recall at the shipped threshold: 15.9% (56/352; 95% CI 12.5–20.1%)
- recall with false positives capped at 0.5%: 8.2%
- recall with false positives capped at 1.0%: 8.8%
- recall with false positives capped at 5.0%: 12.2%

