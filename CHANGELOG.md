# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed
- **Dead detectors no longer pin the score at a fake `0.5`.** `mage`/`hc3_roberta` previously swallowed
  a load failure and returned a neutral `0.5`, which silently pinned the ensemble `max` and made the
  loop's signal meaningless on a broken ML env. Failed detectors are now **excluded** from the
  aggregate (like `roberta_openai`/`fast_detectgpt` already were), surfaced under `failed_detectors`,
  and `score` reports the **effective tier that actually produced numbers** plus a `warning` on
  downgrade — so a full-tier run with a broken stack honestly reports `lite`, not a fake `full`.
- **Fail-fast on load errors.** A detector that fails to load is disabled for the rest of the process
  instead of re-attempting the heavy import on every call (fixes the "took forever" on broken envs).
- Added a **Troubleshooting** section (NumPy 2.x / `torch` mismatch, `mage` `id2label`, full-tier speed).

### Changed
- **Renamed the project to `untell`** (was `humanize`) to avoid the namespace collision with the popular
  PyPI/GitHub `humanize` library and for a distinct, collision-free brand. Package/import is now `untell`,
  console scripts are `untell-*`, and the skill is `/untell`. The `humanize` skill verb stays as plain English.

### Added
- **One-line installers** (`install.sh` / `install.ps1`) — install the skill in a single command.
- **Claude Code plugin** packaging (`.claude-plugin/plugin.json` + `marketplace.json`): install via
  `/plugin marketplace add ssamba1/untell` then `/plugin install untell@untell`.
- **In-browser AI detector** (`docs/demo.html`) — a client-side port of the lite scorer; paste text, get an
  instant AI-tell score, nothing uploaded.
- SEO-first README: badges, before/after proof up top, capability comparison table, and an FAQ targeting the
  real search queries (free AI humanizer, bypass GPTZero/Turnitin, meaning preservation).
- Community health files: `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `ROADMAP.md`, `CITATION.cff`,
  issue/PR templates.
- GitHub Pages landing site (`docs/index.html`) with `sitemap.xml` + `robots.txt`.

## [0.1.0] — research prototype

### Added
- **Closed-loop detector-feedback humanizer** packaged as a Claude Code skill (`/untell`) and Python CLIs
  (`untell-score`, `untell-loop`, `untell-verify`, `untell-prove`, `untell-sentences`).
- **Tiered detector ensemble:** lite (zero-dependency perplexity/burstiness), full (RoBERTa-OpenAI, HC3,
  MAGE, Fast-DetectGPT, GPT-2 perplexity), opt-in RADAR (paraphrase-robust), heavy (Binoculars), and a
  key-gated commercial tier (Originality.ai, GPTZero, Winston, Sapling, ZeroGPT, Copyleaks).
- **Semantic-similarity quality gate** (0.76 P-SP bar) + **preserve-lock** for citations/numbers/quotes/
  URLs/entities.
- **Per-sentence targeting** (`untell-sentences`).
- **Free browser checker** (Playwright) driving the live ZeroGPT web UI — no API key.
- **Evasion attacks** module: word-importance substitution, homoglyph substitution, hidden-character
  scrubbing, back-translation.
- **MCP server** (`untell-mcp`); `.docx`/`.pdf` input; hosted-LLM rewriter providers (`untell.rewriter`).
- **Eval harness** with per-detector beat-rates and a "hardest detector" headline (HC3 / RAID / builtin).
- **CI:** lite matrix (Python 3.9/3.11/3.12) + full-tier job loading real torch detectors. 139 tests, ruff-clean.
- **Live proof:** ZeroGPT 100%→0% in one loop; 100%→35%→0% with per-sentence feedback.
