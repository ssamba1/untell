# Roadmap

Honest framing: "best ever" is **not** "passes everything forever" — that's impossible, because detectors
update, disagree, and re-score the same text differently. The goal is the best point on three axes at once:
**evasion strength × meaning/quality × trust (honest, reproducible scores)**. No shipping tool nails all
three; that's the opening this project aims at.

Legend: ✅ shipped · 🔜 buildable now (no new hardware) · ⛔ needs a GPU.

## Shipped

- ✅ **Closed-loop detector-feedback rewrite** — the strongest training-free technique
  ([arXiv 2506.07001](https://arxiv.org/abs/2506.07001)), live-proven (ZeroGPT 100%→0%).
- ✅ **Multi-detector ensemble** — 7 local adapters (perplexity/burstiness, RoBERTa-OpenAI, HC3, MAGE,
  Fast-DetectGPT, RADAR, Binoculars) + 6 commercial API adapters + a free browser checker. The loop drives
  the **max** across all of them.
- ✅ **Per-sentence targeting** (`humanize-sentences`) — rewrite only the sentences that read as AI.
- ✅ **Semantic-similarity gate + preserve-lock** — refuses meaning-breaking rewrites; locks
  citations/numbers/quotes/URLs/entities.
- ✅ **Honest verification** — `humanize-verify` / `humanize-prove`: per-detector pass/fail, exit 0 only when
  every configured checker passes.
- ✅ **No-GPU evasion toolkit** — word-importance-ranked synonym substitution, homoglyph substitution,
  hidden-watermark/zero-width scrubbing, back-translation (`humanize.attacks`).
- ✅ **Distribution** — Claude Code skill, pip CLIs, MCP server, `.docx`/`.pdf` input, style presets.

## Next — no new hardware

- 🔜 **Named-signal rubric** — make every AI tell an explicit rewrite instruction: clichés, formulaic
  transitions, sentence-length uniformity, vocabulary homogeneity (+ our burstiness/perplexity). Bakes the
  best ideas from the field into one prompt rubric.
- 🔜 **Contrastive-decoding rewrite backend (CoPA-style)** — two-pass human/AI prompting, subtract the AI
  logits. The most architecturally novel no-GPU win; needs an LLM exposing logprobs.
- 🔜 **SICO** — a one-time-optimized universal anti-detection prompt prefix, reused across rewrites.
- 🔜 **Reproducibility guard** — re-scan a pass once more (or with `--margin`) and only declare success if it
  holds, so a noisy detector can't re-flag a marginal pass.
- 🔜 **Published benchmark artifact** — commit `eval/benchmark --tier full --enable-radar` numbers
  (per-detector beat-rate incl. RADAR). The reproducible third-party-style test no competitor publishes.

## The moat — needs a GPU

- ⛔ **RL-against-ensemble** (StealthRL-style GRPO + LoRA) — reward = evasion vs our own detector ensemble +
  semantic similarity. The literature shows this **transfers to detectors it never trained on**. The
  `training/` directory scaffolds this; it's one GPU run away.
- ⛔ **Alignment rewriter (MASH-style)** — style-injection SFT → DPO for human-ness → inference-time
  refinement. Ship as a default local rewriter that needs no API key.

These two are the only capabilities that would make this the strongest *attack model* as well as the most
complete *system*. Everything else above is shippable today.

---

Want to pick something up? See [CONTRIBUTING.md](CONTRIBUTING.md). The 🔜 items are the best contributions.
