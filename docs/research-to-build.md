# What the literature gives us that we can actually use

Companion to [`ai-writing-research.md`](https://github.com/ssamba1/untell/blob/main/ai-writing-research.md) (what has been published) and
[`humanizer-research-report.md`](https://github.com/ssamba1/untell/blob/main/humanizer-research-report.md) (evasion and the humanizer
market). **This document is only the intersection: findings that translate into a dataset, a metric, a
module, or a claim this repo can ship.** Everything else was left in the map.

Ranked by what it buys us over effort. Same verification caveat as the map: `arxiv.org` is
egress-blocked here, so papers were located through search indexes and publisher pages and **not read
in full** — every item below needs the source read before its numbers enter a shipped claim.

---

## The five that matter

### 1. Conformal FPR control — turns the repo's negative result into a constructive one

**arXiv:2505.05084**, ACL 2025 ([ACL Anthology](https://aclanthology.org/2025.acl-long.601/)) —
*Reliably Bounding False Positives: A Zero-Shot MGT Detection Framework via Multiscaled Conformal
Prediction (MCP)*. Uses a small calibration set of human-authored text to derive **length-conditioned
quantile thresholds** with a guaranteed FPR bound, and ships **RealDet**, a multi-domain calibration
corpus.

This is the single most valuable thing found. Right now untell says *your detector's shipped threshold
produces a 17%/40%/89% false-positive rate*. MCP is the answer to the obvious next question — **"then
what threshold should I use?"** — and it answers it with a bound rather than a tuned number.

It also lands directly on a finding the repo already has and currently reports as a wart:
`docs/../untell/references/thresholds.md` documents that lite and full tiers diverge with document
length, and that a single `threshold` doing double duty as stop target and verdict bar is the source of
the 52% → 18% cut. MCP's length-conditioned quantiles are the principled version of the
`verdict_threshold` split that was arrived at empirically.

**Build:** `untell/calibrate.py` — fit quantiles from a human-only calibration set at a user-chosen α,
emit a per-detector, per-length-bucket threshold table; `score_text` gains a `calibrated_verdict`
alongside the existing two. Wire `eval/` to report *both* the vendor threshold and the α-calibrated one
so the gap between them is the headline number.

### 2. Beemo and ARB — the two datasets that test what we actually claim

The repo has HC3, RAID and MAGE (`eval/datasets.py`). All three are **human vs. fully machine**. The
question untell exists to ask — does a verdict survive meaning-preserving editing — has no ground-truth
dataset wired in, only the repo's own rewriter, which is in-sample by construction.

- **Beemo** ([arXiv:2411.04032](https://arxiv.org/abs/2411.04032), NAACL 2025,
  [HF](https://huggingface.co/datasets/toloka/beemo), [code](https://github.com/Toloka/beemo)) — 6.5k
  human / machine texts from ten instruction-tuned LLMs **edited by expert annotators**, plus 13.1k
  LLM-edited, 19.6k total. Benchmarked over 33 detector configurations. Their headline: **expert
  editing evades detection, LLM editing does not**. That is an external, human-produced control for the
  exact transformation untell's loop performs — and it means the repo can finally separate "our
  rewriter moves the score" from "meaning-preserving editing moves the score".
- **ARB** ([arXiv:2607.29539](https://arxiv.org/abs/2607.29539)) — 1,800 human sources × four matched
  variants: HUMAN, Free-LLM, **H2L (LLM-rewritten human text)**, LLM2L. Evaluated at TPR@1%FPR across
  five detectors including Binoculars and RADAR, both of which we ship.

**H2L is the false-accusation case and we have no data for it.** A human writes it, an LLM polishes
it — the single most common real-world configuration, and the one every disciplinary hearing is
actually about. Adding ARB lets untell report the number nobody reports: what a detector does to human
writing that has been through a grammar pass.

**Build:** two loaders in `eval/datasets.py` alongside `_raid_pairs` / `_mage_pairs`. Beemo needs a
four-way label (human / machine / expert-edited / LLM-edited), not the current pair shape — worth the
refactor.

### 3. The base-model measurement — a cheap, devastating, house-style negative result

**arXiv:2605.19516** — *Base Models Look Human To AI Detectors*. Text from **base** (non-instruction-tuned)
models is judged overwhelmingly human by GPTZero and Pangram; their instruction-tuned counterparts are
not. The authors build HIP (Humanization by Iterative Paraphrasing) on top of it.

The attack is not the interesting part for us. **The measurement is:** if a base model's raw output is
already unflagged, the detector is detecting *instruction tuning and RLHF style*, not machine
generation. That reframes every false positive in the repo — an L2 writer, an autistic writer, a
technical writer is flagged for **writing in the register RLHF converges on**, which is exactly the
homogenization literature's finding arriving from the other side. It also gives a one-command
demonstration:

    untell-detector-audit --arm base-vs-instruct

Score matched base and instruct output from the same model on the same prompts. If the ensemble
separates them, the label "AI detector" is wrong and we can say so with a number. This is the same
shape as the repo's existing headline negative results and costs a day.

Supporting: **StyleShield** ([arXiv:2605.00924](https://arxiv.org/pdf/2605.00924)) — continuous
controllable style transfer exposes detector fragility; **the Feature-Inversion Trap**
([arXiv:2510.12476](https://arxiv.org/pdf/2510.12476), ACL 2026, with **StyloBench**) — features that
separate human from machine **flip sign** under personalization, because training-free detectors assume
human text is more diverse, and personalized machine text breaks that assumption. Inversion, not
degradation. `eval/detector_audit.py` already has an `INVERTED` class for exactly this failure — the
paper says it is a *systematic* regime, not a bug, and StyloBench is the corpus to prove it on.

### 4. EU AI Act Article 50 — a live compliance surface with no auditing tool in it

Article 50 has applied **since 2 August 2026** (a month ago), with the marking-and-detection obligation
for systems already on the market phasing in **2 December 2026**
([Commission FAQ](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act),
[Article 50 text](https://artificialintelligenceact.eu/article/50/),
[practitioner guide](https://www.orrick.com/en/Insights/2026/08/EU-AI-Act-Transparency-Obligations-for-AI-Generated-Content-Article-50)).
Providers of systems generating synthetic text must ensure outputs are **marked in a machine-readable
format and detectable as artificially generated**.

Nobody is auditing whether that marking survives contact with normal use. The evidence says it does
not: **SynthID-Text degrades under paraphrase, copy-paste editing and back-translation**
([arXiv:2508.20228](https://arxiv.org/abs/2508.20228)), and there is a published **layer-inflation
attack** against its mean score ([arXiv:2603.03410](https://arxiv.org/abs/2603.03410), OpenReview).
Compliance gaps in Art. 50 II are themselves now a paper
([arXiv:2603.26983](https://arxiv.org/html/2603.26983v1)).

**We are one adapter away from being the tool for this.** SynthID-Text is open source and shipped in HF
Transformers ([code](https://github.com/google-deepmind/synthid-text),
[docs](https://ai.google.dev/responsible/docs/safeguards/synthid)) with a no-training Weighted Mean
detector. Add `untell/detectors/synthid.py` implementing the existing `base.Detector` interface, and
the repo's whole harness — including `attacks/back_translation.py`, which is already written and is
literally one of the attacks the robustness paper uses — becomes a **watermark-survival audit**. Same
measurement discipline, a legally mandated target, and a market that starts in December.

### 5. Statistical honesty — bootstrap CIs and TPR@1%FPR, because n=30 does not support a point estimate

The methodology critiques are unanimous: **fix and report FPR**; use **TPR@1%FPR as the primary
endpoint** alongside AUROC; report **bootstrap confidence intervals** and macro-averaging
([RAID, ACL 2024](https://aclanthology.org/2024.acl-long.674/);
[arXiv:2603.17522](https://arxiv.org/abs/2603.17522);
[MGTEVAL, arXiv:2604.25152](https://arxiv.org/abs/2604.25152)).

The repo's headline numbers are point estimates on n=30 and n=40. A 17% FPR on n=30 has a 95% Wilson
interval of roughly **7%–35%** — which does not change the argument, but stating it makes the argument
unattackable, and this repo's entire credibility rests on being harder on itself than its critics
would be. `docs/free-ceiling-measured.md` and `references/thresholds.md` should carry intervals on
every rate.

**Also from this strand:** detector scores are unstable across tools on identical text, with reported
ICCs of **0.57–0.95**, and the Weber-Wulff 14-tool study
([IJEI 2023](https://link.springer.com/article/10.1007/s40979-023-00146-z), the field's most-cited
audit) found every tool below 80% accuracy and only five above 70%. Cite it — it is the peer-reviewed
precedent for what untell does, and the repo currently does not reference it.

---

## Datasets: wire in, in this order

| Dataset | What it adds that we lack | Where |
|---|---|---|
| **Beemo** | Human **expert** edits of machine text — external control for the rewrite loop | [HF](https://huggingface.co/datasets/toloka/beemo) / [arXiv:2411.04032](https://arxiv.org/abs/2411.04032) |
| **ARB** | H2L: human text rewritten by an LLM — the false-accusation case | [arXiv:2607.29539](https://arxiv.org/abs/2607.29539) |
| **RealDet** | Multi-domain **human-only** calibration corpus for MCP | [arXiv:2505.05084](https://arxiv.org/abs/2505.05084) |
| **StyloBench** | Personalized/style-imitating machine text — triggers feature inversion | [arXiv:2510.12476](https://arxiv.org/pdf/2510.12476) |
| **DetectRL-X** | 8 languages, 6 domains, commercial LLMs, **and polish/expand/condense ops** | [arXiv:2605.15518](https://arxiv.org/abs/2605.15518), ACL 2026 |
| **M4GT-Bench** | Mixed human-machine **boundary** task | [arXiv:2402.11175](https://arxiv.org/abs/2402.11175) |
| **SHIELD** | Controllable **hardness** parameter for graded difficulty | [arXiv:2507.15286](https://arxiv.org/abs/2507.15286) |

DetectRL-X's *polish / expand / condense* operations deserve their own note: they are AI-**assistance**
operations rather than AI generation, they are what people actually do, and `untell/languages.py`
already exists but has no multilingual evaluation data behind it.

## Methods and arms to add

- **Length-conditioned verdicts.** The literature converges on: ~50 words is the floor for any
  reliability, 100–120 for statistical and fine-tuned methods to reach their potential, ~200 for strong
  LLMs, 300–700 ideal; false negatives cluster around 14 words and false positives around 34
  ([arXiv:2406.15583](https://arxiv.org/pdf/2406.15583) and the ETS writing-assessment work,
  [arXiv:2603.02353](https://arxiv.org/pdf/2603.02353)). **untell should refuse a verdict below a length
  floor and report FPR as a curve over length, not a scalar.** `untell/text_split.py` already has the
  machinery.
- **Homogenization metrics as a first-class capability.** Standard, implementable measures:
  **Vendi Score** (exponential entropy of similarity-matrix eigenvalues), embedding dispersion (mean
  pairwise cosine distance), NLI-contradiction diversity, and the tooling survey in
  [arXiv:2403.00553](https://arxiv.org/html/2403.00553v1) / [emb-diversity](https://arxiv.org/html/2607.19848).
  This is a **new product surface**: measure what a rewrite does to a corpus's diversity, not just to a
  detector's score.
- **The open study we are uniquely placed to run.** StyleShield perturbs *machine* text along a style
  axis. Nobody has done the human-side version: **FPR on genuine human writing as a function of that
  writer's distance from the model's stylistic centroid.** That single curve would explain the L2
  result ([Liang et al., arXiv:2304.02819](https://arxiv.org/abs/2304.02819): 61.3% FPR on non-native
  TOEFL essays, 97.8% flagged by ≥1 detector) mechanistically rather than by correlation, and it would
  cover the neurodivergent-writer case, where — per the sources found — **no peer-reviewed
  quantification exists at all**, only case reports. We have the detectors, the embeddings, and the
  human corpora. It is a paper.
- **Author-role fairness axis.** *Who Writes What: Unveiling the Impact of Author Roles on AI-generated
  Text Detection* ([arXiv:2502.12611](https://arxiv.org/pdf/2502.12611)) and the accuracy-bias
  trade-off study ([PMC12453642](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12453642/)) give the
  framing; **no fairness-audit toolkit exists for text detectors** — AIF360, Aequitas and Fairlearn are
  generic classifier tools and nobody has bridged them to this. That bridge is a differentiator.
- **Adversary-aware counter-detection.** **DAMAGE** ([arXiv:2501.03437](https://arxiv.org/pdf/2501.03437))
  studies 19 humanizer tools and trains a detector that catches humanized text at low FPR; GPTZero and
  Turnitin now ship a humanized/AI-paraphrased class. Ship DAMAGE-style detection as a **holdout arm**,
  the way `eval/holdout.py` uses RADAR: if the loop's output is caught by an adversary-aware detector it
  never saw, that is the honest ceiling, and it belongs in the headline.
- **Unicode attacks have a citation now.** `untell/attacks/unicode_tricks.py` implements what *Bad
  Characters: Imperceptible NLP Attacks* (IEEE S&P 2022) formalised: invisible characters, homoglyphs,
  reordering, deletion — **one injection materially degrades vulnerable models, three functionally break
  most of them.** That is a concrete benchmark for the scrubber to be measured against, and the paper is
  the right citation for the Trojan Source framing already in the README.

## Positioning — read before writing another README claim

- **MGTEVAL** ([arXiv:2604.25152](https://arxiv.org/abs/2604.25152),
  [code](https://github.com/Liyuuuu111/MGT-Eval)) is the nearest neighbour and it is strong: 26
  detectors, 12 attacks, CLI **and** web UI, accuracy/F1/AUROC/TPR@low-FPR, a public site. **We do not
  win on detector count or attack count.** untell's distinct claims are: FPR measured on *real human
  writing* at *vendors' own shipped thresholds*, verdict stability across seeds and paraphrases,
  calibration as an output rather than a benchmark, and being a Claude Code skill anyone can point at
  their own corpus. Say that; drop any implication of being the most comprehensive harness.
- **The demand is now legal, not academic.** In early 2026 an Adelphi University student flagged
  "100% AI" won a ruling calling the finding "without valid basis" and ordering it expunged; a
  University of Minnesota expulsion resting partly on detector evidence was challenged; Washington
  State dropped its tool after an accusation resolved "not responsible" on detector-only evidence
  *(secondary — press and legal-blog sources; verify each before citing)*. Institutions need exactly
  what this repo produces: a defensible measurement of what a verdict is worth on *their* corpus.
- **Humans are not the fallback.** Expert academic reviewers ~70%, Ghostbuster's own student annotators
  59%, ESL teachers 61% (67% after training). "Have a human check it" is not a remedy and the docs
  should say so.

## Claims in this repo to revisit

1. `references/thresholds.md` calls 0.40 "strictly better" on the basis of one corpus. Every number in
   that section is an HC3 number and the file says so in one place but not in the table. With MCP the
   whole table becomes a **calibration procedure** instead of a constant.
2. No confidence intervals anywhere. Add them; the argument survives and gets stronger.
3. The `max` aggregation choice is defended from the closed-loop evasion literature. Fine as a stop
   target — but ARB and Beemo both report at **TPR@1%FPR**, and we should report there too if we want
   the numbers to be comparable to anyone else's.
4. Weber-Wulff (IJEI 2023) is the peer-reviewed precedent for this entire project and is not cited.

## Deliberately not pursued

Retrieval-based defence ([Krishna et al., arXiv:2303.13408](https://arxiv.org/abs/2303.13408) — 80–97%
of paraphrased generations caught at 1% FPR from a 15M-generation database) is the one defence that
genuinely works, and it is out of scope: it requires the *provider* to log every generation, so it is
unavailable for local or open-weight models and cannot be audited from outside. Worth one paragraph in
the docs as the honest counter-case; not worth building.
