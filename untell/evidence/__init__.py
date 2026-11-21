"""Evidence about a detector verdict: how stable it is, what it implies, and what it is worth.

The modules here are the audit half of untell:

- :mod:`.stats`     — Wilson intervals, Bayes on a flag, per-person false-flag risk, recall@FPR
- :mod:`.perturb`   — formatting-only ("null") and light editor variants of a text
- :mod:`.scorers`   — one interface over local, commercial, command-line and manual detectors
- :mod:`.stability` — does the verdict on THIS text survive edits that cannot change authorship?
- :mod:`.rates`     — published, cited error rates for named detectors
- :mod:`.brief`     — the evidence brief (Markdown / HTML / JSON)
- :mod:`.report_card` — a detector's dated, versioned report card over a human corpus, and drift
- :mod:`.corpus`    — corpus loaders, including a git time-capsule of pre-LLM human writing

Everything is importable with the standard library alone.
"""
