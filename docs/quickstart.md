# Quick Start

Get untell running in 60 seconds.

## Install

```bash
# Lite tier — zero dependencies, works immediately:
pip install untell

# Full tier — real AI-detector ensemble (recommended):
pip install "untell[full]"

# Everything (full + API server + training):
pip install "untell[full,server,train]"
```

## Humanize your first text

```bash
# Free, no API key needed:
untell humanize \
  "Furthermore, artificial intelligence has fundamentally transformed numerous industries. Moreover, organizations increasingly leverage these technologies to optimize operational efficiency and drive innovation." \
  --rewriter surgical
```

This runs the closed loop with the deterministic word-substitution rewriter — **$0, no GPU, no API key.**

## Score text

```bash
untell score "Your text here" --tier full
```

Returns JSON with per-detector P(AI) scores and the ensemble `max`.

## Count AI tells

```bash
untell tells "Your text here"
```

Counts machine-writing markers: em-dashes, AI vocabulary, formulaic transitions, etc. **Lower = more human.**

## Verify against detectors

```bash
# Local ensemble:
untell verify "Your text here" --tier full

# With commercial detectors (set API keys):
export GPTZERO_API_KEY=...
untell verify "Your text here" --tier commercial
```

## Run the API server

```bash
pip install "untell[server]"
untell-server
```

Open http://localhost:8000/docs for the interactive OpenAPI docs.

## In Claude Code

```bash
/plugin marketplace add ssamba1/untell
/plugin install untell@untell
```

Then: `/untell <your text or file path>`

## Next steps

- [How the closed loop works](https://github.com/ssamba1/untell#tldr) — score, rewrite, re-score,
  and the meaning gates that decide whether a candidate is allowed through.
- [CLI reference](https://github.com/ssamba1/untell#-quick-start) — every subcommand, or run
  `untell --help`, which is generated from the same parsers and cannot go stale.
- [All detector tiers](https://github.com/ssamba1/untell#tiers) — what `lite`, `full`, `heavy` and
  `commercial` actually load, and what each one is worth.
- [What the free tier can and cannot do](free-ceiling-measured.md) — the measurements, including
  the ones that came out against us.
