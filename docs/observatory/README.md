# The Detector Observatory

Dated, versioned report cards for AI-text detectors, measured on a human corpus whose provenance
is a git timestamp, and compared run to run for silent model changes.

## The corpus

[`corpus-python-peps.json`](corpus-python-peps.json) lists 80 prose documents from
[python/peps](https://github.com/python/peps) exactly as they stood at commit `02d07ca`
(2022-11-29), the last commit before ChatGPT's public release. They were written before any tool
that could have written them was available, so the "human" label rests on a date, not on trust.

The text is not stored here. The manifest names the commit and paths, the
[workflow](../../.github/workflows/observatory.yml) rebuilds the corpus from git on every run, and
each report card records a SHA-256 fingerprint of the corpus, so a reader can confirm a card was
measured on the same documents.

**Limits, stated plainly.** This is one register: technical proposals written by experienced,
mostly native-English programmers. The first 80 files in path order skew toward early PEPs. A low
false-positive rate here says nothing about student essays, non-native writers or short text —
which is where the published evidence says detectors fail. The corpus exists to catch *drift*
cheaply and reproducibly, not to stand in for those audits. Run `untell report-card` on your own
corpus for those (see [auditing.md](../auditing.md)).

## Report cards

| detector | date | false positives | null-edit flips | card |
|---|---|---|---|---|
| untell-local-lite | 2026-11-21 | 1.2% (1/80; 95% CI 0.2–6.7%) | 0/100 variants | [md](untell-local-lite/2026-11-21.md) · [json](untell-local-lite/2026-11-21.json) |

Commercial detectors appear here once their API keys are configured as repository secrets and the
workflow is run with `publish`. Nothing in this table has been measured against a commercial
detector yet.

Compare with the same detector on HC3 forum answers: **30%** false positives
([Result 43](../free-ceiling-measured.md)). Same tool, same threshold, 25× the rate, because the
register changed. That gap is the single most important thing a false-positive rate needs
reported next to it.
