# Contributing to untell

Thanks for helping build the most honest, most complete open-source AI humanizer. Contributions of every
size are welcome — a new detector adapter, a free-checker selector, a bug fix, or a docs typo.

## Ground rules (the short version)

- **This is a research / defensive tool.** It exists to study the detector arms race and to defend writers
  against false positives (non-native English writers are falsely flagged at ~61% in some studies). Please
  keep contributions aligned with that framing. We don't accept changes whose only purpose is to help
  misrepresent authorship where that's prohibited.
- **Honesty over hype.** No fake "99% human" claims, no unverifiable benchmark numbers. If you add a claim,
  add the way to reproduce it.
- **Be excellent to each other** — see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Dev setup

```bash
git clone https://github.com/ssamba1/untell
cd untell
pip install -e ".[dev]"        # ruff + pytest + requests
# optional, for real detector signal:
pip install -e ".[full,eval]"

# Install the pre-commit gate. Cloning does not set this, so the hook does nothing until you do:
git config core.hooksPath .githooks
```

### The pre-commit gate

`.githooks/pre-commit` refuses a commit that CI would reject. It runs `ruff` on any Python change,
the documentation guards on any Markdown change, and `untell-audit` only when a live document
changed — the audit takes about a minute, and a gate slow enough to skip is a gate nobody runs.

It exists because of a specific mistake rather than a general principle: a commit was pushed while
`untell-audit` was failing, because the audit and the commit ran in one shell sequence that did not
gate on the audit's exit code. CI caught it — after the push.

`git commit --no-verify` bypasses it, which is the right thing for a work-in-progress commit you do
not intend to push.

### The mutation sweep

```bash
python scripts/mutation_sweep.py          # break the code on purpose, check a test notices
python scripts/mutation_sweep.py --list   # what it breaks, without running it
```

Aimed at the statistical machinery, where a wrong answer is invisible: a detector that scores
slightly wrong shows up, an interval slightly too narrow turns an honest negative into a finding.

Its first run found three survivors in code written the same day. The robustness test for
`outlier_scores` asserted only that an odd document scored above 1.0 — a bar a non-robust
implementation clears easily — so both *median → mean* and *MAD → standard deviation* survived it,
and the test was really only checking that the function returned a number. A third mutant moved the
margin cut by one document and survived, because every assertion in that file was about rates and
signs and none about how many documents landed on each side.

**A survivor needs a killing test, not an exemption.** It refuses to run on a dirty working tree,
because it edits source files and restores them from memory.

```bash
python scripts/mutation_sweep.py --vacuity   # break each module entirely; its test file must fail
```

The coarse companion. A mutant asks whether a test notices *one* broken line; this asks whether a
test file notices its module being broken *entirely*. It cannot catch a weak assertion — one alert
test carries the file — but it catches the failure that recurred four rounds running: a test passing
for a reason unrelated to what it tests, because it patched the wrong constant or scored a fixture
the code under test never saw.

## Before you open a PR

```bash
ruff check .       # lint (must be clean)
ruff format .      # auto-format
pytest -q          # tests (must be green; lite tier needs zero ML)
```

CI runs the same checks on Python 3.9 / 3.11 / 3.12 plus a full-tier job that loads the real torch
detectors. A PR that's green locally should be green in CI.

### A green run is not necessarily a complete one — check what actually ran

`pytest -q` reports modules it cannot *import* as errors rather than failures, and they scroll past
above the summary line. On a minimal install a large part of the suite is silently absent, and the
run still looks broadly fine. MEASURED in a restricted environment, each optional dependency and the
coverage it unlocks:

| missing | what it costs you |
|---|---|
| `rich` | 6 tests in `test_rich_output.py` fail with `NameError` on `_Table` / `_Text` — inside the module you are probably editing if you touch CLI output |
| `spacy` **and** `en_core_web_sm` | **~413 named-entity tests skip.** The model is a separate download and `preserve.py` warns about it at runtime — that warning is easy to lose in scrollback |
| `fastapi`, `httpx` | the API-server modules do not collect at all |
| `torch` | 4 further modules do not collect |

So before trusting a local run:

```bash
pytest -q --collect-only 2>&1 | tail -3   # the error count here is coverage you are NOT running
python -m spacy download en_core_web_sm   # the one that costs the most and is easiest to miss
```

This is written from a real mistake rather than caution: a session's worth of changes was validated
against targeted subsets while `rich` was absent, so tests asserting on that module's behaviour could
not have run at all — and tests that inspected its *source* passed instead, which looked like
evidence and was not.

## Probe & scratch policy

- Probe scripts and their outputs (`.jsonl`/`.txt` artifacts, `sliceN_*.py`) live in
  [`.claude/probes/`](.claude/probes/) and **are committed** — they are the audit trail.
- Scratch that is not meant to be kept (memory harnesses, `audit_tmp.json`, one-off
  `_fix_*.py` / `_probe*.py` / `sliceN_*` files) lives **outside the repo** (e.g. the OS
  temp dir). If it must appear at the repo root, it matches a root-scratch pattern in
  [`.gitignore`](.gitignore) and stays untracked-and-ignored.
- Stage explicit paths only — never `git add -A` — and end every work session with a
  `git status` showing only intentional files.

## Good first contributions

- **A new free web-detector selector** — add an entry to a `browser_sites.json` (see
  [examples/browser_sites.example.json](examples/browser_sites.example.json)) and the probe notes in
  [docs/free-detector-probes.md](docs/free-detector-probes.md). No code required.
- **A new detector adapter** — implement the `Detector` protocol in `untell/detectors/base.py`
  (`score(text) -> float | None`, where `None` opts out for empty/too-short input), gate heavy deps behind availability checks, and add a test.
- **Rewrite-rubric improvements** — `untell/references/prompt-rubric.md` is where the named AI-signal
  targeting lives (clichés, formulaic transitions, sentence uniformity, vocab homogeneity, burstiness,
  perplexity).
- **Docs / examples / typos** — always welcome.

## How detector adapters work

Each adapter returns a single `P(AI) ∈ [0,1]`. The ensemble in `score.py` reports every detector plus the
`max` (the value the loop drives down). Keep adapters:

- **Tiered** — pure-stdlib ones run in the lite tier; torch ones gate on `import torch` succeeding and
  degrade gracefully (the score JSON's `tier` field reports what actually ran).
- **Honest** — if a model is non-commercial licensed (e.g. RADAR), mark it clearly and keep it opt-in.

## Adding a language

32% of the humanizer repos we profiled target a language other than English, and everything here
is English-only. `untell/languages.py` is the registry for fixing that; the catalogues are not
written, and will not be written by us, because Korean 번역체 calques and Chinese academic-register
tells need people who read those languages daily.

Adding one touches no existing file:

```python
# untell/tells_zh.py
from untell.languages import register

def score_zh(text: str, *, include_matches: bool = False) -> dict:
    ...  # same shape as score_tells: words, tells, tells_per_100w, by_category

register("zh", score_zh, script="Han", label="Chinese")
```

`catalogue_for(text)` then routes Han-script text to it. Until a language is registered, text in
that script returns **None** rather than falling back to English — running an English catalogue
over Korean finds no English tells and reports a clean score for text nothing examined, which is
worse than saying "not supported".

**What a catalogue needs before it ships is a measurement, not a word list.** Every figure in
`untell/scripts/tells.py` is precision against a paired human/AI corpus, and several patterns that
sounded obviously right turned out to point the wrong way — `em_dash`, the single most-cited AI tell
in public discourse, has fired on **0 AI documents out of 400** across two corpora. A Chinese
catalogue needs the equivalent: paired Chinese text, per-category precision, and the categories that
fail reported next to the ones that work. `tests/test_languages.py` deliberately asserts that only
English ships, so adding one is a conscious act with that expectation attached.

## Commit / PR style

- Small, focused PRs. One concern per PR.
- Describe *what* changed and *why*; if it changes a claim, include how to reproduce.
- Reference any issue it closes (`Closes #123`).

## License

By contributing, you agree your contributions are licensed under the repository's [MIT License](LICENSE).
