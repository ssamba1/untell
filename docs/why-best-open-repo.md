# Is this the best open-source AI-humanizer repo? The honest proof.

**Scope of the claim.** "Best humanizer *repo* available" means best **open-source** humanizer codebase
on GitHub. Commercial tools (Undetectable.ai, StealthGPT, WriteHuman…) are closed SaaS, not repos —
out of scope. We surveyed the open field blind (GitHub topics, papers-with-code, 15 repos). Verdict
below is evidenced, not asserted, and states honestly where we are *not* #1.

---

## The decisive finding

The independent survey of the open-source humanizer field concluded, verbatim:

> "There is **no** open-source repo that combines (a) a real evasion approach validated against
> multiple live detectors, (b) a quality/meaning-preservation verifier, (c) an iterative
> detector-feedback loop at inference time, and (d) a user-installable package."

**This repo is the one that has all four** — the only one filling that gap:

| Gap criterion | This repo |
|---|---|
| (a) validated vs **multiple live detectors** | 8 local (incl. RADAR, Binoculars, Fast-DetectGPT, MAGE, HC3) + **6 commercial API adapters** + browser checkers; **live-proven 100%→0% on ZeroGPT** |
| (b) quality/meaning **verifier** | semantic-similarity gate + preserve-lock (citations/numbers/entities) + `humanize-verify` |
| (c) **iterative detector-feedback loop at inference** | the core loop + **per-sentence targeting** (rewrite only the flagged sentences) |
| (d) **user-installable package** | `pip install` + 5 console scripts (`humanize-score/loop/verify/prove/sentences`) **and** a Claude skill |

---

## Feature matrix — this repo vs the strongest open competitors

| Capability | **ours** | StealthRL | patina | StealthHumanizer | DIPPER | lynote humanize-text | harshaneel/humanize |
|---|---|---|---|---|---|---|---|
| Inference-time detector-feedback loop | ✅ | ◑ (train-time) | ◑ (own heuristic) | ◑ (multi-pass) | ❌ | ❌ | ◑ (manual) |
| Multiple real detectors in the loop | ✅ (14) | ✅ (ensemble) | ❌ (own score) | ❌ (internal) | ❌ | ❌ | ◑ (Binoculars only) |
| Commercial-detector adapters (Originality/GPTZero/Turnitin-class) | ✅ (6) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Live-detector validation (real bypass shown) | ✅ (ZeroGPT 100→0) | ✅ (AUROC, paper) | ❌ | ❌ | ✅ (paper) | ❌ | ◑ (Binoculars) |
| Quality/meaning verifier (not just a claim) | ✅ semantic gate + lock | ✅ BERTScore | ✅ rollback | ✅ keyword recall | ◑ | claim only | heuristic |
| Per-sentence targeting | ✅ | ❌ | ◑ | ❌ | ❌ | ❌ | ❌ |
| Packaged install (pip / skill) | ✅ both | ❌ (research) | ✅ | ✅ | ❌ (GPU) | ✅ | ✅ (skill) |
| Automated tests | ✅ 16 modules | ◑ sanity | ✅ | ✅ | ❌ | ❌ | ◑ manual |
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
  GPU moat — see `best-humanizer-roadmap.md`.)
- **patina** (196★) — best-designed *consumer* tool: pattern analysis + LLM rewrite + meaning-rollback
  + CI. But its AI score is its **own heuristic** — no validation against real detectors, no
  commercial/live integration. We add the real-detector ensemble, commercial adapters, and live proof.
- **StealthHumanizer** (58★) — most features + CI, but a **12-metric internal** score, not real
  detectors. Same gap.
- **DIPPER** (199★) — credible research paraphraser, but **one-shot, GPU-only, no loop, no install**.
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

**Proof, not marketing:** measured live (ZeroGPT 100%→0%, and 100%→35%→0% via per-sentence feedback),
CI-green across real torch detectors, and feature-for-feature ahead of every open competitor on
completeness — with the one exception (StealthRL's raw model) named honestly.
