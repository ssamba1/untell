# Report card: openai-roberta-2023

*2026-11-21T19:30:05+00:00 · untell 0.4.0 · detector version early 2023 (scores recorded by Liang et al.) · threshold 0.5*

Corpus **liang2023** — 394 human, 352 AI documents (0 unscored) · fingerprint `f9fde1550bccada2…`

## False positives on human writing

**Overall:** 16.0% (63/394; 95% CI 12.7–19.9%)

| slice | false-positive rate |
|---|---|
| group: stanford-cs224n-abstracts | 1.4% (2/145; 95% CI 0.4–4.9%) |
| group: toefl-non-native | 58.2% (53/91; 95% CI 48.0–67.8%) |
| group: us-8th-grade | 9.1% (8/88; 95% CI 4.7–16.9%) |
| group: us-college-admissions | 0.0% (0/70; 95% CI 0.0–5.2%) |
| length: <150 words | 36.7% (54/147; 95% CI 29.4–44.8%) |
| length: 150–299 | 3.1% (3/96; 95% CI 1.1–8.8%) |
| length: 300–599 | 6.1% (6/99; 95% CI 2.8–12.6%) |
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

- AUROC: 0.593
- recall at the shipped threshold: 26.1% (92/352; 95% CI 21.8–31.0%)
- recall with false positives capped at 0.5%: 0.9%
- recall with false positives capped at 1.0%: 5.7%
- recall with false positives capped at 5.0%: 16.8%
