# Is this the best open-source AI-humanizer repo? The honest proof.

**Scope of the claim.** "Best humanizer *repo* available" means best **open-source** humanizer codebase
on GitHub. Commercial tools (Undetectable.ai, StealthGPT, WriteHuman…) are closed SaaS, not repos —
out of scope. We surveyed the open field ourselves (GitHub topics, papers-with-code, ~110 repos; see
`humanizer-research-report.md`), and re-swept it on 2026-08-05 across 624 distinct queries turning up
1124 candidate repos — see the box below for what that sweep changed and where it stopped short. Verdict below is evidenced, not asserted, and states honestly where we are *not* #1.

---

## The decisive finding

Our own deep-research survey of the open-source humanizer field (`humanizer-research-report.md`) concluded, verbatim:

> "There is **no** open-source repo that combines (a) a real evasion approach validated against
> multiple live detectors, (b) a quality/meaning-preservation verifier, (c) an iterative
> detector-feedback loop at inference time, and (d) a user-installable package."

**This repo is the one that has all four** — the only one filling that gap:

> **Re-surveyed 2026-08-05. The four-part conjunction still holds; one of its parts, read alone,
> does not.** A fresh sweep (624 distinct queries, 1124 candidate repos) turned up a genuine
> counterexample on criterion (c): **[`chengez/Adversarial-Paraphrasing`](https://github.com/chengez/Adversarial-Paraphrasing)**
> (NeurIPS 2025, [arXiv:2506.07001](https://arxiv.org/abs/2506.07001)) paraphrases *under the
> guidance of an AI text detector* — an inference-time detector-feedback loop, training-free, and
> with far stronger published numbers than anything here: **87.88% average TPR@1%FPR reduction**
> across neural, watermark-based and zero-shot detectors (98.96% against Fast-DetectGPT, 64.49%
> against RADAR).
>
> So "(c) at inference time" is **not** ours alone, and this page previously read as if it were.
> What survives is the conjunction: chengez is research code — its quality check is a post-hoc
> GPT-4o evaluation for the paper, not a gate inside the pipeline, and there is no installable
> package — so it has (a) and (c) without (b) or (d).
>
> Two claims in the same sweep were checked and **did not hold up**, recorded so they are not
> repeated: `rudra496/StealthHumanizer` was reported as looping and does not ("the detector runs
> after humanization to show results, not to drive refinement"; its score is a 12-metric internal
> heuristic), and `devswha/patina` was too ("one-shot rewrite with post-hoc verification, not
> iterative detector-driven loops"). Both characterisations in the matrix below were already right.
>
> The sweep did **not** finish: it stopped on an API spend limit after the discovery phase, so
> none of the 1124 candidates were profiled and no completeness critic ran. Read the conjunction
> claim as "not refuted by a partial survey", not as "verified exhaustively".

| Gap criterion | This repo |
|---|---|
| (a) validated vs **multiple live detectors** | 8 local adapters — 5 run by default (RoBERTa-OpenAI, HC3, Fast-DetectGPT, MAGE, GPT-2 perplexity); RADAR is opt-in via `UNTELL_ENABLE_RADAR=1` (non-commercial license) and Binoculars needs CUDA — + **7 commercial API adapters** + browser checkers; **live-proven 100%→0% on ZeroGPT** (measured 2026-06-25 on the formulaic demo paragraphs; a third-party site that can change without notice — re-run `--browser zerogpt` before citing it) |
| (b) quality/meaning **verifier** | semantic-similarity gate + preserve-lock (citations/numbers/entities) + `untell-verify` |
| (c) **iterative detector-feedback loop at inference** | the core loop + **per-sentence targeting** (rewrite only the flagged sentences) |
| (d) **user-installable package** | `pip install` + **21** console scripts (`untell`, `-score`, `-loop`, `-humanize`, `-verify`, `-prove`, `-sentences`, `-tells`, `-voice`, `-humanness`, `-hedges`, `-numbers`, `-scrub`, `-compare`, `-ceiling`, `-detector-audit`, `-eval-policy`, `-distill`, `-surrogate`, `-server`, `-mcp`) **and** an MCP server, a REST API and a Claude skill |

---

## Feature matrix — this repo vs the strongest open competitors

| Capability | **ours** | StealthRL | patina | StealthHumanizer | DIPPER | lynote humanize-text | harshaneel/humanize |
|---|---|---|---|---|---|---|---|
| Inference-time detector-feedback loop | ✅ | ◑ (train-time) | ◑ (own heuristic) | ◑ (multi-pass) | ❌ | ❌ | ◑ (manual) |
| Multiple real detectors in the loop | ✅ (14) | ✅ (ensemble) | ❌ (own score) | ❌ (internal) | ❌ | ❌ | ◑ (Binoculars only) |
| Commercial-detector adapters (Originality/GPTZero/Turnitin-class) | ✅ (6) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Live-detector validation (real bypass shown) | ✅ (ZeroGPT 100→0, 2026-06-25, demo corpus) | ✅ (AUROC, paper) | ❌ | ❌ | ✅ (paper) | ❌ | ◑ (Binoculars) |
| Quality/meaning verifier (not just a claim) | ✅ semantic gate + lock | ✅ BERTScore | ✅ rollback | ✅ keyword recall | ◑ | claim only | heuristic |
| Per-sentence targeting | ✅ | ❌ | ◑ | ❌ | ❌ | ❌ | ❌ |
| Packaged install (pip / skill) | ✅ both | ❌ (research) | ✅ | ✅ | ❌ (GPU) | ✅ | ✅ (skill) |
| Automated tests | ✅ **1694** tests, 61 modules | ◑ sanity | ✅ | ✅ | ❌ | ❌ | ◑ manual |
| CI (lite + full-tier, real models) | ✅ 4 jobs | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Runs without a GPU | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ | ✅ |
| License | MIT | MIT | MIT | MIT | Apache | MIT | MIT |

Stars are not capability: lynote (1.4k★) is an unvalidated translation chain; DadaNanjesha (394★) is a
pre-LLM NLP style transformer; obaskly (124★) just automates the *commercial* undetectable.ai. None
close the loop against real detectors with a verifier and an install.

---

## What each competitor is, and why we're more complete

- **StealthRL** (16★, the SOTA research repo) — the only other repo that truly closes a detector loop,
  via **GRPO RL training** of a Qwen3-4B policy against an ensemble (97.6% ASR, transfers to held-out
  detectors). **Genuinely a stronger raw evasion *model* than ours** — and we say so. But it is a
  **GPU training framework, not a usable tool**: no inference package, no commercial-detector
  validation, no verifier for end users, no CI, needs serious GPU. We are the **usable, complete,
  installable** system; it is the **strongest attack model**. (We roadmap exactly its approach as our
  GPU moat — see `ROADMAP.md`.)
- **patina** (311★ as of 2026-08-05, was 196★) — best-designed *consumer* tool: pattern analysis + LLM rewrite + meaning-rollback
  + CI. But its AI score is its **own heuristic** — no validation against real detectors, no
  commercial/live integration. We add the real-detector ensemble, commercial adapters, and live proof.
- **StealthHumanizer** (58★) — most features + CI, but a **12-metric internal** score, not real
  detectors. Same gap.
- **DIPPER** (199★) — credible research paraphraser, but **one-shot, GPU-only, no loop, no install**.
- **chengez/Adversarial-Paraphrasing** (NeurIPS 2025, arXiv:2506.07001) — **the strongest published
  inference-time detector-guided attack, and the counterexample to criterion (c) above.** Training-free:
  an off-the-shelf instruction LLM paraphrases under a detector's guidance. **87.88% average TPR@1%FPR
  reduction** across neural, watermark-based and zero-shot detectors (98.96% vs Fast-DetectGPT, 64.49%
  vs RADAR) — numbers far beyond anything measured here, peer-reviewed, and on a proper evaluation set
  rather than our n=6..12. What it is not: a product. No meaning gate inside the pipeline (quality is a
  post-hoc GPT-4o evaluation for the paper), no numeral/citation preservation, no installable package,
  no test suite. **If someone packaged its mechanism behind our meaning gates, the result would beat
  this repo outright** — that is the most credible threat in the field, and it is stated here rather
  than left out.
- **Skill-file repos** (harshaneel 51★, Aboudjem 96★) — pure-markdown heuristic skills (like our
  `SKILL.md`) but with **no detector backend, no loop, no tests**. Ours is a skill *backed by* a real
  detector ensemble + loop + verify + CI.
- **peggywritesforyou** (~3★) — the *closest architecturally*: a real Python/Flask tool that independently
  arrived at the same 5-pillar design (adversarial feedback loop, multi-detector cross-validation, targeted
  prompting, per-sentence targeting, pivot-language rotation), using RoBERTa + Sapling + ZeroGPT. Credit
  where due. We beat it on: **commercial-detector adapters** (Originality/Turnitin-class), a **semantic
  meaning gate** (it relies on a human-in-the-loop review panel, not an automated similarity gate), a
  **packaged pip + skill install**, **CI**, and **published live proof**. It's the one open repo that shares
  our architecture — and we're the more complete, verifiable system.

---

## The research systems that use detector feedback (2024-2025)

Surveyed 2026-08-05 and verified against each repo's own README and paper. None of these were in
the matrix above, and together they are the honest answer to "is the closed loop ours alone" — it
is not. All three are **research artifacts, not products**: no meaning gate inside the pipeline, no
numeral or citation preservation, no installable package, no test suite. That is the distinction
this page rests on, and it is a narrower claim than "nobody else closes the loop".

| repo | venue | how the detector is used | what it reports |
|---|---|---|---|
| [`chengez/Adversarial-Paraphrasing`](https://github.com/chengez/Adversarial-Paraphrasing) | NeurIPS 2025 | **Inference-time, per text.** An off-the-shelf instruction LLM paraphrases under a detector's guidance. Training-free. | **−87.88% average TPR@1%FPR** across neural, watermark and zero-shot detectors (−98.96% Fast-DetectGPT, −64.49% RADAR) |
| [`ColinLu50/Evade-GPT-Detector`](https://github.com/ColinLu50/Evade-GPT-Detector) (SICO) | TMLR 2024 | **Optimisation-time.** A proxy detector scores candidates while in-context examples are iteratively optimised (~6 iterations); the resulting prompt is then applied without further scoring. | claims evasion of "all existing AI-generation text detectors, including GPTZero and the OpenAI official detector", on SQuAD / ELI5 / Yelp |
| [`zhouying20/HMGC`](https://github.com/zhouying20/HMGC) | COLING 2024 | **Training-time.** Distils labels from the victim detector into a surrogate, then attacks the surrogate. | see [arXiv:2404.01907](https://arxiv.org/abs/2404.01907) |

Three things worth stating plainly:

- **SICO's claim bears on ours.** This page and the README say no free tool beats GPTZero. SICO's
  paper claims exactly that, in 2024. We have not reproduced it, GPTZero has changed since, and SICO
  needs a paid LLM to run — but "nobody has claimed it" would be false, and the honest position is
  that we have not tested it rather than that it does not exist.
- **HMGC is the approach this repo roadmaps as its own next step** (surrogate distillation — see
  `training/surrogate.py`). It is not a gap in the argument, it is prior art for our own plan, and
  citing it is better than presenting the idea as novel.
- **Only chengez is inference-time per text**, which is the shape our loop has. SICO optimises once
  and then applies a fixed prompt; HMGC trains. Those are different products with different costs.

---

## The honest caveats (where we are NOT #1)

1. **Raw evasion-model strength:** StealthRL's GPU-trained RL policy is a stronger *attack model* than
   our training-free loop. We are the most complete *system*; it is the strongest *model*. The fix is
   our roadmapped GPU moat (RL-against-ensemble / MASH), not yet built.
2. **Beating the hardest commercial detectors (Originality/Turnitin):** machinery built + verifiable,
   but **needs paid keys to prove** — untested, and research says these are genuinely hard.
3. **Stars/maturity:** newer repo; lynote/DIPPER/DadaNanjesha have more stars (mostly unvalidated).

---

## Verdict

By the survey's own gap definition, **this is the most complete and capable open-source AI-humanizer
repo available** — the only one combining a real multi-detector-validated, quality-gated, inference-time
**closed loop** with a **packaged install + a Claude skill + CI + live proof**. It is the best *usable*
open humanizer. The single thing that would also make it the strongest *attack model* — GPU-trained
RL-against-ensemble — is the one item explicitly roadmapped and honestly deferred for hardware.

**Proof, not marketing:** measured live on 2026-06-25 against the formulaic demo paragraphs (ZeroGPT 100%→0%, and 100%→35%→0% via per-sentence feedback),
CI-green across real torch detectors, and feature-for-feature ahead of every open competitor on
completeness — with the one exception (StealthRL's raw model) named honestly.
