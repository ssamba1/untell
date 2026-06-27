# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- **Definitive comparison vs the free humanizers** — [`docs/humanizer-comparison.md`](docs/humanizer-comparison.md).
  Catalogs the free-humanizer field (SaaS + repos), their claims and mechanisms, and shows every free
  tool reduces to 3–4 techniques we already implement. A reproducible, $0 head-to-head (`untell-compare`)
  scores each technique class by ensemble P(AI), AI-tells, and meaning — finding our loop is the only
  mechanism that drives the AI-tells rate to **zero while preserving meaning**, and that the free tools'
  "99% bypass" claims don't survive independent testing (Originality flags the top "free" tool at 100% AI).
- **`untell tells` / `tells.py`** — a mechanical, detector-*independent* AI-tells scorer (em-dashes, the
  "delve" vocabulary, formulaic transitions, negated contrast, vague attribution, clichés, chatbot
  artifacts, burstiness). Unlike the detectors (which anti-correlate with human-ness on some text), fewer
  tells is unambiguously more human-reading — the right yardstick for "is this output more natural."
- **`untell compare` / `eval/compare_humanizers.py`** — runs a fixed corpus through the humanizer
  technique classes (synonym-swap, back-translation, our loop) and scores all three ways.
- **Unified `untell <subcommand>` CLI** (`untell humanize|score|tells|verify|compare|ceiling|…`) — one
  discoverable entry point instead of eight `untell-*` scripts (which still work). `untell` with no args
  lists everything; the no-rewriter error now points at the free `--rewriter surgical` path.

- **Measured the free inference-only evasion ceiling** — the data point the literature is missing.
  With a working local `torch`/`transformers` stack the full open-detector ensemble runs on CPU, so
  [`docs/free-ceiling-measured.md`](docs/free-ceiling-measured.md) reports the actual before→after
  movement of a training-free, $0 rewrite: flagged 0.90 → 0.60, mean max P(AI) 0.87 → 0.68 (n=10),
  with content-locked detectors immovable by any meaning-preserving rewrite — confirming the project's
  honest stance rather than any "undetectable" claim.
- **`SurgicalRewriter` (no-key, CPU) and `--rewriter surgical`** for `untell-loop` and `untell-ceiling`.
  PWWS/TextFooler-style word-importance substitution wrapped as a `Rewriter`, so the closed loop runs
  with no API key, no GPU, and no model download — which is what makes the free measurement possible.
- **`untell-ceiling`** harness (measure the loop's evasion vs the local ensemble), the **LLM-as-judge**
  detector (`commercial` tier), **best-of-N** rewriting, and the **local LoRA-policy** rewriter +
  A/B eval (`untell-eval-policy`), consolidated onto one branch.

### Fixed
- **RL adapter-save guard was checking the wrong bytes.** `rl_humanizer` summed `rglob("*")` (which
  includes `out/checkpoint-*/` dirs), so the "<1MB = save misfired" guard could pass even when the
  final adapter never saved. It now verifies `adapter_model.safetensors`/`.bin` directly, and wraps
  `train()`/`save_model()` in `try/finally` so an interrupted GPU session still flushes an adapter.
- **`LocalPolicyRewriter`** no longer imports `peft` for the base-only eval path, raises a clear error
  for `UNTELL_POLICY_4BIT` on a CPU box (instead of an opaque bitsandbytes failure), and reads the
  generation device from a real parameter (multi-GPU/CPU-offload safe).
- **`LLMJudgeDetector`** percentage disambiguation (`>=2.0`, so a stray "1.5" clamps to ~1.0 instead
  of becoming 0.015); `Detector.score` protocol typed `float | None` to match the None-exclusion path.

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
