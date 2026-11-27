# Report card: untell-local-full

*2026-11-22T18:20:15+00:00 · untell 0.4.0 · detector version not recorded · threshold calibrated (the detector's own verdict)*

Corpus **python-peps@2022-11-29** — 80 human, 0 AI documents (0 unscored) · fingerprint `1780ebf0627c2b26…`

## False positives on human writing

**Overall:** 0.0% (0/80; 95% CI 0.0–4.6%)

| slice | false-positive rate |
|---|---|
| group: peps | 0.0% (0/80; 95% CI 0.0–4.6%) |
| length: 150–299 | 0.0% (0/20; 95% CI 0.0–16.1%) |
| length: 300–599 | 0.0% (0/24; 95% CI 0.0–13.8%) |
| length: 600+ | 0.0% (0/36; 95% CI 0.0–9.6%) |

Projected for honest writers at 4.58% per document (upper end of the 95% CI on the overall rate):

| documents | P(≥1 false flag) | per 1,000 writers |
|---:|---:|---:|
| 1 | 4.6% | 46 |
| 5 | 20.9% | 209 |
| 10 | 37.4% | 374 |
| 20 | 60.9% | 609 |
| 40 | 84.7% | 847 |

## Verdict stability under formatting-only edits

- variant-level flip rate: 0.0% (0/69; 95% CI 0.0–5.3%)
- documents with at least one flip: 0.0% (0/10; 95% CI 0.0–27.8%)
- median score spread across a document's variants: 0.006
