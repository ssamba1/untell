# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- SEO-first README: badges, before/after proof up top, capability comparison table, and an FAQ targeting the
  real search queries (free AI humanizer, bypass GPTZero/Turnitin, meaning preservation).
- Community health files: `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `ROADMAP.md`, `CITATION.cff`,
  issue/PR templates.
- GitHub Pages landing site (`docs/index.html`).

## [0.1.0] — research prototype

### Added
- **Closed-loop detector-feedback humanizer** packaged as a Claude Code skill (`/humanize`) and Python CLIs
  (`humanize-score`, `humanize-loop`, `humanize-verify`, `humanize-prove`, `humanize-sentences`).
- **Tiered detector ensemble:** lite (zero-dependency perplexity/burstiness), full (RoBERTa-OpenAI, HC3,
  MAGE, Fast-DetectGPT, GPT-2 perplexity), opt-in RADAR (paraphrase-robust), heavy (Binoculars), and a
  key-gated commercial tier (Originality.ai, GPTZero, Winston, Sapling, ZeroGPT, Copyleaks).
- **Semantic-similarity quality gate** (0.76 P-SP bar) + **preserve-lock** for citations/numbers/quotes/
  URLs/entities.
- **Per-sentence targeting** (`humanize-sentences`).
- **Free browser checker** (Playwright) driving the live ZeroGPT web UI — no API key.
- **Evasion attacks** module: word-importance substitution, homoglyph substitution, hidden-character
  scrubbing, back-translation.
- **MCP server** (`humanize-mcp`); `.docx`/`.pdf` input; hosted-LLM rewriter providers (`humanize.rewriter`).
- **Eval harness** with per-detector beat-rates and a "hardest detector" headline (HC3 / RAID / builtin).
- **CI:** lite matrix (Python 3.9/3.11/3.12) + full-tier job loading real torch detectors. 139 tests, ruff-clean.
- **Live proof:** ZeroGPT 100%→0% in one loop; 100%→35%→0% with per-sentence feedback.
