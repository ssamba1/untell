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

## Documentation

- **[Quick Start](quickstart.md)** — install and run in 60 seconds
- **[How It Works](how-it-works.md)** — the closed loop explained
- **[CLI Reference](cli/untell.md)** — every command and option
- **[API Server](api-server.md)** — deploy the REST API
- **[Training](training.md)** — the GPU moat (RL against the ensemble)
- **[Detector Tiers](detectors.md)** — all 7+ detectors in the ensemble
- **[Research: Free Evasion Ceiling](research/free-ceiling.md)** — how far does $0 get you?
- **[Research: Humanizer Comparison](research/comparison.md)** — untell vs every free technique
- **[AI Tells Catalog](research/ai-tells.md)** — the 20+ signals the loop eliminates

## License

MIT — free to use, modify, and distribute.
