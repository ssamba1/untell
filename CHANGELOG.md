# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- **`untell batch` -- directory-tree humanization with JSON manifest.** `untell batch DIR` walks
  a directory tree, humanizes every `.txt`/`.md` file with the same loop as `untell humanize`,
  mirrors the structure into `DIR_humanized/`, and writes a `manifest.json` recording input path,
  status, pre/post detector scores, and whether the text was rewritten. Binary files are skipped
  cleanly; per-file failures never abort the run; the exit code is 1 if any file failed. Flags:
  `--out`, `--tier`, `--threshold`, `--rewriter`, `--max-iters`, `--best-of`, `--dry-run`,
  `--limit`, `--json`. (`af37909`)
- **`untell watch DIR` -- humanize files on change.** Polls a directory and humanizes every
  `.txt`/`.md` file the moment it appears or is edited, reusing the batch pipeline with one shared
  rewriter. Editor-save bursts are coalesced by a debounce window (`--debounce`). Flags: `--out`,
  `--tier`, `--threshold`, `--rewriter`, `--poll-interval`, `--debounce`, `--dry-run`. (`0e5cbfd`)
- **`untell explain` -- reports which rule locks each span and why.** The preserve-lock mask was
  opaque: a span came back verbatim with no way to ask why. `untell explain TEXT` (or `--file`,
  stdin, `--json`) now lists every locked span, the rule(s) that matched, and the documented
  rationale from a machine-checked registry. The registry is tested: every rule has a rationale,
  every rationale names a rule. (`04e3bb2`)
- **`untell humanize --diff` -- shows only what changed.** Renders a unified-diff-style
  before/after view (red deletions, green additions, dim hunk headers) through the same
  rich-output conventions as the standard report, with a plain-text fallback. `--diff --json`
  emits a machine-readable payload (format `untell-diff`, hunks with 0-based spans) that also
  carries the locked spans and the count of locks that survived byte-for-byte. (`d1e3e11`)
- **`untell humanize --jsonl` -- streaming output mode for long documents.** Splits input on
  blank lines and emits one JSON object per block as it completes, flushed immediately, so a
  1 MB document reports progress instead of going silent for minutes. A final summary object
  closes the stream. `--jsonl` and `--json` are mutually exclusive; the combination exits 2
  with a clean error. (`520edfc`)
- **`untell humanize --manifest PATH` -- reproducibility manifest.** Writes a JSON record for
  each run: input/output sha256, seed, rewriter, tier, threshold, pre/post detector scores,
  untell version, and an honest determinism class (`reproducible` for local rewriters;
  `non-deterministic by design` for hosted and browser paths). For a reproducible run the
  manifest is itself byte-identical across runs and across processes. (`516253d`)
- **`untell humanize --timings` -- per-phase timing output.** Emits a JSON block recording
  score/rewrite/rescore/loop-total times so the rewrite-dominated cost shape is visible per
  run. (`331ee9a`)
- **`UNTELL_SELECT` -- selection objective for best-of-N.** Controls what the candidate-
  selection step ranks on: `max` (the tier maximum, shipped default), `mean` (ensemble mean,
  so lowering four detectors beats gaming one), or `dropout` (maximum over a seeded-random
  subset of the tier, resampled each iteration). (`ce3b6f8`)
- **Browser checker uses an automatic site selector.** `_all_checkers()` builds the candidate
  list dynamically (built-in sites first, then user-added sites), and `'auto'` picks the first
  available. The zerogpt submit selector was also fixed: the previous selector matched a
  navigation link before the actual "Detect Text" button, so no detection ever fired and every
  retry spent its full wait budget before raising `SelectorMiss`. (`59504dc`, `a1196f1`)
- **The web demo now shows AI-tell counts.** `/humanize` returns `tells_before` and
  `tells_after`; the CLI and rich-output table already showed them; the demo page
  (`docs/demo.html`) never referenced either key. On input where the detectors saturate, the
  score can barely move while the tells fall to zero, so the two score bars alone read as
  "nothing happened." Both counts now appear. (`c5141ce`)
- **`untell humanize --html PATH` -- save a styled HTML report.** Calls the HTML report
  module and writes the output to `PATH`; echoes the path to stderr so stdout stays clean
  for piping. (`a5a1dbd`)

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

- **`untell-server` silently did nothing.** An extraction refactor placed `_host_from_env()`
  inside `main()`, causing `main()` to return after building the argument parser. The console
  script, the Dockerfile entrypoint, and `python -m untell.api_server` all exited 0 printing
  nothing; `--help` produced no output; the CI docker job's "server starts and answers" step
  had no server to answer. (`b1ed8d2`)
- **The Docker image could never build.** `.dockerignore` dropped `eval/` and `training/`
  (declared packages in `pyproject.toml`), producing a `package directory eval does not
  exist` error from the builder. It also excluded every `*.md` file, giving the wheel an
  empty long description and stripping `untell/SKILL.md` and the references directory from
  the installed package. (`75be76a`)
- **The API server bound to `0.0.0.0` by default instead of `127.0.0.1`.** This contradicted
  the README, the module's own comments, and the CORS tests. The server is now localhost-only
  by default; `UNTELL_HOST` or `--host` override it. (`694f786`)
- **`/humanize` silently billed a hosted rewriter when a free one was unavailable.**
  Requesting `t5_paraphrase` or `mt_pivot` without optional dependencies returned HTTP 200
  with no `rewriter_warning` and selected a hosted (paid) backend. The endpoint now returns
  422, matching the MCP tools which already refused. (`694f786`)
- **`/health` re-resolved the full detector list on every call.** The startup cost (measured
  at 9.34s cold) ran on every liveness probe -- the exact call an orchestrator makes before
  deciding to restart a container. The result is now resolved during lifespan startup and
  TTL-cached thereafter (measured 0.0026s warm). (`e567607`)
- **The version number in `api_server` was `0.2.0` while the package shipped `0.3.0`.**
  (`4a00730`)
- **CJK and RTL text was treated as one sentence.** `split_sentences` only knew `[.!?]`; a
  CJK document was one sentence, giving burstiness CV 0.0 and causing per-sentence targeting
  to name the whole document as one unit. Added CJK/Arabic terminators (no whitespace
  required), plus a zero-width bypass so carriers between a full stop and the next word
  cannot hide a boundary. Windowed scoring for scriptio-continua text now uses character
  widths rather than space-split words, so adapters no longer truncate to the opening
  ~380 words. (`0315a14`)
- **Emoji tag sequences (England/Scotland/Wales flags) were destroyed by `scrub_hidden`.**
  Tag characters U+E0000-U+E007F form valid emoji tag sequences but are also invisible. The
  scrubber treated them as hidden characters and deleted the flag glyphs. (`b5b0856`)
- **U+2028 (line separator) and U+2029 (paragraph separator) were neither scrubbed nor
  scored.** Measured: inserting U+2028 after every `e` in a two-sentence paragraph moved the
  lite/stdlib score from 0.6735 to 0.5545, a 0.119 drop in the direction that reports AI
  text as human, with no warning and no removal. Both are now caught. (`e9643cb`)
- **`count_hidden` re-derived what `scrub_hidden` does and had drifted for the sixth time.**
  The two functions now share one implementation. (`8402356`)
- **Binary stdin caused `UnicodeDecodeError` tracebacks from the CLI.** Piping binary content
  into `untell score`, `untell scrub`, and `untell humanness` printed a raw traceback.
  NUL-bearing stdin was also scored as prose rather than refused. All now exit 2 with one
  line. (`50975c0`, `0680990`, `7a0c925`)
- **Lone-surrogate input crashed `untell_text`, the NER preserver, and the REST 422
  renderer.** A `UnicodeEncodeError` from the library, a `ValueError` from spaCy, and a
  `TypeError` from the error-payload path each produced tracebacks. Lone surrogates are now
  refused or sanitised at every surface. (`6716429`, `bb87f87`, `5b38d76`)
- **Preserve did not lock dates, currencies, SI units, coordinates, or formulas.**
  Dates like `10 November 2023`, prices like `€1,200`, units like `9.81 m/s²`, coordinates,
  and equations were all rewritable. The lock catalogue now covers these forms. (`9eda40e`)
- **Preserve did not lock compound units, time ranges, exponents, or formatted phone
  numbers.** `120 kWh/month`, `09:00-17:00`, exponents, and `+1 (800) 555-1234` were all
  rewritable. (`1162504`)
- **Preserve did not lock feet-inches heights, measurement dimensions, or semicolon numeric
  citations.** `5'11"`, `4×6 cm`, and `(pp. 12; 14)` were all rewritable. (`b91932f`)
- **Preserve did not lock short hex strings, two-component dotted identifiers, or additional
  phone-number formats.** (`a9a77d5`)
- **HTML `<code>` tags were the one notation the preserver left rewritable.** (`8c70a16`)
- **Curly single quotes were rewritable.** All other quotation styles were already locked.
  (`f5ca2da`)
- **A citation containing a semicolon was not recognised as a citation.** `(Smith, 2020;
  Jones, 2021)` was not locked. (`0900a53`)
- **A price earlier in a sentence could expose an equation.** The preserver's masking was
  order-sensitive: a price before a formula caused the formula's token to be unmasked by the
  price's unmask step. (`3660968`)
- **A preserve setting locked its own name but left its value rewritable.** The sentinel
  pattern matched the key only. (`544be36`)
- **`restore()` edited documents that nothing had rewritten.** Calling `restore()` on text
  not passed through `lock()` applied inverse substitutions to accidental pattern matches.
  (`7502220`)
- **A masked abbreviation was treated as a sentence boundary by everything downstream.**
  A `preserve`-masked token containing a period triggered the sentence-boundary detector,
  splitting the sentence in the middle of a locked span. (`bccf8aa`)
- **NER false-locked common English words as named entities.** spaCy tagged capitalised
  `Email`, `May`, `Will`, `Mark`, `Bill`, and `Rose` as PERSON entities; `lock()` then froze
  those words in every context, preventing `Email me the file` from being rewritten.
  Single-token PERSON entities whose text is a common word are now filtered. (`00722ae`)
- **Bidi controls between a terminator and the next word hid the sentence boundary.** A
  zero-width character between `.` and a capital letter made `split_sentences` see one
  sentence where there were two. Abbreviation and quoted-period rules now see through
  trailing zero-width characters. (`4ef658a`)
- **Footnote/endnote markers after a terminator were not recognised.** Superscripts and
  bracketed numerals were counted as abbreviations. Latin abbreviations `ca.`, `viz.`,
  `nb.`, `op.`, and `cit.` were also missing. (`c0cc7f3`)
- **A quoted period with a lowercase continuation was treated as a sentence boundary.**
  `"It ended."` followed by `he said` split at the close-quote. (`62b53df`)
- **The dotted-initialism filter capped at four letters, missing five- and six-letter
  initialisms.** `U.S.A.`, `N.A.T.O.`, `I.U.P.A.C.` were split at internal periods. Cap
  raised to six. (`0a82920`)
- **Sentence-final abbreviations split on a capital continuation.** `Dr.` followed by a
  name was treated as a sentence end. (`180fc97`)
- **Disjoint aligned pairs truncated the source document.** When `aligned_chunks` produced
  pairs covering a subset of the source, the outer text was trimmed to match. (`4696358`)
- **Negated-contrast flattening deleted text across sentence boundaries.** `"It is not X.
  It is Y."` had its second sentence consumed by the transform for the first. (`31a2bcd`)
- **Uncontracted negated-contrast phrases were not flattened.** `"It is not X, it is Y"` was
  not matched; only the contracted form `"It's not"` was handled. (`a262839`)
- **The adoption loop counted each candidate's tells twice.** The current-best tell count
  was computed over already-adopted text rather than the candidate's text, inflating the
  denominator for every adoption decision. (`c9a692c`)
- **A conjunction-trap comma incorrectly blocked a clean structural split.** A comma before
  a coordinating conjunction inside a clause was treated as a compound-sentence marker.
  (`c71f42b`)
- **The comma splitters split inside parentheses and brackets.** A comma in `(A, B)` triggered
  a sentence split. (`8a82cf2`)
- **A bracket was treated as a sentence boundary.** An opening parenthesis immediately after
  a word triggered the boundary detector. (`a5ba654`)
- **Display-math `$$...$$` blocks were transformed.** Operators and terms inside display-math
  environments were treated as prose and rewritten. The delimiters are now locked. (`a7a4a19`)
- **The layout `restore_layout_lines` guard was inverted.** The condition caused the
  layout-protection pass to apply to every document except aligned ones, silently disabling
  layout protection for the class of documents it was written to protect. (`d53b5fd`,
  `cca631b`)
- **The quality gate's cosine condition was inverted by a fleet edit.** `if cos is not None`
  was changed to `if cos is None`, disabling the gate for documents that computed a cosine
  similarity and enabling it for documents that did not. (`3fb3e75`)
- **`RELAXED_SIM_BAR` was silently changed from 0.30 to 0.20** by a sweeping audit commit.
  (`29cd12b`)
- **A mistyped subcommand was silently humanized instead of refused.** `untell humnaize` ran
  the rewriter on the misspelled string as its input text. (`d76344c`)
- **CLI panels did not escape Rich markup in user-supplied text.** Brackets in input were
  interpreted as Rich markup tags. Flag-like arguments beginning with `-` were also accepted
  silently on paths that should reject them, and `--json` was not accepted consistently
  across all subcommands. (`2e02bb3`)
- **The optional-dependency error message for `--rewriter local` was wrong.** The message
  named the package's development extra instead of the install path from the README. (`e5a7d33`)
- **The plain terminal path dropped the caveat and the tell counts.** Users who installed
  `untell` without the `[rich]` extra saw neither the caveat nor the AI-tell counts. (`ee3ca09`)
- **Hidden characters introduced by a rewriter were not scrubbed from the output.** The
  input-side scrub (before `lock()`) already existed. A hosted LLM, T5 sample, or
  local-policy step could re-emit a hidden character; `restore()` was not followed by a
  scrub. Measured with an injecting rewriter: a zero-width space appeared in the final text
  with `scrub=True` and no warning. (`e3c38f8`)
- **`--seed -1` and `--seed 1` produced the same random stream.** Both were converted to
  their absolute value before seeding. (`f7da552`)
- **`untell prove --file MISSING` printed a `FileNotFoundError` traceback.** (`32d6ee9`)
- **`untell-compare` accepted `--n 0` and `--threshold 2.5` without complaint.** Zero
  candidates cannot be compared, and a threshold above 1 can never be met by a probability
  score. Both now exit 2 with a clear message. (`6cadc0e`, `5735dc3`)
- **`untell-ceiling` and `untell-compare` reported a bad `--file` argument as a traceback,
  not a message.** (`5fb4c5c`)
- **`score_text` and `untell_text` raised a raw `TypeError` on bytes input.** (`912929b`)
- **The humanize-loop polish step warned about the same failure type once per failure, not
  once per type.** On a document with repeated polish failures of the same class, the
  terminal showed the same warning once per sentence rather than once for the class. (`01e43f8`)
- **A `None` max score crashed the humanize report.** When no detector ran, the result's
  `max` key was `None` and the report formatter crashed while rendering the score bar.
  (`57d008b`)
- **The `humanness` score bar crashed or flooded the terminal on non-finite input.** Infinity
  or NaN from a detector path caused the bar renderer to either raise or print an unbounded
  number of characters. (`e2c18b2`)
- **The MCP ceiling tool accepted a non-existent tier and a threshold nothing can reach.**
  `tier="bogus"` ran the lite path silently; `threshold=50` returned passes_all=True with a
  warning. Both now match the REST `/verify` endpoint and the CLI. (`3373638`)
- **MCP `_bad_args` crashed on non-numeric input instead of refusing.** `top="all"` or
  `threshold="high"` raised inside the validation function. (`606f0e0`)
- **MCP `_bad_args` treated `None` as an invalid `top`/`seed` value.** `None` is the
  documented default for both; a fleet edit regressed them to "invalid argument". (`a506353`)
- **MCP `_bad_args` crashed instead of refusing infinite counts.** (`d57026c`)
- **MCP tools accepted oversized text or an unknown ceiling rewriter without refusing.**
  (`2f68c78`)
- **An unknown rewriter name on the MCP surface produced a misleading error.** The message
  told the caller to check the rewriter name when the real issue was a missing backend.
  (`60c2a11`)
- **The torch-path and stdlib-path scores collided in the per-text score cache.** The
  content-addressed cache keyed on text, detector names, tier, and threshold -- but not on
  `UNTELL_LITE_NO_TORCH`, which flips `perplexity_burstiness` between GPT-2 and a stdlib
  heuristic. Measured: 56 full-suite failures, all verdict-threshold assertions after the
  first env toggle. (`eb07c50`)
- **`clamp01` converted a `NaN` detector score into a neutral `0.5`.** A silently-failed
  detector returned `NaN`; `clamp01` mapped it to the midpoint rather than propagating the
  failure. A failed detector now appears in `failed_detectors`. (`2ef7ee3`)
- **The `mage` detector's fallback handling was fragile.** A missing snapshot file, a
  mismatched hash, or network unavailability each raised instead of falling back gracefully.
  (`7279283`)
- **T5 sampling did not seed torch from the loop's seed.** The T5-based rewriter paths drew
  from an unseeded torch RNG, so `--seed N` did not make T5 outputs reproducible. (`401501b`)
- **`UNTELL_LITE_NO_TORCH=1` did not gate the NLI and roles meaning gates.** The lite-env
  flag disabled `perplexity_burstiness` but not the two meaning-gate paths that also load
  torch models. (`1a16ee5`)
- **`UNTELL_POLICY_MAXTOK` set to a non-integer raised inside the argument parser.** Even
  `--help` was blocked. Invalid values now warn and fall back to the default. (`58c52bf`)
- **An unclosed quote put the quote character inside the API key.** (`31fa6fa`)
- **Non-English text received AI verdicts with no language caveat on five surfaces.**
  A German paragraph passed to `score_text`, `score_tells`, `score_sentences`, `humanize`,
  and `humanness` returned AI results without noting that the detectors and tell catalogue
  are English-only. `humanness` returned 100.0 "Human" for German text because nothing in
  its scoring path examined it. `--top` on `sentences` was also not respected on two
  surfaces, and a negative `--top` value flagged `n-1` instead of the most-flagged sentences.
  All language-caveat branches now share one function with language-first priority.
  (`23253c1`, `dd5c45b`, `4bc1db0`, `b3be984`, `fc391db`, `9d338af`, `51799d6`)
- **The numerals fact gate admitted changed quantities and vetoed unchanged ones.** The
  comparison read the wrong direction. (`9012649`)
- **Spelled multi-scale numbers compared as separate quantities.** `"five million"` and
  `"5 million"` were compared as `5 != 5,000,000`; `billion` and `trillion` were not
  recognised in the digit path. Both paths now share one scale table. (`524e6a7`)
- **`aligned_chunks` was quadratic in document length.** The difflib-based alignment produced
  an O(n*m) cost that timed out on long documents. (`9134c09`)
- **The distill filter used the raw cosine bar instead of the loop's meaning gate.** Documents
  the meaning gate would accept were rejected by the stricter raw cosine, producing a
  distillation set different from what the loop itself would produce. (`47cdbc2`)
- **`untell distill` accepted degenerate numeric arguments at parse time.** `--n 0` or an
  extreme `--length` started running rather than being caught early. (`e1391d4`)
- **The composite rewriter duplicated one draw at each clamping edge of the intensity
  sweep.** The boundary values were sampled twice. (`f2cc79e`)
- **The detector-audit summary named wrong probe counts and reported miscalibrated
  verdicts.** The summary showed derived-probe counts rather than raw-probe counts, and the
  verdict classification was applied to the wrong column. (`0e1729c`)

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

- **Supervised detector scoring is 1.4-9.3x faster on multi-window documents.** The four
  window-based adapters (`roberta_openai`, `hc3_roberta`, `fast_detectgpt`, `mage`) previously
  scored each window with a separate model call; a 15-window document cost 15 forwards.
  `base.batched_windowed_max` and per-detector `_score_batch` now score all windows in a
  small number of padded forwards; scores are bit-identical to the sequential path. Measured:
  `mage` 121.8s -> 13.1s (hc3-human), `roberta_openai` 53.4s -> 6.5s (hc3-human). (`bdc2c8b`)
- **Detector scores are cached across loop iterations.** On iterations where the rewriter
  produced no change, the per-text cache is hit and detectors are not called again. (`3fccf19`)
- **`count_hidden` was O(n^2).** The character-walk replacement now runs in O(n). (`9aeccd8`)
- **CLI startup no longer imports the FastAPI stack for command-line bounds.** `run.py`
  imported `api_server` to read a port-range constant, pulling FastAPI, uvicorn, and their
  dependency trees into every CLI invocation. The constant was moved. (`be9b15d`)
- **spaCy NER results are now cached per document.** Repeated per-sentence NER calls were
  replaced by one call per document, and degenerate-input guards and a quadratic code-pattern
  anchor were also fixed. (`9e02182`)
- **CI: ruff lint gate job and fast-suite deselection in the lite tier job.** The ruff gate
  runs with zero tolerance on shipped code (probe files are exempted by documented policy);
  the lite job deselects `pytest-slow` so CI answers in minutes while the full job runs
  everything. (`518758f`)

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
