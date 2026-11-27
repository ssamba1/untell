# Report card: zerogpt-2023

*2026-11-21T19:30:05+00:00 · untell 0.4.0 · detector version early 2023 (scores recorded by Liang et al.) · threshold 0.5*

Corpus **liang2023** — 394 human, 352 AI documents (0 unscored) · fingerprint `f9fde1550bccada2…`

## False positives on human writing

**Overall:** 12.9% (51/394; 95% CI 10.0–16.6%)

| slice | false-positive rate |
|---|---|
| group: stanford-cs224n-abstracts | 0.0% (0/145; 95% CI 0.0–2.6%) |
| group: toefl-non-native | 52.7% (48/91; 95% CI 42.6–62.7%) |
| group: us-8th-grade | 1.1% (1/88; 95% CI 0.2–6.2%) |
| group: us-college-admissions | 2.9% (2/70; 95% CI 0.8–9.8%) |
| length: <150 words | 32.7% (48/147; 95% CI 25.6–40.6%) |
| length: 150–299 | 0.0% (0/96; 95% CI 0.0–3.8%) |
| length: 300–599 | 2.0% (2/99; 95% CI 0.6–7.1%) |
| length: 600+ | 1.9% (1/52; 95% CI 0.3–10.1%) |

Projected for honest writers at 16.62% per document (upper end of the 95% CI on the overall rate):

| documents | P(≥1 false flag) | per 1,000 writers |
|---:|---:|---:|
| 1 | 16.6% | 166 |
| 5 | 59.7% | 597 |
| 10 | 83.8% | 838 |
| 20 | 97.4% | 974 |
| 40 | 99.9% | 999 |

## Detection (AI documents)

- AUROC: 0.570
- recall at the shipped threshold: 23.9% (84/352; 95% CI 19.7–28.6%)
- recall with false positives capped at 0.5%: 0.0%
- recall with false positives capped at 1.0%: 0.0%
- recall with false positives capped at 5.0%: 18.8%
