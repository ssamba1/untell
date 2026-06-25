# Contributing to humanize

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
git clone https://github.com/ssamba1/humanize
cd humanize
pip install -e ".[dev]"        # ruff + pytest + requests
# optional, for real detector signal:
pip install -e ".[full,eval]"
```

## Before you open a PR

```bash
ruff check .       # lint (must be clean)
ruff format .      # auto-format
pytest -q          # tests (must be green; lite tier needs zero ML)
```

CI runs the same checks on Python 3.9 / 3.11 / 3.12 plus a full-tier job that loads the real torch
detectors. A PR that's green locally should be green in CI.

## Good first contributions

- **A new free web-detector selector** — add an entry to a `browser_sites.json` (see
  [examples/browser_sites.example.json](examples/browser_sites.example.json)) and the probe notes in
  [docs/free-detector-probes.md](docs/free-detector-probes.md). No code required.
- **A new detector adapter** — implement the `Detector` protocol in `humanize/detectors/base.py`
  (`score(text) -> float in [0,1]`), gate heavy deps behind availability checks, and add a test.
- **Rewrite-rubric improvements** — `humanize/references/prompt-rubric.md` is where the named AI-signal
  targeting lives (clichés, formulaic transitions, sentence uniformity, vocab homogeneity, burstiness,
  perplexity).
- **Docs / examples / typos** — always welcome.

## How detector adapters work

Each adapter returns a single `P(AI) ∈ [0,1]`. The ensemble in `score.py` reports every detector plus the
`max` (the value the loop drives down). Keep adapters:

- **Tiered** — pure-stdlib ones run in the lite tier; torch ones gate on `import torch` succeeding and
  degrade gracefully (the score JSON's `tier` field reports what actually ran).
- **Honest** — if a model is non-commercial licensed (e.g. RADAR), mark it clearly and keep it opt-in.

## Commit / PR style

- Small, focused PRs. One concern per PR.
- Describe *what* changed and *why*; if it changes a claim, include how to reproduce.
- Reference any issue it closes (`Closes #123`).

## License

By contributing, you agree your contributions are licensed under the repository's [MIT License](LICENSE).
