# untell — the open-source AI humanizer that *closes the loop*

**Iteratively rewrite AI-generated text against live AI-detector scores until it reads human — while keeping your meaning, citations, and facts intact.**

[![CI](https://github.com/ssamba1/untell/actions/workflows/ci.yml/badge.svg)](https://github.com/ssamba1/untell/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/untell)](https://pypi.org/project/untell/)

---

## What makes untell different

Most "AI humanizers" do **one blind paraphrase pass** and plateau at 60–80% detector bypass. untell runs a **closed loop**: it *scores* your text against an ensemble of real AI detectors, *rewrites* using each detector's score as feedback (targeting the exact sentences that read as AI), and *re-scores* — repeating until the hardest detector stops flagging it **and** a semantic-similarity gate confirms the meaning is unchanged.

That iterative, detector-feedback approach is the strongest *training-free* technique in the published literature ([arXiv 2506.07001](https://arxiv.org/abs/2506.07001): −88% TPR@1%FPR, transfers across detectors, preserves meaning) — and **no shipping tool, open or commercial, actually does it.**

## Key capabilities

| Capability | untell | Others |
|---|---|---|
| **Closed detector-feedback loop** | ✅ | ❌ blind single pass |
| **Real detectors in the loop** | ✅ 8 local + 7 commercial | ❌ internal proxy only |
| **Semantic meaning gate** | ✅ NLI entailment + contradiction veto, over a similarity bar | ❌ no verification |
| **Per-sentence targeting** | ✅ rewrite only the flagged spans | ❌ whole-text reroll |
| **Citation lock** | ✅ byte-for-byte preserve | ❌ facts get mangled |
| **Free no-key path** | ✅ surgical rewriter ($0) | ❌ paid API required |
| **Run locally** | ✅ CPU, no GPU needed | ❌ cloud-only |
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
log](free-ceiling-measured.md)**: 24 numbered results, including every experiment that *failed* and
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
- **[Measured: the free evasion ceiling](free-ceiling-measured.md)** — the full log, 24 results
- **[Summary: the free-ceiling report](free-ceiling-report.md)** — the short version
- **[Humanizer comparison](humanizer-comparison.md)** — untell vs every free technique
- **[The 435-repo census](humanizer-census.md)** — what this field is actually made of
- **[Why this is the most complete open humanizer](why-best-open-repo.md)** — the argument, with its corrections
- **[Training runbook](free-training-runbook.md)** — the GPU path (RL against the ensemble)

## License

MIT — free to use, modify, and distribute.
