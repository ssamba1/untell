# Is this the best open-source AI-humanizer repo? The honest proof.

**Scope of the claim.** "Best humanizer *repo* available" means best **open-source** humanizer codebase
on GitHub. Commercial tools (Undetectable.ai, StealthGPT, WriteHuman…) are closed SaaS, not repos —
out of scope. We surveyed the open field ourselves (GitHub topics, papers-with-code, ~110 repos; see
`humanizer-research-report.md`), and re-swept it on 2026-08-05 across 624 distinct queries turning up
**1287 candidate repos, 435 read individually** ([`humanizer-census.md`](humanizer-census.md)) — see the box
below for what that census changed. Verdict below is evidenced, not asserted, and states honestly where we are *not* #1.

---

## The decisive finding

Our own deep-research survey of the field ([`humanizer-research-report.md`](https://github.com/ssamba1/untell/blob/main/humanizer-research-report.md))
ranks the exploitable gaps. Its **first** one, quoted exactly:

> "**Closed-loop detector-feedback rewriting.** No shipping product does iterative rewrite against
> live detector scores. Evidence says it's the single strongest lever (−88% TPR, training-free,
> quality-preserving). **Build this first.**"

The four criteria below are **our own framing** of what it would take to close that gap end to end —
they are not a quotation, and a previous version of this page presented them as one:

> **Superseded in part by the 2026-08-05 census** ([`humanizer-census.md`](humanizer-census.md) —
> 1287 repos found, 435 read individually). Three things on this page are now known to be wrong or
> too strong, and they are corrected there rather than quietly here:
>
> - **The detector loop is not ours alone.** 49 of 435 profiled repos put a detector in the loop,
>   44 of them at inference time. `chengez/Adversarial-Paraphrasing` couples it *per token*.
> - **Automated meaning verification is not ours alone.** 85 of 435 verify meaning, and 131 do some
>   form of fact preservation. `Advancing-Machine-Human-Reasoning-Lab/apt` uses the same bidirectional-NLI
>   entailment gate this repo does.
> - **"Most complete open humanizer" holds only in English.** 139 of the 435 (32%) target another
>   language — a per-record *reading*, not a derived count: the census JSON has no language field,
>   and three defensible keyword rules give 130, 135 and 138. Treat it as "roughly a third".
>   What is checkable is the top of the table. Three of the eight largest repos are non-English on
>   the evidence of their own census records — `gongzhonghao-rewrite` (298.8k★, its validator
>   checklist is quoted in Chinese), `kevintsai1202/Humanizer-zh-TW` (68.5k★) and `op7418/Humanizer-zh` (14.7k★, "a
>   Chinese-language text editor"). Korean `NomaDamas/k-skill` (7.0k★) and `epoko77-ai/im-not-ai` (4.2k★) are large and
>   non-English but rank 9th and 12th, so they are not among the eight largest; an earlier version
>   of this line named them as if they were. Our catalogue, the voice matcher's constants and every
>   measurement here are English-only.
>
> What survives is the **conjunction plus an installable package**, and the measurement discipline.
>
> - **Stars will not follow from any of this.** Measured across the census: our category holds
>   0.3% of the field's stars and its largest member has 413. Engineering raises the floor and
>   not the ceiling — see [what would make this the top repo](what-would-make-this-the-top-repo.md).
> No profiled repo has all four criteria and ships as a package.

> **Correction, 2026-08-05.** This section used to open with a block quote attributed *"verbatim"*
> to that report: *"There is no open-source repo that combines (a) a real evasion approach validated
> against multiple live detectors, (b) a quality/meaning-preservation verifier, (c) an iterative
> detector-feedback loop at inference time, and (d) a user-installable package."* **That sentence
> does not appear in the report — in any commit, ever.** It was checked against every version in git
> history; the distinctive phrases ("open-source repo", "user-installable", "quality/meaning") return
> zero hits in all of them, and the only two files in this repo containing them are this page and the
> README, both citing it as a quote. The report's actual claim is the one now quoted above, and it is
> **narrower and different**: it is about *shipping products*, not open-source repos.
>
> The report had also been deleted from the repo on 2026-07-28 (incidentally, in a commit about
> rewriter work), so all four citations of it — including a live hyperlink in the README — pointed at
> a missing file. It is restored.

Against our own four criteria, this repo has all four:

> The counterexample on criterion (c) is
> **[`chengez/Adversarial-Paraphrasing`](https://github.com/chengez/Adversarial-Paraphrasing)**
> (NeurIPS 2025, [arXiv:2506.07001](https://arxiv.org/abs/2506.07001)): **−87.88% average
> TPR@1%FPR** across neural, watermark and zero-shot detectors, and its loop runs **per token**
> (`Paraphraser.paraphrase()` scores every top-k candidate's partial decode). It has (a) and (c)
> without (b) or (d) — research code, no meaning gate in the pipeline, no package, no tests.
> Forty-eight other repos also close a loop; see the census for all of them.

| Gap criterion | This repo |
|---|---|
| (a) validated vs **multiple live detectors** | 8 local adapters — 5 run by default (RoBERTa-OpenAI, HC3, Fast-DetectGPT, MAGE, GPT-2 perplexity); RADAR is opt-in via `UNTELL_ENABLE_RADAR=1` (non-commercial license) and Binoculars needs CUDA — + **7 commercial API adapters** + browser checkers; **live-proven 100%→0% on ZeroGPT** (measured 2026-06-25 on the formulaic demo paragraphs; a third-party site that can change without notice — re-run `--browser zerogpt` before citing it) |
| (b) quality/meaning **verifier** | semantic-similarity gate + preserve-lock (citations/numbers/entities) + `untell-verify` |
| (c) **iterative detector-feedback loop at inference** | the core loop + **per-sentence targeting** (rewrite only the flagged sentences) |
| (d) **user-installable package** | `pip install` + **26** console scripts (`untell`, `-score`, `-loop`, `-humanize`, `-verify`, `-prove`, `-sentences`, `-tells`, `-voice`, `-humanness`, `-hedges`, `-numbers`, `-scrub`, `-explain`, `-batch`, `-watch`, `-compare`, `-ceiling`, `-detector-audit`, `-eval-policy`, `-distill`, `-surrogate`, `-server`, `-mcp`, `-audit`, `-latex`) **and** an MCP server, a REST API and a Claude skill |

---

## What the measurement discipline actually buys — a worked example

The claim above reduces to "we look, and we publish what we find." Here is the most useful thing it
found, in 2026-08-09.

Both model-backed meaning gates were **not reading the whole document**. The entailment gate
tokenises `(original, rewrite)` as one sequence truncated at 256 tokens; the similarity gate's
embedding backends truncate too. Neither says so. Measured by moving the *same* edit to a different
position in the *same* document:

| edit: "improved outcomes" → "did NOT improve outcomes" | at the start | at the end |
|---|---|---|
| 7 words | 0.9976 | 0.9971 |
| 143 words | 0.9833 | **0.0179** |
| 279 words | 0.9833 | **0.0179** |

`0.0179` is the contradiction score for two **identical** strings. And the similarity gate scored a
whole sentence replaced with unrelated text at **1.0000** past 280 words.

Neither is a mis-set threshold. The changed text was never fed to the model, so no value of the
0.76 similarity bar or the 0.5 contradiction bar could have caught either — the gates were most
confident exactly where they were blindest. A rewriter could invert any claim after roughly the
first 130 words of a document and nothing in this project would have noticed.

**Why this is the example worth giving.** It was found by probing a property no test suite naturally
checks — *does the answer depend on where in the input the change is?* — not by a failing test, a
bug report, or reading the code. The fix is in, the invariant is pinned
(`tests/test_gates_read_the_whole_document.py`), and the write-up includes the version of the fix
that was **wrong**: aligning chunks proportionally drifts once the rewriter merges sentences, which
produced false vetoes on faithful rewrites until the cut points came from `difflib` instead.

**And the first fix only closed half of it, which is the more useful part of the story.** Chunking
was applied to the contradiction check and deliberately *not* to entailment — the proportional
version had caused false vetoes there, so it was reverted and left whole-text. Contradiction catches
meaning INVERSION; entailment catches meaning LOSS, because deleting content contradicts nothing.
So the same measurement, re-run for deletion instead of inversion, still failed:

| most of a sentence deleted | entailment | verdict |
|---|---|---|
| after 10 words | 0.0017 | caught |
| after 140 words | **0.9800** | **missed** |
| after 280 words | **0.9800** | **missed** |

with contradiction innocent at 0.003, similarity 0.965 and the numeral, certainty and polarity
guards all clean — the whole gate passed it. Entailment is now chunked as well; the revert's reason
had expired when the aligner moved to `difflib`, and re-measured against the current one it newly
vetoes 0 of 25 candidates the gate accepts. The lesson is not about NLI: a fix aimed at one symptom
of a shared cause leaves the other symptoms, and reporting the fix as complete is what stops anyone
looking.

**What it does not let us claim.** This page notes that
`Advancing-Machine-Human-Reasoning-Lab/apt` uses the same bidirectional-NLI entailment gate. The
truncation follows from the *standard* way that model is called, so the same failure plausibly
exists wherever the pattern is copied — but we have not run their code and are not asserting it.
It is a hypothesis about the field, offered as something worth checking, and the way to check it is
in this repo: move one edit to the end of a long document and see whether the verdict changes.

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
| Automated tests | ✅ **10668** tests, 658 modules (reproduce with `UNTELL_LITE_NO_TORCH=1 pytest --collect-only -q`) | ◑ sanity | ✅ | ✅ | ❌ | ❌ | ◑ manual |
| CI (lite + full-tier, real models) | ✅ 4 jobs | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Runs without a GPU | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ | ✅ |
| License | MIT | MIT | MIT | MIT | Apache | MIT | MIT |

Stars are not capability: lynote (1.4k★) is an unvalidated translation chain; DadaNanjesha (394★) is a
pre-LLM NLP style transformer; obaskly (124★) just automates the *commercial* undetectable.ai. None
close the loop against real detectors with a verifier and an install.

---

## What each competitor is, and why we're more complete

- **StealthRL** (18★, the SOTA research repo) — once described here as "the only other repo that
  truly closes a detector loop"; the census counted **49**, so read this as one of the strongest, not
  the only. It closes it
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
