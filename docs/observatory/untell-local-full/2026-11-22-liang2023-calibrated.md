# Report card: untell-local-full

*2026-11-22T18:12:11+00:00 · untell 0.4.0 · detector version not recorded · threshold calibrated (the detector's own verdict)*

Corpus **liang2023** — 394 human, 352 AI documents (0 unscored) · fingerprint `f9fde1550bccada2…`

## False positives on human writing

**Overall:** 7.9% (31/394; 95% CI 5.6–11.0%)

| slice | false-positive rate |
|---|---|
| group: stanford-cs224n-abstracts | 0.0% (0/145; 95% CI 0.0–2.6%) |
| group: toefl-non-native | 23.1% (21/91; 95% CI 15.6–32.7%) |
| group: us-8th-grade | 2.3% (2/88; 95% CI 0.6–7.9%) |
| group: us-college-admissions | 11.4% (8/70; 95% CI 5.9–21.0%) |
| length: <150 words | 14.3% (21/147; 95% CI 9.5–20.9%) |
| length: 150–299 | 0.0% (0/96; 95% CI 0.0–3.8%) |
| length: 300–599 | 3.0% (3/99; 95% CI 1.0–8.5%) |
| length: 600+ | 13.5% (7/52; 95% CI 6.7–25.3%) |

Projected for honest writers at 10.95% per document (upper end of the 95% CI on the overall rate):

| documents | P(≥1 false flag) | per 1,000 writers |
|---:|---:|---:|
| 1 | 11.0% | 110 |
| 5 | 44.0% | 440 |
| 10 | 68.6% | 686 |
| 20 | 90.2% | 902 |
| 40 | 99.0% | 990 |

## Verdict stability under formatting-only edits

- variant-level flip rate: 0.0% (0/55; 95% CI 0.0–6.5%)
- documents with at least one flip: 0.0% (0/10; 95% CI 0.0–27.8%)
- median score spread across a document's variants: 0.000

## Detection (AI documents)

- AUROC: 0.824
- recall at the shipped threshold: 45.5% (160/352; 95% CI 40.3–50.7%)
- recall with false positives capped at 0.5%: 0.0%
- recall with false positives capped at 1.0%: 0.0%
- recall with false positives capped at 5.0%: 0.0%
