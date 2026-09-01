# What the literature gives us that we can actually use

Companion to [`ai-writing-research.md`](https://github.com/ssamba1/untell/blob/main/ai-writing-research.md) (what has been published) and
[`humanizer-research-report.md`](https://github.com/ssamba1/untell/blob/main/humanizer-research-report.md) (evasion and the humanizer
market). **This document is only the intersection: findings that translate into a dataset, a metric, a
module, or a claim this repo can ship.** Everything else was left in the map.

Ranked by what it buys us over effort. **Everything here has since been verified as far as the
environment allows — the audit trail, the tiers and the corrections are in
[`research-verification.md`](research-verification.md).** PubMed/PMC and github.com are reachable and
were read directly; arXiv, ACL, Nature, Science, Springer and HuggingFace are blocked by organization
egress policy. Items marked ✅ were read at source.

---

## The six that matter

### 1. Conformal FPR control — turns the repo's negative result into a constructive one

✅ **Read at source** ([2025.acl-long.601](https://aclanthology.org/2025.acl-long.601/); Zhu, Ren, Cao,
Lin, Fang, Li) — *Reliably Bounding False Positives: A Zero-Shot MGT Detection Framework via
Multiscaled Conformal Prediction (MCP)*. Conformal prediction bounds the FPR from a human-only
calibration set; the paper's own framing is that "most existing detection methods focus excessively
on detection accuracy, often neglecting the societal risks posed by high false positive rates", and
that plain CP constrains FPR but "leads to a significant reduction in detection performance" — MCP
exists to recover it. It ships **RealDet** as the calibration corpus.

> ✗ Two details this document previously asserted are **not in the published abstract**: that the
> quantiles are *length-conditioned*, and RealDet's 15-domain / 22-LLM / 847k-text dimensions. Both
> came from secondary summaries and are now Tier B. Build against the paper.

This is the single most valuable thing found. Right now untell says *your detector's shipped threshold
produces a 17%/40%/89% false-positive rate*. MCP is the answer to the obvious next question — **"then
what threshold should I use?"** — and it answers it with a bound rather than a tuned number.

It also lands directly on a finding the repo already has and currently reports as a wart:
`docs/../untell/references/thresholds.md` documents that lite and full tiers diverge with document
length, and that a single `threshold` doing double duty as stop target and verdict bar is the source of
the 52% → 18% cut. MCP's conformal quantiles are the principled version of the `verdict_threshold`
split that was arrived at empirically — and if they are also **length-conditioned**, as secondary
summaries claim but the published abstract does not say (⚠️ Tier B, see the correction above), that
maps onto the length divergence exactly. The bound does not depend on it.

**Build:** `untell/calibrate.py` — fit quantiles from a human-only calibration set at a user-chosen α,
emit a per-detector, per-length-bucket threshold table; `score_text` gains a `calibrated_verdict`
alongside the existing two. Wire `eval/` to report *both* the vendor threshold and the α-calibrated one
so the gap between them is the headline number.

### 2. Beemo and ARB — the two datasets that test what we actually claim

The repo has HC3, RAID and MAGE (`eval/datasets.py`). All three are **human vs. fully machine**. The
question untell exists to ask — does a verdict survive meaning-preserving editing — has no ground-truth
dataset wired in, only the repo's own rewriter, which is in-sample by construction.

- **Beemo** ([2025.naacl-long.357](https://aclanthology.org/2025.naacl-long.357/), formerly arXiv:2411.04032,
  [HF](https://huggingface.co/datasets/toloka/beemo), [code](https://github.com/Toloka/beemo)) — 6.5k
  human / machine texts from ten instruction-tuned LLMs **edited by expert annotators**, plus 13.1k
  LLM-edited, 19.6k total — ✅ composition confirmed on the authors' repo, including the GPT-4o /
  Llama-3.1-70B editor models and a 20–40% edit budget. Benchmarked over **11 detectors in 33
  configurations**. Their headline: **expert editing evades detection, LLM editing does not**. That is an external, human-produced control for the
  exact transformation untell's loop performs — and it means the repo can finally separate "our
  rewriter moves the score" from "meaning-preserving editing moves the score".
- **ARB** ([arXiv:2607.29539](https://arxiv.org/abs/2607.29539)) — 1,800 human sources × four matched
  variants: HUMAN, Free-LLM, **H2L (LLM-rewritten human text)**, LLM2L. Evaluated at TPR@1%FPR across
  five detectors including Binoculars and RADAR, both of which we ship.

**H2L is the false-accusation case and we have no data for it.** A human writes it, an LLM polishes
it — the single most common real-world configuration, and the one every disciplinary hearing is
actually about.

> ✗ **Correction to an earlier draft**, which said nobody publishes what detectors do to H2L text.
> Wrong. Pratama (*PeerJ CS*, ✅ read at source, [DOI](https://doi.org/10.7717/peerj-cs.2953)) ran
> exactly that experiment with per-subgroup over- and under-detection rates, and Karr, Khvatskii, Hua
> & Chawla (Notre Dame, **ACM AILS '26** — peer-reviewed;
> [arXiv:2608.11256](https://arxiv.org/abs/2608.11256)) put light "refine abstract only" edits at
> **64–80% flagged by Pangram and 38–49% by GPTZero** against **9–15%** for unmodified originals —
> while **>96% of humanized rewrites evade both**. ARB's value is scale, matched design
> and a strict operating point — not primacy. **The gap is in our corpora, not in the literature**,
> which is a smaller claim and a true one.

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

### 6. The AI-assisted arm, FAR/MFAR, and per-subgroup stratification — the shape of the product

This item did not exist before the sources were read. It is now the one that most changes what
untell *outputs*, and every part of it is ✅ Tier A.

**The finding that reorders everything.** In Pratama (*PeerJ CS*,
[DOI](https://doi.org/10.7717/peerj-cs.2953)), GPTZero scored **97.22% accuracy at 0.00% FPR** on
clean human-vs-AI — and was then the *most biased* of three tools on **AI-assisted** text, against
non-native authors (Welch's t = −2.115, p = 0.036), over-detecting **25%** of non-native authors
versus **11%** of native ones. **A detector can be perfect on the benchmark everyone runs and unfair
on the only case that matters.** An audit that stops at human-vs-AI — which is every audit, ours
included — cannot see this.

**Two metrics with published names, which we should adopt verbatim rather than invent:**

- **FAR — False Accusation Rate:** share of genuine human documents flagged by **at least one** tool.
  Measured at **44.44%**. This is exactly what untell's `max` aggregation computes, and there is now
  a citation and a precedent for it.
- **MFAR — Majority False Accusation Rate:** flagged by a **majority** of tools. Measured at **4.17%**.

Reporting both turns "which detector is wrong" into "how exposed is a writer facing this stack",
which is the question an institution actually has.

**Stratification is the product.** The literature already specifies the protocol — assemble human
corpora stratified by observable subgroup (first language, programme, year, task type), run the
detector per stratum, record per-subgroup FPR — **and nobody ships it.** That is the gap, and it is
squarely in untell's shape: point it at your own corpus, get FAR/MFAR per subgroup at both the
vendor threshold and a calibrated one.

**Two more free measurements the same source hands us.** Which assistant polished the text moved risk
more than who wrote it (Gemini-2.0-Pro-enhanced abstracts scored **55.50%** mean AI at GPTZero versus
**19.79%** for ChatGPT-o1, t = −5.97, p < 0.001) — so "which tool did you use" belongs in the report.
And ZeroGPT flagged text at scores **below 30%** while others use 50%: vendor thresholds are not even
internally consistent, which is the calibration argument making itself.

**Prior art to cite, not reinvent:** [FPRCal](https://github.com/cisco-ai-defense/fpr-model-calibration)
(Cisco AI Defense) already calibrates detector scores to a fixed-FPR scale as a scikit-learn pipeline
fitted on benign scores. Security domain, not text detection — the application is open, the technique
is not ours.

**Free corpus:** Pratama's abstracts, per-tool scores and analysis code are **MIT-licensed** at
[github.com/ahmadrpratama/ai-text-detection-bias](https://github.com/ahmadrpratama/ai-text-detection-bias)
— 72 abstracts, 36 native / 36 non-native, in original / AI-generated / AI-assisted form. Small, but
it is a ready-made fairness corpus with ground truth and a permissive licence.

## Datasets: wire in, in this order

| Dataset | What it adds that we lack | Where |
|---|---|---|
| **Beemo** | Human **expert** edits of machine text — external control for the rewrite loop | [HF](https://huggingface.co/datasets/toloka/beemo) / [2025.naacl-long.357](https://aclanthology.org/2025.naacl-long.357/) |
| **ARB** | H2L: human text rewritten by an LLM — the false-accusation case | [arXiv:2607.29539](https://arxiv.org/abs/2607.29539) |
| **Resume corpus (LREC 2026)** | **The assisted arm with a public three-way label**: 420 resumes marked authentic / AI-enhanced / fully AI-generated, five IT job descriptions, authentic ones anonymised. Commercial detectors do badly on it — Originality 55.7% accuracy, Writer 25.0% | [2026.lrec-1.581](https://aclanthology.org/2026.lrec-1.581/) |
| **SenDetEX benchmark** | Sentence-level detection on human-AI hybrid text where the two alternate irregularly — the case our length-conditioned curve says is hardest | [2025.emnlp-main.268](https://aclanthology.org/2025.emnlp-main.268/) |
| **RealDet** ⚠️ Tier B | Calibration corpus: 15 domains, 22 LLMs, 847k+ texts, 113k+ human-written, EN+ZH, plus adversarial paraphrase/edit variants — **none of these dimensions appear in the published abstract**, so they are unverified at source | [arXiv:2505.05084](https://arxiv.org/abs/2505.05084) |
| **StyloBench** | Personalized/style-imitating machine text — triggers feature inversion | [arXiv:2510.12476](https://arxiv.org/pdf/2510.12476) |
| **DetectRL-X** | 8 languages, 6 domains, commercial LLMs, **and polish/expand/condense ops** | [arXiv:2605.15518](https://arxiv.org/abs/2605.15518), ACL 2026 |
| **M4GT-Bench** | Mixed human-machine **boundary** task | [arXiv:2402.11175](https://arxiv.org/abs/2402.11175) |
| **SHIELD** | Controllable **hardness** parameter for graded difficulty | [arXiv:2507.15286](https://arxiv.org/abs/2507.15286) |
| ✅ **APT-Eval** | **15K samples graded by degree of AI polishing**, 12 detectors — the H2L axis, refereed | [2025.findings-acl.1303](https://aclanthology.org/2025.findings-acl.1303/) |
| ✅ **MixSet** | First dedicated mixed corpus: AI-revised human text *and* human-revised machine text | [2024.findings-naacl.29](https://aclanthology.org/2024.findings-naacl.29/) |
| ✅ **FAIDSet** | Multilingual/multi-domain human / LLM / **collaborative**, plus generator family | [2026.eacl-long.151](https://aclanthology.org/2026.eacl-long.151/) |
| ✅ **HERO split** | human / generated / **polished** / translated, length-robust by construction | [2025.findings-emnlp.812](https://aclanthology.org/2025.findings-emnlp.812/) |
| ✅ **CoCoNUTS** | 315,535 peer reviews, six human–AI collaboration modes | [2026.acl-long.1240](https://aclanthology.org/2026.acl-long.1240/) |
| ✅ **ICNALE bias study** | Gender, CEFR proficiency, academic field, language environment; ANOVA + WLS | [2025.acl-long.1292](https://aclanthology.org/2025.acl-long.1292/) |

**Prefer the ✅ rows.** They are refereed, public, and graded by *degree* of AI involvement, which is
the axis untell actually measures. A systematic pass over 38,231 ACL abstracts found them; the first
draft of this document reached for arXiv preprints because it had only searched, not read.

DetectRL-X's *polish / expand / condense* operations deserve their own note: they are AI-**assistance**
operations rather than AI generation, they are what people actually do, and `untell/languages.py`
already exists but has no multilingual evaluation data behind it.

## Methods and arms to add

- ✅ **Length-conditioned verdicts — now measured, not just recommended.**
  `python -m eval.pre_llm_fpr --by-length` scores pre-LLM abstracts truncated to each band. On 90 of
  them at lite tier: **30.0% flagged at ≤50 words (CI 22.5–38.7%)**, **21.7% at 50–100
  (CI 15.2–29.8%)**, 18.5% at 100–200. The 200+ band reads 13.3% on n=15 with a CI to **37.9%** — the
  interval discipline paying for itself immediately, since that row would otherwise be quoted as
  "no false positives". The floor is real and sits where the literature puts it.
- **The evidence behind those bands.** The literature converges on: ~50 words is the floor for any
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
- **The open study, stated accurately this time.** ✗ An earlier draft claimed nobody had connected
  stylistic distance to false-positive rate. Reading the sources killed that: ✅ Liang et al. ran the
  *intervention*, in both directions, in 2023 — enriching the vocabulary of non-native essays cut the
  average FPR from **61.3% to 11.6%**, and simplifying native essays *raised* misclassification — and
  Karr et al. tie detector scores to long-token and Academic Word List density. The axis is
  established causally, not by correlation. Their asymmetry is the frame for everything here:
  **detectors flag legitimate light editing at 64–80% (Pangram) and 38–49% (GPTZero) while letting
  >96% of deliberately humanized text through** — hardest on the people not cheating.
  **What is actually open is narrower and more useful:** a *continuous, centroid-referenced* distance
  measure — embed a corpus, locate the model's stylistic centroid, plot FPR against each writer's
  distance from it — computed **per subgroup**, with modern detectors, at a calibrated operating point.
  That turns a two-point intervention into a dose-response curve an institution can act on. It also
  covers the neurodivergent case, where **no peer-reviewed quantification exists at all** — checked
  from three directions, and the sources actively warn that circulating figures trace to no study.
- **Author-role fairness axis.** *Who Writes What: Unveiling the Impact of Author Roles on AI-generated
  Text Detection* ([2025.acl-long.1292](https://aclanthology.org/2025.acl-long.1292/)) and the accuracy-bias
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
  [code](https://github.com/Liyuuuu111/MGT-Eval)) is the nearest neighbour and it is **stronger than
  the first draft of this document credited**. ✅ Read at source, its repo advertises **25+ detectors**
  and **12+ attack families** — including a **humanization** family — and it already reports
  **bootstrap CIs, ECE, Brier, risk-coverage and TPR@FPR**, with CLI and web UI. **We do not win on
  detector count, attack count, or statistical reporting.** untell's distinct claims are: FPR measured on *real human
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
