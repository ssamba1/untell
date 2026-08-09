# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- **`untell-audit`** (`untell.scripts.audit`) — machine-checks every claim the documentation makes about
  the code: detector and rewriter counts, console-script declarations *and* whether their entry points
  actually resolve, CLI flags (by source inspection, not `--help` scraping), census cross-checks,
  env-var documentation, cross-document links, and calibration constants. Claims are split into
  **derivable** (re-computed from the code; a mismatch fails CI) and **measured** (cannot be re-derived,
  so the check is that the number states its provenance). Runs on every build.
- **`untell-latex`** (`untell.scripts.latex`) — `.tex`-aware handling: `prose_only()` strips maths,
  environments and commands so the detector scores prose rather than markup, plus `cite_keys()`,
  `bib_keys()`, `dropped_citations()` and `unresolved_citations()` for verifying a rewrite against a
  `.bib`. `LOCKED_ENVIRONMENTS` is the single source of truth, imported by `preserve.py`.
- **Environment-variable reference** in the README — all 20 `UNTELL_*` variables, with `untell-audit`
  failing the build when a variable exists in the code but not in the table.
- **Mechanical-soundness and reachability test batteries** — `test_output_is_mechanically_sound.py`
  reads real rewriter output for fragments, stacked conjunctions and bracket imbalance (a tell
  catalogue scores a sentence fragment as perfectly clean); `test_everything_registered_can_fire.py`
  asserts every registered detector, rewriter and meaning gate is reachable from the shipped code path.
- **Rich terminal output** (`untell.rich_output`) — colored before/after comparison tables, word-level
  diff highlighting, progress bars, and AI-score bars. Auto-detects when ``rich`` is installed
  (`pip install untell[rich]`); degrades gracefully to plain text otherwise.
- **Interactive web demo** (`docs/demo.html`) — professional dark-mode UI with live before/after
  scoring, word-level diff, style selector, and rewriter selector. Connects to the API server.
- **Structural + Composite rewriters** — `--rewriter structural` (sentence-level transforms) and
  `--rewriter composite` (structural + surgical chained) for the best free $0 path. Both always
  available, no API key, no GPU.
- **`untell humanness` CLI command** — scores text 0-100 combining AI-tells density + detector
  ensemble max + burstiness. Includes `--tier`, `--file`, `--json` flags.
- **CI/CD PyPI publish workflow** (`.github/workflows/publish.yml`) — builds and publishes to PyPI
  on tagged releases using trusted publishing. One-click release process.
- **14 rewriter style modes** on CLI — `--style` now accepts: casual, professional, academic, blunt,
  storytelling, journalistic, technical, persuasive, empathetic, humorous, poetic, instructional,
  conversational, minimalist.
- **REST API server** (`untell.api_server`, `untell-serve`) — a FastAPI service with
  OpenAPI docs, API-key auth, CORS, and 7 endpoints: health, score, humanize, tells, sentences, verify,
  ceiling. Deployable behind any process manager or Docker. (`pip install "untell[server]"`)
- **Local LLaMA-as-judge detector** (`untell.detectors.local_judge`) — any HuggingFace instruct model
  as an AI detector (Qwen2.5, LLaMA, Mistral). Defaults to Qwen2.5-1.5B. **Heavy tier at every model
  size**: measured at 3.7s per call against 0.03–0.06s for the rest of the full tier, for AUROC 0.514
  on labelled pairs. No API key, no rate limits, no cost per call. Selectable via `$UNTELL_JUDGE_MODEL`.
- **Domain-adaptive style engine** — 14 voice modes (was 6). New: technical, persuasive, empathetic,
  humorous, poetic, instructional, conversational, minimalist. Passed as `--style <voice>` to any
  rewriter or API call.
- **Professional documentation site** — mkdocs-material with dark/light theme, full CLI reference,
  API server docs, training guide, research results. Served at `/docs` in the API server.
- **Batched detector scoring** — `batch_score_texts()` scores multiple texts with one detector-load
  instead of N. Used by `score_sentences()` (N sentences → 1 detector load) and `importance()` +
  `surgical_substitute()` in the surgical rewriter (O(words) → O(1) detector loads).
- **`untell verify --tier <name>`** — verify against local detector ensemble without commercial API keys.
  Defaults to `--tier=full`; pass `--tier commercial` for commercial-only.
- **Exponential-backoff retry** (`untell._retry`) for all API call sites — Anthropic/OpenAI rewriters,
  LLM-as-judge, and all commercial detector HTTP calls.
- **Expanded surgical rewriter synonym map** — ~22 → ~180+ entries covering the full AI-tells catalog.
- **MCP server expansion** — added `tells`, `ceiling`, `compare`, and `rewriter="surgical"` param.
- **Pre-commit hooks** — `.pre-commit-config.yaml` (ruff, trailing-whitespace, EOF-fixer, JSON/YAML,
  merge-conflict, LF enforcement).
- **Test coverage** — new `test_retry.py` (8), `test_unicode_tricks.py` (16), `test_mcp_server.py` (1),
  `test_datasets.py` (6), `test_baselines.py` (10), `test_local_judge.py` (4), `test_api_server.py` (8).
  Total: 262 tests (+53 from the 209 baseline).
- **One-line installers** (`install.sh` / `install.ps1`) — install the skill in a single command.
- **Claude Code plugin** packaging (`.claude-plugin/plugin.json` + `marketplace.json`): install via
  `/plugin marketplace add ssamba1/untell` then `/plugin install untell@untell`.
- **Browser demo** (`docs/demo.html`) — a front-end for the REST API: paste text, get before/after
  scoring and a word-level diff. It does **not** score in the browser; the text is POSTed to an
  `untell-server` instance, which is your own machine unless you point `?api=` somewhere else.
  (An earlier entry here described the page as scoring locally and promised the text stayed on the
  machine. It never did either. A privacy promise the shipped page does not keep is worse than no
  promise, so `untell-audit` now fails the build if any document makes that claim while the page
  still contains a `fetch(`.)
- SEO-first README: badges, before/after proof up top, capability comparison table, and an FAQ targeting the
  real search queries (free AI humanizer, bypass GPTZero/Turnitin, meaning preservation).
- Community health files: `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `ROADMAP.md`, `CITATION.cff`,
  issue/PR templates.
- GitHub Pages landing site (`docs/index.html`) with `sitemap.xml` + `robots.txt`.
- **Definitive comparison vs the free humanizers** — [`docs/humanizer-comparison.md`](docs/humanizer-comparison.md).
  tool reduces to 3–4 techniques we already implement. A reproducible, $0 head-to-head (`untell-compare`)
  scores each technique class by ensemble P(AI), AI-tells, and meaning — finding our loop is the only
  mechanism that drives the AI-tells rate to **zero while preserving meaning**, and that the free tools'
  "99% bypass" claims don't survive independent testing (Originality flags the top "free" tool at 100% AI).
- **`untell tells` / `tells.py`** — a mechanical, detector-*independent* AI-tells scorer (em-dashes, the
  "delve" vocabulary, formulaic transitions, reader-steering openers, negated contrast, participial
  trailers, vague attribution, clichés, sycophancy, chatbot artifacts, inflated copula, **hedge-stacking,
  false-range breadth, rule-of-three staccato, markdown artifacts, semicolon crutch**, burstiness).
  Unlike the detectors (which anti-correlate with human-ness on some text), fewer tells is unambiguously
  more human-reading — the right yardstick for "is this output more natural." Honest scope: it mechanizes
  the regex-able readable tells, not the semantic ones (no-concrete-particulars, false both-sides
  balance, over-comprehensiveness) or the statistical ones only a trained detector sees.
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
- Added a **Troubleshooting** section (NumPy 2.x / `torch` mismatch, `mage` `id2label`, full-tier speed).

### Changed
- **Rewriter rates are now matched to a human corpus, not chosen.** Clause-merge connectors are drawn
  with the frequencies measured on the human half of a paired corpus (`, and ` 0.659 … `, though ` 0.007,
  where the rewriter previously emitted `though` 29 times); sentence-fronting is budgeted to the human
  0.20 rate, parentheses to 0.80 per 100 words and contractions to 0.67 per 100 words. Both columns of
  the corpus were checked — several transforms were firing far *under* the human rate, not over.
- **`best_of` defaults to 3** (was 1), and per-iteration progress is now wired to the CLI — it had been
  defined, tested, and called from nowhere.
- **The lite tier's verdict threshold is separate from the loop's target.** Reusing one number made the
  always-available tier flag 60% of *human* text; a calibrated `verdict_threshold` carried on the result
  brings that to 15%.
- **Surgical rewriter** — `importance()` and `surgical_substitute()` now batch detector calls via
  `batch_score_texts()`. Complexity drops from O(words × detectors × synonyms) to O(1) detector loads.
- **Per-sentence scoring** — uses `batch_score_texts()` for O(1) instead of O(n) detector loads.
- **`untell verify` exit code** — returns 0 when no checkers configured (was 1).
- **Training pipeline** — removed deprecated `prepare_model_for_kbit_training` (peft>=0.14 incompatible).
- **Env-var consistency** — renamed `HUMANIZE_ENABLE_RADAR` → `UNTELL_ENABLE_RADAR`;
  `HUMANIZE_BROWSER_SITES` → `UNTELL_BROWSER_SITES` (backward compat maintained).
- **Commercial detectors** — all 6 adapters now return `None` (not `0.5`) on empty/unavailable text,
  matching the `Detector` protocol contract. The ensemble correctly excludes them.
- **Module-level imports** — `verify.py` imports commercial adapters lazily (inside `verify()`), not at
  module load, so broken installs don't crash import.
- **File read hardening** — `errors="replace"` on all 7 `open(encoding="utf-8")` calls to prevent
  `UnicodeDecodeError` on invalid input.
- **Confirm re-score** — now operates on the final restored text (not masked text with sentinel tokens),
  ensuring the noise-guard catches detector activation on real citations/numbers.
- **Polish step** — runs on restored text, compares similarity against the original input.
- **Edge-case hardening** — `_MAX_INPUT_CHARS=50,000` truncation guard in `score_text()` and
  `batch_score_texts()`.
- **Version** — bumped to `0.2.0` (beta classifiers on PyPI).
- **Detector registry** — includes `LocalJudgeDetector` in the ensemble.
- **Renamed the project to `untell`** (was `humanize`) to avoid the namespace collision with the popular
  PyPI/GitHub `humanize` library and for a distinct, collision-free brand. Package/import is now `untell`,
  console scripts are `untell-*`, and the skill is `/untell`. The `humanize` skill verb stays as plain English.

### Fixed
- **`.tex` input was a complete no-op.** `document` is an environment, so preserve-lock masked the entire
  file and the rewriter saw nothing to change. End-to-end score on a LaTeX document: 0.6261 → 0.0815.
- **Sentence-boundary detection ignored half the sentinels.** `_plain_register` re-stashes preserve-locks
  as NUL-delimited indices, but the boundary check looked only for `⟦HZ…⟧`, so a sentence beginning with a locked
  citation was invisible to every structural transform.
- **Substituted phrasal verbs split from their pronoun objects** — `applying → putting to work` produced
  "putting to work **it** accurately". The swap now declines a particle-tailed substitute before a
  pronoun. `harnessing → putting to work` carried the same latent bug.
- **Fourteen synonym-map replacements emitted a tell the catalogue itself lists**, and the map was missing
  the inflected forms of words it already knew (`leverage` was covered, `leverages` and `leveraging` were
  not), so the most common surface form of an over-used word passed through untouched.
- **The API server's rate-limit dictionary grew without bound** — one entry per client, never reclaimed.
  Stale buckets are now evicted opportunistically under a 4096-entry soft cap.
- **`perplexity_burstiness` was anti-correlated and saturating.** The always-available lite detector
  scored every sentence *in isolation* and averaged, discarding the context that makes AI text
  predictable — measured gap −0.198 (AI text scoring *below* human text) at paragraph length — and
  its linear clamps floored a realistic technical document to exactly **0.0**, so the loop declared
  it human and rewrote nothing. Rewritten as one in-context pass with logistic calibration fitted to
  labelled data: **AUROC 0.999** on 200 held-out HC3 pairs, nothing saturated. Long documents are now
  walked in overlapping windows instead of truncated at GPT-2's 1024 tokens (1023 → 4088 tokens
  scored on a 3918-word document).
- **`local_judge` raised on every call** — it passed `device_map=`, which hard-requires `accelerate`,
  an undeclared dependency, while `available()` reported True. Moved to the **heavy** tier once it
  worked: 3.7s per call against 0.03–0.06s for every other detector, for AUROC 0.514.
- **Meaning gate admitted role swaps.** "The company sued the regulator" → "The regulator sued the
  company" scored 0.987 bidirectional entailment. A new predicate-argument veto
  (`untell.scripts.roles`) catches 9/9 role permutations with 0/13 false vetoes; the gate now admits
  **0 of 13** meaning-changing rewrites (was 4).
- **Preserve-lock covered 25 of 57 fact types**; 16 more locked only *partially*, which reads as
  protected while the rest stays mutable ("16 GB" locked "16"; "March 15, 2024" left the month
  rewritable; "5 mg" locked nothing). Now 55/57 full, 0 partial — including fenced and inline code.
- **40 of 51 invisible-watermark carriers passed through `scrub_hidden`** while `count_hidden`
  reported the text clean. Bidi controls and variation selectors are now stripped where they are
  payload and kept where they are load-bearing (RTL text, emoji).
- **A browser readout showing both figures returned the HUMAN percentage as P(AI)**
  ("Human 45% / AI 55%" → 0.45).
- **A NaN from any detector reported the text as human**, in invalid JSON; a non-numeric score
  crashed `score_text` outright.
- **`humanness()` scored text MORE human when the detector stack was dead** (71.1 vs 60.2), reading
  the unscored placeholder as a confident "not AI".
- **`untell-ceiling --dataset hc3` silently measured five canned paragraphs** — HC3's hub repo ships
  a loading script that `datasets>=3` rejects, and the failure was caught and logged.
- **Rewriter output quality**: "Dr. Smith published" came out as "Dr, though smith published";
  clause joins stacked conjunctions ("and plus,", "while and,"); substitutions dropped the original
  capitalisation ("Furthermore," → "also,").
- **Duplicate `"therefore"` key** in word_importance.py synonym map.
- **Unused import** `score_text` in `sentences.py`.
- **RL adapter-save guard was checking the wrong bytes.** `rl_humanizer` summed `rglob("*")` (which
  includes `out/checkpoint-*/` dirs), so the "<1MB = save misfired" guard could pass even when the
  final adapter never saved. It now verifies `adapter_model.safetensors`/`.bin` directly, and wraps
  `train()`/`save_model()` in `try/finally` so an interrupted GPU session still flushes an adapter.
- **`LocalPolicyRewriter`** no longer imports `peft` for the base-only eval path, raises a clear error
  for `UNTELL_POLICY_4BIT` on a CPU box (instead of an opaque bitsandbytes failure), and reads the
  generation device from a real parameter (multi-GPU/CPU-offload safe).
- **`LLMJudgeDetector`** percentage disambiguation (`>=2.0`, so a stray "1.5" clamps to ~1.0 instead
  of becoming 0.015); `Detector.score` protocol typed `float | None` to match the None-exclusion path.
- **Dead detectors no longer pin the score at a fake `0.5`.** `mage`/`hc3_roberta` previously swallowed
  a load failure and returned a neutral `0.5`, which silently pinned the ensemble `max` and made the
  loop's signal meaningless on a broken ML env. Failed detectors are now **excluded** from the
  aggregate (like `roberta_openai`/`fast_detectgpt` already were), surfaced under `failed_detectors`,
  and `score` reports the **effective tier that actually produced numbers** plus a `warning` on
  downgrade — so a full-tier run with a broken stack honestly reports `lite`, not a fake `full`.
- **Fail-fast on load errors.** A detector that fails to load is disabled for the rest of the process
  instead of re-attempting the heavy import on every call (fixes the "took forever" on broken envs).

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
