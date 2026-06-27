# The free ceiling of a closed-loop AI-text humanizer

**What is the realistic ceiling of a zero-out-of-pocket humanizer** — one that may use only free
resources (downloadable open-source detector and rewriter models, free Colab/Kaggle GPU, free
automatable detector web UIs, free API trial quotas, and a frontier LLM the user already has via
Claude Code)? This report answers that for the `untell` architecture: a training-free, closed-loop,
detector-feedback rewriter gated on semantic similarity and byte-exact citation preservation.

It is deliberately honest about what free **cannot** do, in keeping with the rest of the project.

## How this was produced

A deep-research pass: the question was decomposed into 5 angles, searched in parallel, 22 sources
fetched, 104 falsifiable claims extracted, and the top 25 put through 3-vote adversarial verification
(a claim needed 2 of 3 independent refutation attempts to fail). **9 claims survived, 16 were
killed** — including several plausible-but-wrong claims that would otherwise have shaped the design
(see *Killed claims*). Treat 2025–2026 arXiv preprints as preliminary; only MASH is peer-reviewed
(ACL 2026 Findings).

## The one-line ceiling

The published state of the art (92–97.6% attack success) **requires GPU fine-tuning**; no verified
training-free method reaches it. For a $0 tool the ceiling is **high against the open/local detectors
you can put in the loop, and fundamentally unprovable against the dominant commercial detectors**
(GPTZero, Originality.ai, Turnitin) — because you cannot put those in the loop for free, and they
actively counter-detect humanized text.

## Ceiling by detector tier (ranked by free-reachability)

| Tier | Free-reachable? | Evidenced ceiling |
|---|---|---|
| **Local open-source** (RoBERTa-OpenAI, Fast-DetectGPT, Binoculars, MAGE) | Yes — runs locally on CPU/GPU | **Trained:** 97.6% ASR, mean TPR@1%FPR → 0.024 (StealthRL). **Inference-only (untell's regime): now MEASURED** — see [`free-ceiling-measured.md`](free-ceiling-measured.md): a modest, unreliable drop (mean max P(AI) 0.86 → ~0.74–0.76), far below the trained ceiling, with content-locked detectors immovable by any meaning-preserving rewrite. |
| **Free web UI** (ZeroGPT, others still automatable) | Yes, but slow (~10 s/check) and increasingly bot-gated | In-loop optimization works in principle. ZeroGPT is **not** established as uselessly inaccurate (that claim was refuted 0-3). |
| **Commercial API** (GPTZero, Originality.ai) | No — paid API only | Beating them needs them **inside the training reward**: AuthorMist drove GPTZero 88% → 12%, but only because GPTZero was the reward signal; training on GPTZero alone left WinstonAI at 30%. |
| **Turnitin** | No — **no public API at all** | Out of reach of any automated loop, free or paid. |

**The gap the literature leaves open:** the strongest systems never evaluated the detectors people
actually fear on a genuinely held-out basis. MASH tested only Writer (89% ASR) and Scribbr (90%) —
both niche. StealthRL tested only open-source detectors. AuthorMist's commercial numbers are in-loop,
not held-out. **No verified ceiling exists against GPTZero, Originality.ai, ZeroGPT, or Turnitin for
anyone, trained or training-free.** This is the central unknown for untell's real use case.

## The two axes and where they trade off

**Evasion is bounded by which detector is in the loop.** untell has the open ones, so it can push
hard on those. The published training-free closed-loop attack that untell's architecture mirrors
(Adversarial Paraphrasing, arXiv:2506.07001) reports **−87.88% TPR@1%FPR averaged across 8 detectors**
*with an off-the-shelf detector in the loop* (Fast-DetectGPT −98.96%, RADAR −64.49%). That is the
regime untell operates in. The widely-misread "stylistic prompts move Binoculars by ≤1pp" result
(confirmed 3-0) is for one-shot prompts *without* a detector in the loop — it does not bound a
closed-loop system.

**Readability stays high by design.** The Claude rewriter, the semantic-similarity gate, the
byte-exact sentinel lock, and the AI-tells catalog (`references/ai-tells.md`) keep output reading
human. The frontier is real: aggressive token-level substitution (PWWS-style word swaps reach
61–100% ASR on open detectors, CPU-only and free) buys evasion at the cost of fluency. untell's
similarity gate is the correct guard for staying on the human-reading side of that trade.

So the achievable corner of the trade-off, for free, is: **prose that reads genuinely human and
clears the detectors you can run/automate.** The unreachable corner is: **prose provably undetectable
by GPTZero/Originality/Turnitin** — for free or otherwise.

## Highest-leverage free moves, ranked

1. **Measure untell's inference-only evasion** against the local open detectors. The literature has
   *no* data point in this regime; the eval harness can produce the one number nobody has. Free, and
   it tells you exactly where untell sits between 1% and 97.6%. Do this first.
2. **Promote word-importance substitution into the loop.** untell already ships `surgical_substitute`;
   PWWS-style attacks reach 61–100% ASR on open detectors, CPU-only. Expected magnitude: large on the
   open tier.
3. **Best-of-N + Claude-as-judge.** Generate N rewrites, score all, and use Claude itself (with the
   ai-tells catalog) as an extra detector signal. Free (tokens only); lifts both axes; magnitude
   unmeasured but plausibly substantial.
4. **Free-GPU LoRA-RL policy** — the real ceiling-raiser, and the one item that needs effort.
   StealthRL's 97.6% used Qwen3-4B + LoRA rank-32 rewarded by the **free** open-detector ensemble — a
   setup that fits a free Colab T4 (16 GB, 12 h/session) or Kaggle (~30 h/week). So the ~97% open-tier
   ceiling is plausibly reproducible at $0. Fragile (preemptible GPU, time caps) and only valid
   against the open detectors it trains on.
5. **Put ZeroGPT (and any still-automatable free web detector) in the loop.** The only real-detector
   signal available for free. Slow and fragile, but it is a real target rather than a proxy.

## What free cannot do

- **Guarantee beating GPTZero / Originality.ai / Turnitin.** You cannot query them for free to
  optimize against, local-proxy correlation with them on *adversarial* text is unestablished (and may
  be near-zero), and GPTZero ships a dedicated anti-humanizer classifier reporting ~95% accuracy on
  output from popular bypass tools (2025). Any "beats Turnitin" claim is unprovable for free. The
  tool should keep saying exactly that.
- **Reach the published 92–97.6% ceiling with zero training.** Pure inference sits below it; the top
  of the open-tier range needs the free-GPU LoRA-RL step.

## A note on false positives

Detectors are noisy. Leading tools (Turnitin, GPTZero, Copyleaks) falsely flag roughly 1–2% of
human essays at baseline, with materially higher rates for non-native (ESL) writers and some
neurodivergent writers. This is why untell frames itself as a research tool and a defense against
false positives, not a guarantee of evading any specific system.

## Killed claims (verification kept these out of the design)

- "ZeroGPT is uselessly inaccurate (16.9% accuracy)." Refuted 0-3.
- "Binoculars ≈ Originality, and collapses to ~42% on GPT-4 text." Refuted 0-3 / 0-3 — no confirmed
  GPT-4 weak spot.
- "Detector vulnerabilities are orthogonal and don't transfer." Refuted 0-3 — they *do* transfer,
  which is why optimizing the `max` across an ensemble is sound.
- "TempParaphraser is a training-free 82.5% attack." Refuted 1-2 — there is no verified high-ASR
  training-free baseline besides Adversarial Paraphrasing.

## Open questions worth measuring

1. untell's actual inference-only % flagged after N rounds against Binoculars / Fast-DetectGPT (move
   #1 above).
2. Whether closed-loop rewriting against an open detector transfers at all to GPTZero/Originality on
   held-out text — i.e. is there *any* free proxy correlation with the commercial tier.
3. The practical free-Colab/Kaggle ceiling for GRPO on a 3–4B model rewarded only by open detectors
   (no paid API), which is where untell's "GPU moat" would sit.

## Sources

- Adversarial Paraphrasing (training-free closed loop, −88% TPR@1%FPR): arXiv:2506.07001
- MASH (92% avg ASR, SFT+DPO, ACL 2026 Findings): arXiv:2601.08564
- StealthRL (97.6% ASR, GRPO+LoRA on Qwen3-4B vs 4 open detectors): arXiv:2602.08934
- AuthorMist (GPTZero 88%→12% in-loop, GRPO vs commercial APIs): arXiv:2503.08716
- Binoculars (≤1pp from stylistic prompts; adversarial bypass out of scope): arXiv:2401.12070
- Attacks retain stylistic fingerprints: arXiv:2505.14608
- RAID detector benchmark (TPR@FPR head-to-head): arXiv:2405.07940
- GPTZero anti-humanizer / AI-paraphrasing detection: gptzero.me/news/ai-paraphrasing-detection,
  gptzero.me/news/detecting-ai-humanized-text-how-gptzero-stays-ahead
- Free-GPU limits (Colab T4 16 GB / 12 h, Kaggle ~30 h/wk): thundercompute.com colab-alternatives
- False-positive / ESL bias: arXiv:2406.01179, researchgate AI-detection false-positive impacts

*Generated by the project's deep-research harness (5 angles, 22 sources, 25 claims adversarially
verified). Numbers are reported as published; arXiv preprints from 2025–2026 are preliminary.*
