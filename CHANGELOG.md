# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed
- **A rewrite could weld English words into German and French.** Every transform in the structural
  rewriter is English, and applied to Latin-script text that is not English they do not fail — they
  produce fluent-looking damage: an opener prepended to a German sentence, and `and` inserted as a
  clause joiner in German and French. The existing guard is script-based, so it separates Chinese
  from German and German is Latin. Such text is now returned unchanged with a caveat on the result.
  The test needs positive evidence of another language rather than absence of English, because the
  two do not separate on short input — an English heading scores 0.000 and Italian 0.125 — and a
  false positive would silence the rewriter on text it can read. Measured 0 false positives over 20
  deliberately hostile English samples.
- **`untell verify --threshold`, the server port, and a bad `--detector-thresholds` value all
  crashed or lied instead of explaining.** `UNTELL_PORT=abc` raised a `ValueError` while building
  the argument parser, so even `--help` — the route to the `--port` flag that would override it —
  died with it. The port range is now checked too: 0 and 70000 parse as integers and fail later
  inside uvicorn, where the message is about sockets rather than about the variable the user set.
- **A broken `.docx` or `.pdf` printed a stack trace.** Both readers converted a missing dependency
  into a clear message and neither converted the parsing libraries' own errors, which descend from
  their own base classes rather than from `ValueError`. An empty, corrupt, or password-protected
  file exited 1 with a traceback; `Package not found at '...'` was the misleading one, since the
  file is present and readable and simply is not a .docx. All now exit 2 with one line, and the
  three cases are told apart because they call for different actions.
- **`--json` broke on two error paths.** `untell scrub --json` with no input left stdout EMPTY, so a
  caller parsing it got a JSONDecodeError instead of the message saying what to fix, and a bad
  `--detector-thresholds` value printed plain text regardless of the flag — the one case where the
  caller most needs to read what was wrong with their own argument. Both now answer
  `{"error": ...}` and keep exit 2; the human-readable form is kept for runs without the flag.
- **A verdict about the first 50,000 characters was presented as a verdict about the document.**
  Scoring truncates there and said nothing. Measured on a 67,200-character input, the reported max
  is identical to the first 50,000 scored alone, to machine precision. The tell catalogue does NOT
  truncate, so the same document reported 10,774 tells against the scorer's 8,010 — two surfaces
  describing different documents. Both scoring paths now say what they dropped.
- **A conditional with its clauses swapped passed the meaning gate.** "If the sensor fails, the
  system shuts down." -> "If the system shuts down, the sensor fails." reverses the causation, and
  measured on three such pairs the full NLI path gave contradiction 0.0065-0.0277 and entailment
  0.96-0.99 — accepted on both the NLI and stdlib paths. The three predicate-argument rules were
  blind to it by construction. The check keys on the PARSE rather than word order, so "B if A" is
  still accepted as the same claim as "If A, B"; measured 0 false vetoes over 81 real rewrites.
- **Seeding did not survive a second thread.** `untell_text` seeds the global `random` module, and
  save/seed/restore is only atomic if nothing else runs in between. Measured with three threads
  asking for the seed they had just been given serially: 1/3, 0/3 and 1/3 matched, and a caller who
  had seeded their own RNG found it moved. Serialised now. The REST server never hit it, because
  every endpoint blocked the event loop — which was masking it.
- **`--style academic` opened a paper with "Basically,".** The formal profiles already decline
  contractions and hold back the plain-word swap; the opener pool was never covered by that, so the
  rate fell with the profile while the vocabulary did not change. Three spoken-register openers are
  now withheld from the three formal styles; the other six are attested in formal writing and stay.
- **An opener that summarises what came before could be the first sentence.** "In short," and "Put
  simply," announce a compression of preceding text, and "Also," adds to it; at the top of a block
  there is nothing to compress. Measured at 4 of 100 rewrites before, 0 after, with the pool
  otherwise unchanged and the dose steady at 5.00% of sentences against a human 3.13%.
- **`untell-audit` could not run as a file.** It had no `sys.path` bootstrap, and its untell imports
  are all lazy — so nothing failed at import time and its shape did not resemble the six scripts
  fixed earlier. It failed later instead, on the first check that needed the package.
- **SKILL.md cited a file the installer does not ship.** Both installers copy `untell/` and nothing
  else, so a repo-relative path into `docs/` is broken for everyone who installed the documented
  way. Now a URL, which resolves from an installed skill and a checkout alike.

- **The zero-dependency path could not import untell.** Six scripts had their run-as-file
  `sys.path` bootstrap BELOW their package imports, where it is unreachable — the import raises
  `ModuleNotFoundError` first. `python .../untell/scripts/score.py` on a machine without the
  package installed died immediately, which is exactly the path the skill installer creates and
  the README leads with. An editable install hides it, so it only ever appeared on CI's Linux and
  Windows installer jobs. `score`, `tells`, `verify`, `preserve`, `quality` and `entailment` all
  fixed and verified running from an unrelated cwd on a bare interpreter.
- **`untell verify --threshold 5` certified any text as passing.** Detector scores are
  probabilities, so a threshold above 1 cannot be reached: text this same command rates 0.826 was
  marked `[PASS]`, printed "PASSES ALL 1 CHECKERS" and exited 0. On the command whose job is
  gating, a slipped decimal point green-lights everything. `score --threshold`,
  `sentences --threshold` and `humanize --confirm` had the same gap and are now bounded by the
  same validator the REST and MCP surfaces already used.
- **`untell prove` returned 1 whether the text failed or nothing had run.** With no API keys it
  printed "cannot prove 'passes all'" and exited 1, so a gating job could not tell "rewrite more"
  from "set ORIGINALITY_API_KEY". Now exit 2, matching `untell-verify`.
- **The MCP `compare` tool raised `TypeError` on every call.** It passed no `texts` to a function
  that requires them, so the tool was dead while registered, advertised and documented. It also
  validated no arguments; both fixed, and it now names its corpus in the result.
- **MCP could not ask for `confirm` or `detector_thresholds`.** Both change the verdict and both
  were modelled on the REST body, so the same request answered differently by protocol — the
  fourth instance of that drift in this file.
- **A version number was locked as far as its second dot.** `preserve` masked `1.26.4` as
  `⟦HZ0000⟧.4`, leaving the tail rewritable while every sentinel check reported success. Dotted
  identifiers (semantic versions, IPv4, section numbers) and hex identifiers (git shas, digests)
  now lock whole; the hex rule was chosen after measuring 0 false locks against 240 real texts.
- **A magnitude word was part of the number when spelled and thrown away when not.**
  `"Losses hit five million." -> "five billion"` was caught and `"5 million" -> "5 billion"` was
  not, because the digit path dropped the word; `billion` and `trillion` were unknown entirely.
  Both paths now share one scale table, so `5 million` and `5,000,000` compare equal.
- **Four attribution verbs were hedges only in the past tense.** The evidential class held
  `believed`, `thought`, `considered` and `estimated` but not their present forms, so
  `"We believe the mechanism is oxidative." -> "It is established ..."` cleared every gate.
  `suspect` and `purport` were missing in the other direction and caused false vetoes.
- **Caveats reached the result and stopped short of the reader.** `humanness` answered with a bare
  number on the weakest detector path; the web demo showed a percentage and a "Human" badge with
  no caveat at all; the plain-text renderer (what `pip install untell` prints without the `rich`
  extra) dropped both the score warning and the tell counts; and `untell tells` printed its
  warning only when no tell had fired. All four now carry what they were handed.
- **A run depended on what the process had rewritten before it.** `structural.py` draws from the
  global `random` module in 27 places and nothing seeded it, so the stream carried between calls.
  Measured on one document in one process, identical arguments, differing only in position: scored
  first it returned 0.4003 and 778 characters; scored after two other documents, 0.4325 and 770.
  Every batch figure was therefore order-dependent, and no reported number could be reproduced
  without replaying the sequence before it. `untell_text` now seeds from a digest of its input and
  restores the caller's RNG state afterwards. **This changes output text for a given input** —
  same quality, different draw. Seeding is per run, not per rewrite, so best-of-N still gets
  distinct candidates. `random.seed()` around the call no longer reaches the loop; pass the new
  `seed=` argument to select a stream.
- **`untell-verify` exited 0 when no checker ran.** On a machine with no API keys,
  `--tier commercial` printed "No checkers ran." and returned 0 — which means *pass* to CI, so a
  gating job was told the text had passed every major AI checker when none was consulted. Now
  exit 2, kept distinct from 1 (checkers ran and failed) because nothing running is a
  configuration problem, not a verdict about the text.
- **A missing API key was reported as a bad rewriter name.** `rewriter="anthropic"` with the SDK
  present and `ANTHROPIC_API_KEY` unset answered "check the name" — advice to fix something that
  was not broken. The four cases (no key, no SDK, neither, unknown name) now give four messages,
  each naming the specific thing missing.
- **`untell-server` crashed with a bare `ModuleNotFoundError` on a base install.** The console
  script imports the module before `main` can print anything, so nothing said which extra supplies
  FastAPI. Now a named `ImportError` giving `pip install 'untell[server]'` — deliberately not a
  `SystemExit`, so a library caller importing the module gets the exception their `try` expects.
- **`humanness` answered confidently at lengths where it cannot separate the classes.** At 12 words
  it returned 99.7 and called it "human" while `score_text` on the same text warned the verdict was
  unreliable. Measured on 30 HC3 pairs truncated to 40 words: AUROC 0.694 against 0.978 at full
  length, and 0 of 30 genuine human texts scored in a human band. The number is still returned; the
  caveat now reaches the caller, and the bar is `score_text`'s own so the two cannot drift apart.
- **The short-text warning understated its own measurement.** The bands quoted 98/62/40/28% of
  human text flagging at 5/10/20/40 words. Re-measured by the same method — truncation to the first
  N words — they are 100/85/85/100%. Now ranges spanning both truncated and naturally-short text.
- **The sentence-start capital rewrote identifiers and paths.** `_flatten_cliches` upcased the first
  letter after any terminator, so "Call untell.score. untell.tells also works." became
  "... Untell.tells ...", and the same for `src/main.py` and `--tier`. Scoped by shape, so ordinary
  prose still gets its capital.
- **`/tells` returned a `matches` key its published schema never declared**, so a client generated
  from the spec dropped the field showing which phrases were counted. A conformance test now checks
  both directions across five endpoints.
- **`SKILL.md` described behaviour the code had changed.** Voice matching scores four features, not
  three; BERTScore and its 0.88 bar are gone; and `flagged` no longer means `max < threshold` —
  they diverge in a band reachable on the default clean install, where the documented procedure had
  no stated action.

### Changed
- **The server no longer blocks itself.** Every endpoint was `async def` calling a blocking worker
  directly, so a rewrite ran on the event loop: measured against an 11.20s `/humanize` with
  `/health` polled every 20ms, 0 health responses landed during it. Five workers are now offloaded
  (324 responses during the same rewrite). `/health` itself resolved the detector list on first
  call — 9.34s cold against 0.0026s warm — which is exactly the call an orchestrator makes before
  restarting a container that never served a request; it is now resolved during startup, before
  traffic is accepted. This does not make concurrent rewrites parallel: they still serialise, off
  the event loop instead of on it.
- **`mt_pivot` drew three identical candidates and paid for three.** Its decode is beam search with
  no sampling, so `best_of` bought nothing. Declaring it deterministic collapsed 6 rewrite calls to
  2 on one document, with byte-identical output and an identical score.

- **Released the accumulated notes as 0.3.0.** 0.2.0 and 0.3.0 both shipped without a
  changelog heading: the entries stayed under `[Unreleased]` while `pyproject`,
  `untell.__version__`, `plugin.json`, `marketplace.json` and `CITATION.cff` all moved to
  0.3.0, so anyone who installed 0.3.0 and opened this file was told the latest release was
  0.1.0. They are recorded under 0.3.0 rather than split between the two, because the
  boundary is not recoverable from the file and inventing one would be worse than saying so.
  `tests/test_changelog.py` now ties the newest heading to the shipped version — the existing
  tests there checked the file's shape (standard sections, no duplicate headings, no orphaned
  entries) and all of them passed throughout.

## [0.3.0]

### Added
- **The loop reports the AI tells it removed.** `tells_before` and `tells_after` on the result,
  an "AI tells" row in the table, and both in the OpenAPI schema. On a corpus where the detectors
  saturate this is the only before/after pair that moves: measured on 4 HC3 documents at full
  tier, `max` gained +0.0000 on 4 of 4 while tells fell 4->0, 1->0 and 1->0.
- **`seed` on every surface, and reported back.** `--seed` on the CLI, `seed` on the MCP tool and
  the REST body, and the effective seed on the result — without it the derived value is a digest
  of the input and a caller holding an output has no way to ask for it again.

- **Described OpenAPI responses for all seven endpoints.** Every handler returns a bare `dict`, so
  FastAPI had generated `{"type": "object", "additionalProperties": true}` for each — the docs page
  the README advertises told a client nothing about what comes back. Now documented with field
  names, types, which are always present, and what the non-obvious ones mean: that `max` is the
  headline number, that `tier` can differ from `tier_requested` when detectors fail, that
  `verdict_threshold` rather than `threshold` decides `flagged`, that `rewriter_available: false`
  means nothing was rewritten. Attached with `responses=` rather than `response_model=`, because a
  response model *filters* — it would silently drop `failed_detectors`, `detector_errors` and
  `warning`, which appear only when something has gone wrong and are exactly what a caller then
  needs. Tests assert the descriptions stay true, since nothing else enforces it.
- **`detector_errors`** in the `/score` response — the message from each detector that raised,
  beside the existing `failed_detectors` list. Present only when something failed.
- **Language registry** (`untell.languages`) — `register(code, scorer, script=...)` and
  `catalogue_for(text)`, shipping with one entry: English, pointing at the existing catalogue.
  Text in a script nobody has written for returns **None** rather than falling back to English,
  because running an English catalogue over Korean finds no English tells and reports a clean score
  for text nothing examined. Additive by construction — a test asserts `scripts/tells.py` contains
  no reference to the registry, so adding a language means writing a file and touching nothing.
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
  mechanism that lowers the AI-tells rate while holding the meaning gate (to **zero** on the built-in
  demo corpus, 14.46 → 0.0; on real HC3 text, 4.22 → 3.81 — the zero belongs to those three
  paragraphs, not to the tool), and that the free tools'
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
- **A score on text too short to judge now says so.** `/score`, `untell score` and the MCP `score`
  tool answered `"a"` with P(AI) 0.9987 and `flagged: true`. Below 40 words the ensemble does not
  discriminate — measured on 40 HC3 pairs, 98% of HUMAN text flags at 5 words, 28% at 40 — and the
  result now carries that rate as a caveat. The number itself is unchanged.
- **`tells_per_100w` on a handful of words is caveated.** `Moreover.` is one word and one tell and
  reports 100.0 per 100 words, against corpus means of 0.642 human and 7.320 AI. Below 14 words —
  the point where a single tell stops exceeding the AI mean — the result says to read the count
  instead.
- **A non-breaking space no longer changes the verdict.** Replacing every space with U+00A0, which
  is what a paste out of Word or a web page contains, took human text from 5/10 to 9/10 flagged
  (mean P(AI) 0.4322 → 0.7801) and hid 2 of 5 AI tells, because tokenisers and literal-space
  patterns do not treat it as a space. Unicode space separators are now folded before scoring and
  before the tell catalogue runs, by one shared rule in `untell/text_split.py`.
- **Sentence fronting now actually respects its budget.** The rate above was the intent; the counter
  that enforces it held a literal `0x08` byte where `\b` was meant, inside an `r"..."` string where a
  word boundary and a backspace look identical. No text contains a backspace, so the count of
  already-fronted sentences was permanently zero and the budget permanently full — text already at
  or above the human rate kept receiving more. Measured on a block already fronting all three of its
  eligible sentences: 0.67 sentences newly fronted per run, now 0.00.
- **`humanness()` on non-Latin script says why it cannot answer.** It returned 50 (undetermined),
  which was right, with the reason "text is shorter than 5 words" — true of a word regex that counts
  `[A-Za-z']+` and absurd for a 40-character Chinese paragraph. It now names the real limit, that the
  catalogue is English-only.
- **`/score` returned a string inside the map of detector scores.** A failed detector leaves its
  message beside the score internally (`{"hc3_roberta": null, "hc3_roberta__error": "..."}`) and
  every in-repo consumer filters keys ending in `__error`. REST clients do not have that
  convention, so the first thing anyone writes — `max(body["detectors"].values())` — raised
  `TypeError: '>' not supported between instances of 'str' and 'float'`. Fixed at the boundary
  only; the library contract is unchanged and a test asserts it, since three in-repo consumers
  depend on it.
- **The CLI accepted argument values the REST API rejects with 422** — `--threshold 50` (nothing
  can ever be flagged), `--threshold -1` (everything always is), `--best-of 0`, `--max-iters -5`
  (the loop does no work and reports a pass), and `--best-of 10000`, which ran until it was killed
  genuinely generating candidates. The CLI now reads its bounds off the API's own annotated types
  rather than repeating them. `test_surface_parity.py` existed to prevent exactly this and compared
  defaults and vocabularies but not *ranges*.
- **`untell_text` output key** — the rewrite is under `final`; there is no `text` key. Pinned,
  because `result.get("text") or original` returns a plausible string rather than raising, so the
  mistake survives every casual check.
- **Both model-backed meaning gates stopped reading part-way through the document.** The entailment
  gate tokenises (original, rewrite) as one sequence truncated at 256 tokens, and the similarity
  gate's embedding backends truncate too, so each was scoring only the front of a long input while
  reporting a verdict about all of it. Measured with the *same* edit moved to a different position:
  a negation 143 words in scored **0.0179** — the contradiction score for two identical strings —
  and replacing a whole sentence 280 words in scored a similarity of **1.0000**. Neither is a
  mis-set threshold; the changed text was never fed to the model, so no bar could have caught it,
  and a rewriter could invert any claim after roughly the first 130 words unnoticed. Both gates now
  score `difflib`-aligned chunks and take the worst (`max` contradiction, `min` similarity), which
  costs 0.17s → 0.57s per pair on a 298-word input and rejects 0 of 30 real rewrites. `roles`,
  `hedges` and `numerals` were probed the same way and are position-independent to 552 words.
- **A substitution could strengthen a claim, and no gate could ever catch it.**
  `demonstrates → proves` scores 0.993 entailment with 0.0009 contradiction — it passes cleanly and
  always will, because a strictly stronger claim entails the weaker one by construction.
  Entailment is the wrong instrument for this class, so the offenders are removed at source:
  `prove`/`proves`/`proving`, `arguably → possibly`, `unprecedented → record`,
  `various → all sorts of`. Also `demonstrate → display`, which was simply ungrammatical
  ("the experiments display **that** it works"), and `arguably → one could say`, which put a clause
  in an adverb slot.
- **The pronoun "I" was being lowercased** — `"...slow, and i believe the cache was cold."` It sat
  in the 220-word safe-to-lowercase list among the other pronouns, and it is the one word in
  English that never is.
- **A quotation was merged into the narration**, producing
  `'"...," she said, and "And, the cost is prohibitive.".'` — the connector landing before an
  opening quote, and a second full stop appended because the quoted sentence's own stop is inside
  the quotation where `rstrip` cannot reach it.
- **`untell-mcp --help` printed nothing and started a server.** `main()` never parsed `argv`, so
  the flag fell through to serving JSON-RPC on stdin. `untell-audit` passed this script because it
  checks that entry points *resolve*, which is not the same as running.
- **Three tests were failing in CI's full-tier job**, asserting numbers only true of the
  pure-Python lite scorer while reading that path out of the ambient environment.
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
