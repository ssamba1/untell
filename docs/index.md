# untell — an AI-detector auditing toolkit

**Measure whether an AI detector can be trusted: what it does to writing a human actually wrote, how stable its verdict is, and whether that verdict survives meaning-preserving edits.**

[![CI](https://github.com/ssamba1/untell/actions/workflows/ci.yml/badge.svg)](https://github.com/ssamba1/untell/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/untell)](https://pypi.org/project/untell/)

---

## What this is for

An AI detector gives you a number, and that number is increasingly used to make consequential accusations. This measures what it is worth. Measured here, at each tool's own shipped threshold: the full local ensemble flags **57% of 394 human essays** — 92% of TOEFL essays by non-native writers — in its own report card ([observatory](observatory/README.md)); on 30 HC3 answers it had measured 17%; the lite tier flagged **30%** on conversational prose; one bundled detector flags **6 of 8** human documents and another flags **89%** of them.

The rewrite loop is the instrument, not the product: score, edit under a meaning gate, re-score — because a verdict that collapses under meaning-preserving editing was never measuring authorship. Its result is a negative one, and it is stated as such: the loop moves the detectors it optimises against and **does not move a detector it has never seen**.

## Key capabilities

| Capability | What it does |
|---|---|
| **Evidence brief** (`untell brief`) | stability under edits that change no words, cited published error rates, Bayes on the flag, per-person false-flag risk — for one verdict on one document |
| **Any detector** | ✅ 8 local + 8 commercial adapters, `cmd:` for anything scriptable, `manual:` for scores recorded from a web UI (Turnitin) |
| **Report cards** (`untell report-card`) | false-positive rate by writer group and length with 95% intervals, per-writer rollups, recall at capped FPR |
| **Drift** (`untell drift`) | compares two report cards and flags silent model changes |
| **Human by timestamp** (`untell capsule`) | a human corpus from git history before 2022-11-30 |
| **Offline browser kit** | [`brief.html`](brief.html) — the same test with nothing uploaded |
| **Robustness probe** (`untell probe`) | detector-in-the-loop rewriting under a meaning gate; its finding is that gains do not transfer |
| **MCP server** | ✅ Claude Desktop integration | ❌ |
| **REST API server** | ✅ FastAPI, auth, OpenAPI | ❌ |
| **Open source** | ✅ MIT | ❌ closed SaaS |

## Quick install

```bash
pip install untell                     # zero-dependency lite tier
pip install "untell[full]"             # real detector ensemble on CPU
pip install "untell[server]"           # REST API server
```

One command to humanize:

```bash
untell humanize "Your AI-sounding paragraph here." --rewriter surgical
```

## The measurement log — start here

Most tools in this space publish a benchmark table. This one publishes **[the full measurement
log](free-ceiling-measured.md)**: 229 numbered results, including every experiment that *failed* and
every claim of ours that a later measurement refuted.

A sample of what is in there, because the refutations are the point:

| | |
|---|---|
| **Result 17** | The hypothesis that one stubborn detector sets the ceiling — **refuted**. The reported `max` is an envelope; different texts are caught by different detectors. |
| **Result 18** | A diversity gate that provided *no* diversity. Draw-to-draw similarity was identical to four decimals with it on and off. |
| **Result 21** | Two structural moves measured and then **declined**: passive→active reaches too little to justify the grammar risk, and first-person injection would make the tool assert a stance its input never had. |
| **Result 22** | The rewriter was emitting **sentence fragments**, invisible to every metric here, and fixing it **cost** 0.026 of evasion score. Both stated. |
| **Result 24** | The free tier called **60% of human writing AI**. Fixed by separating the reported verdict from the loop's target. |

Run `untell-audit` to re-check the claims in these documents against the code as it stands.

## Documentation

- **[Quick Start](quickstart.md)** — install and run in 60 seconds
- **[API Server](api-server.md)** — deploy the REST API
- **[What each function returns](result-shapes.md)** — the key that carries the answer, per entry point. They differ, and guessing wrong returns a plausible value rather than raising.
- **[Measured: the free evasion ceiling](free-ceiling-measured.md)** — the full log, 229 results
- **[Summary: the free-ceiling report](free-ceiling-report.md)** — the short version
- **[Humanizer comparison](humanizer-comparison.md)** — untell vs every free technique
- **[The 435-repo census](humanizer-census.md)** — what this field is actually made of
- **[Why this is the most rigorous open detector audit](why-best-open-repo.md)** — the argument, with its corrections
- **[Training runbook](free-training-runbook.md)** — the GPU path (RL against the ensemble)

## License

MIT — free to use, modify, and distribute.
