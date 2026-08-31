# Research on AI writing — a literature map (as of August 2026)

**Question asked:** what has actually been published on AI writing?

**Scope.** Deliberately wider than [`humanizer-research-report.md`](humanizer-research-report.md), which
covers one slice (detector internals, evasion, the humanizer market). This map covers seven strands:
how much AI-written text exists, what AI does to prose itself, detection, detector fairness, attacks
and watermarking, what happens to the human writer, and how writing quality is now evaluated.

> **Evidence caveat — read this first.** `arxiv.org` is blocked by this environment's egress proxy, so
> the papers below were located and summarised from search indexes and publisher pages, **not** read in
> full. Titles, IDs and venues are reliable; specific numbers are as-reported and should be checked
> against the source before any of them is quoted in the repo's own claims. Where a number comes from a
> blog or vendor page rather than a peer-reviewed or preprint source, it is marked *(secondary)*.

---

## TL;DR

Seven findings recur across independent groups, and they cohere into one story:

1. **AI-assisted writing is now the majority case in at least one corpus.** Biomedical abstracts are the
   best-measured domain and the estimates climb every year.
2. **The effect on prose is convergence, not just volume.** Multiple methods — lexical, stylistic,
   semantic, argumentative — find variance shrinking, in the same direction, across languages.
3. **Detection surveys published in 2026 are notably less confident than the 2023–24 generation.**
4. **The non-native-speaker false-positive result has held up and been extended** to other demographic
   axes.
5. **Detector-guided paraphrase attacks remain unbeaten in the open literature**, and now transfer to
   held-out detectors.
6. **Watermarking has moved from "promising" to "specific attacks published"** — including against
   SynthID-Text.
7. **The human-side literature has converged on ownership and overreliance** as the measurable
   quantities, not "quality".

This is the same conclusion untell's own measurements reach from the other end: a detector verdict is
worth much less than the products selling it imply, and the interesting question is what AI writing does
to writing rather than whether a classifier can spot it.

---

## 1. How much AI-written text is out there

The prevalence literature is the most methodologically mature strand, because it has a natural
identification strategy: measure *excess* vocabulary against a pre-2022 baseline rather than classify
individual documents.

| Study | Corpus | Headline estimate |
|---|---|---|
| Kobak et al., **"Delving into LLM-assisted writing in biomedical publications through excess vocabulary"**, *Science Advances* ([doi](https://www.science.org/doi/10.1126/sciadv.adt3813), [PMC12219543](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12219543/)) | >15M PubMed abstracts, 2010–2024 | **≥13.5%** of 2024 abstracts LLM-processed — a floor, by construction |
| **"Most biomedical publications show signs of LLM-assisted writing"** ([arXiv:2608.10715](https://arxiv.org/html/2608.10715v1)); see also *Nature* news, ["Staggering 90% of biomedical papers now show signs of AI help"](https://www.nature.com/articles/d41586-026-02551-z) | PubMed Central | **~89%** by end of 2025 |
| Liang et al., **"Quantifying large language model usage in scientific papers"**, *Nature Human Behaviour* ([s41562-025-02273-8](https://www.nature.com/articles/s41562-025-02273-8)) | Multi-field abstracts | **22.5%** of CS abstracts vs **7.7%** of maths by Sept 2024 |
| **"The diffusion of large language models in published academic articles"**, *PNAS* ([2605754123](https://www.pnas.org/doi/10.1073/pnas.2605754123)); *Science* [coverage](https://www.science.org/content/article/one-fifth-computer-science-papers-may-include-ai-content) | Published articles | ~one-fifth of CS papers contain AI content |
| **"Estimating the prevalence of LLM-assisted text in scholarly writing"** ([arXiv:2512.01560](https://arxiv.org/pdf/2512.01560)) | 7.3M articles, 2020–2025 | 12% (2023) → **~57%** (2025) |

**The spread from 13.5% to 89% is the finding**, not a flaw. The estimators measure different things —
"any LLM touch" versus "substantially LLM-written" — over different corpora, and none of them can
separate a grammar pass from a ghostwritten paragraph. Section-level breakdowns are consistent across
studies: abstracts, introductions and discussions are far more affected than methods and results.

Adjacent adoption surveys (all self-report, all *(secondary)*): [Gallup/Lumina 2026](https://news.gallup.com/poll/704090/routine-college-students-despite-campus-limits.aspx)
puts 57% of US college students at weekly-or-more AI use in coursework; the [HEPI Student Generative AI
Survey 2026](https://www.hepi.ac.uk/reports/student-generative-ai-survey-2026/) reports ~75% habitual use
in written assessments; [Muck Rack's 2026 State of Journalism](https://www.globenewswire.com/news-release/2026/03/19/3259178/0/en/muck-rack-s-2026-state-of-journalism-report-finds-82-of-journalists-use-ai.html)
reports 82% of 1,044 journalists using at least one AI tool. The measured — rather than self-reported —
counterpart is **"AI use in American newspapers is widespread, uneven, and rarely disclosed"**
([arXiv:2510.18774](https://arxiv.org/pdf/2510.18774)); *rarely disclosed* is the part that matters.

## 2. What AI does to the writing itself

This is the strand that has grown fastest since 2025, and the one with the most convergent evidence.
Four independent measurement families point the same way.

**Linguistic diversity.** **"The Shrinking Landscape of Linguistic Diversity in the Age of Large Language
Models"** ([arXiv:2502.11266](https://arxiv.org/abs/2502.11266); *Nature Human Behaviour*,
[s41562-026-02550-0](https://www.nature.com/articles/s41562-026-02550-0)) — 7 datasets, >880,000 texts —
reports writing-complexity variance down **21–50%**, and finds LLMs amplify patterns associated with
dominant varieties while suppressing others.

**Semantic diversity.** **"The Homogenizing Effect of Large Language Models on Human Expression and
Thought"** ([arXiv:2508.01491](https://arxiv.org/pdf/2508.01491); *Trends in Cognitive Sciences*,
[S1364-6613(26)00003-3](https://www.cell.com/trends/cognitive-sciences/abstract/S1364-6613(26)00003-3))
finds AI assistance can raise the quality of an individual output while cutting variation *across*
people — in college-admissions essays, human writing produced roughly **2–8×** the collective semantic
diversity of base GPT-4 essays.

**Lexical fingerprints.** The *delve*/*underscore*/*intricate* shift is now itself a literature:
[arXiv:2603.18161](https://arxiv.org/pdf/2603.18161) ("How LLMs Distort Our Written Language"),
[arXiv:2508.01930](https://arxiv.org/html/2508.01930v1) (tracing overuse to RLHF), and a cross-lingual
replication in **"AI-Associated Lexical Shifts Across 34 Languages"**
([arXiv:2605.25358](https://arxiv.org/pdf/2605.25358)). A *PNAS* exchange
([Reply to Topaz and Bahl](https://www.pnas.org/doi/abs/10.1073/pnas.2621834123?af=R)) argues over how to
interpret the post-2022 shift — worth reading for the identification problem, which is real.

**Voice and structure.** **"Can We Still Hear the Accent?"**
([arXiv:2604.08568](https://arxiv.org/pdf/2604.08568)) finds detection of native-language signals in
academic text down **>10%** post-LLM — the writer's background being smoothed out. Companion results:
**"Voice Under Revision"** ([arXiv:2604.22142](https://arxiv.org/pdf/2604.22142)) on personal narrative,
**"Narrative Flattening"** ([arXiv:2605.27878](https://arxiv.org/pdf/2605.27878)) on post-training
compressing thematic/affective/stylistic variation in LLM fiction, and **"Argument Collapse: LLMs Flatten
Long-Form Public Debate"** ([arXiv:2606.01736](https://arxiv.org/pdf/2606.01736)).

**Why this matters for detection work specifically:** homogenization and detection are the same
phenomenon viewed from two ends. The signal detectors exploit *is* the flattening — which is exactly why
a detector penalises any writer whose natural prose already sits near the model's centre of mass.

## 3. Detection — the 2026 survey generation

Four 2026 surveys/benchmarks, and they read considerably more sceptically than the 2023–24 wave:

- **"A Comprehensive Survey of Machine-Generated Text Detection"** (Jan 2026) — [ResearchGate](https://www.researchgate.net/publication/399324725_A_Comprehensive_Survey_of_Machine-Generated_Text_Detection)
- **"Human or Machine? A Survey on Machine-Generated Text Detection"** — [ResearchGate](https://www.researchgate.net/publication/401008191_Human_or_Machine_A_Survey_on_Machine-Generated_Text_Detection); notable for cataloguing 2023–2025 corpora and for cross-lingual coverage
- **"Detecting the Machine: A Comprehensive Benchmark of AI-Generated Text Detectors Across Architectures, Domains, and Adversarial Conditions"** ([arXiv:2603.17522](https://arxiv.org/abs/2603.17522), [code](https://github.com/MadsDoodle/Detecting-the-Machine-A-Comprehensive-Benchmark-of-AI-Generated-Text-Detectors-Across-Architectures)) — paired Q/A design, cross-domain and cross-generator transfer, adversarial rewriting; reports a **perplexity polarity inversion** and a **generator–detector identity problem** as distinct failure modes
- **"Why AI-Generated Text Detection Fails: Evidence from Explainable AI Beyond Benchmark Accuracy"** ([arXiv:2603.23146](https://arxiv.org/pdf/2603.23146))

Also: **"AI Generated Text Detection"** ([arXiv:2601.03812](https://arxiv.org/abs/2601.03812)),
**"Diversity Boosts AI-Generated Text Detection"** (TMLR, Feb 2026,
[arXiv:2509.18880](https://arxiv.org/pdf/2509.18880)), **"Show, Don't TELL: Explainable AI-Generated Text
Detection"** ([arXiv:2605.27921](https://arxiv.org/pdf/2605.27921)), and the long-running
[LLM-generated-Text-Detection](https://github.com/junchaoIU/LLM-generated-Text-Detection) reading list.

The theoretical ceiling result — as human and machine text distributions overlap, any detector's AUROC
tends to 0.5 — is covered in untell's own report and traced there to the Ghosal et al. survey
([arXiv:2310.15264](https://arxiv.org/abs/2310.15264)), *not* to Sadasivan et al., which is the usual
mis-citation.

## 4. Fairness and false positives

The single most-replicated result in the field. Liang et al. (2023, *Patterns*;
[arXiv:2304.02819](https://arxiv.org/abs/2304.02819)) found 7 detectors flagged **61.3%** of non-native
TOEFL essays as AI while classifying native-speaker essays near-perfectly; **97.8%** of the human TOEFL
essays were flagged by at least one detector. The mechanism is perplexity: L2 writers use more
predictable vocabulary and simpler structure, which reads as machine-like.

What has changed since:

- Reported extension along other demographic axes — a 2026 ACL study (Pindrop) testing 16 detectors is
  said to find non-White English-language learners flagged disproportionately, with **no detector
  uniformly fair** *(secondary — I could not reach the ACL page to confirm this directly; treat as a lead
  to verify)*.
- Vendors now dispute the result on their own products — Pangram reports **0.00%** FPR on a re-test of
  the TOEFL data, which is a first-party figure, not an independent replication *(secondary)*.
- Independent 2026 tests continue to report L2 writers flagged at roughly **2–3×** the native rate
  *(secondary — blog-grade, small-n)*.

untell's own measurements are the relevant local check on all of this, and they are harsher than most
published FPR figures: the full local ensemble flags 17% of genuine human HC3 answers at shipped
thresholds, one bundled detector flags 6 of 8 human documents, and another flagged 89% before it was
demoted.

## 5. Attacks and watermarking

**Attacks.** Nothing published since untell's earlier survey overturns its conclusion; the 2026 additions
sharpen it.

| Paper | What it establishes |
|---|---|
| **Adversarial Paraphrasing** ([arXiv:2506.07001](https://arxiv.org/abs/2506.07001)) | Training-free, detector-guided paraphrase; broadly effective and *transferable* across detection systems |
| **StealthRL** ([arXiv:2602.08934](https://arxiv.org/html/2602.08934)) | RL paraphrase policy trained against a multi-detector ensemble; transfers to **held-out** detectors |
| **Paraphrasing Attack Resilience of Various AI-Generated Text Detection Methods** ([arXiv:2605.14240](https://arxiv.org/abs/2605.14240)) | Frames the core result as a **performance-vs-resilience dichotomy**: the detectors that score best are not the ones that survive paraphrase |
| **DIPPER** ([arXiv:2303.13408](https://arxiv.org/abs/2303.13408)) | The original controllable-paraphrase result; still the baseline everything is measured against |

That dichotomy is the most useful framing to have entered the literature recently, and it is precisely
what untell's harness measures — leaderboard accuracy and verdict stability under meaning-preserving
edits are different axes, and vendors report only the first.

**Watermarking.** Two 2026 results on Google's SynthID-Text:

- **"On Google's SynthID-Text LLM Watermarking System: Theoretical Analysis and Empirical Validation"**
  ([arXiv:2603.03410](https://arxiv.org/abs/2603.03410), [OpenReview](https://openreview.net/forum?id=4AfWqR3quK))
  — first theoretical analysis; proves the mean score is vulnerable to increased tournament layers and
  builds a **layer-inflation attack**; the Bayesian score is more robust.
- **"Robustness Assessment and Enhancement of Text Watermarking for Google's SynthID"**
  ([arXiv:2508.20228](https://arxiv.org/abs/2508.20228)) — SynthID-Text degrades under paraphrase,
  copy-paste editing and back-translation; proposes SynGuard (semantic + lexical embedding, **+11.1%** F1
  recovery).

Plus **TextSeal** ([arXiv:2605.12456](https://arxiv.org/pdf/2605.12456)) on localized watermarks for
provenance, and [arXiv:2502.11598](https://arxiv.org/pdf/2502.11598) on watermarks against unauthorized
distillation. The overall shape: watermarking is the only provenance approach with a real theoretical
story, and it only ever covers text from a cooperating generator — which is why it does not answer the
question a classroom or an editor actually has.

## 6. The human side — ownership, overreliance, cognition

The most-cited single study is MIT's **"Your Brain on ChatGPT: Accumulation of Cognitive Debt when Using
an AI Assistant for Essay Writing Task"** ([arXiv:2506.08872](https://arxiv.org/abs/2506.08872),
[site](https://www.brainonllm.com/)): 54 participants, 32-electrode EEG, three conditions (LLM / search
engine / brain-only), with a session-4 crossover completed by 18 participants. Findings — weakest brain
connectivity in the LLM group, lowest self-reported ownership, LLM users struggling to quote their own
essays, and the Brain-to-LLM crossover group showing better recall than the LLM-throughout group. **It is
a small, non-peer-reviewed, widely over-cited study**; the honest reading is a real signal about
engagement and ownership, not a demonstration of lasting cognitive harm.

The HCI literature around it is more careful and more useful:

- **"From Use to Oversight: How Mental Models Influence User Behavior and Output in AI Writing
  Assistants"** ([arXiv:2604.05166](https://arxiv.org/abs/2604.05166)) — better system understanding
  raised perceived usability *and* produced more grammatical errors: a backfiring effect
- **"Overreliance in Writing Tasks"** ([arXiv:2605.15322](https://arxiv.org/abs/2605.15322)) — proposes
  similarity-based measures of AI influence plus a reflective-writing interface intervention
- **"From Planning to Revision: How AI Writing Support at Different Stages Alters Ownership"**
  ([arXiv:2604.11009](https://arxiv.org/html/2604.11009v2)) — quality up, ownership down
- **"Process-Oriented Evaluation of AI-Assisted Scientific Writing"**
  ([arXiv:2606.15583](https://arxiv.org/abs/2606.15583)) — experts switch from restructuring to
  substitution when AI authorship is disclosed
- **"Collaborative Document Editing with Multiple Users and AI Agents"** (CHI 2026,
  [10.1145/3772318.3790648](https://dl.acm.org/doi/10.1145/3772318.3790648)) — 30 participants, 14 teams,
  one week: teams folded agents into existing norms of authorship and control rather than treating them
  as members
- **"Quantifying Co-writing with AI across Datasets from the HCI Community"** (CHI 2026 EA,
  [10.1145/3772363.3798711](https://dl.acm.org/doi/full/10.1145/3772363.3798711)) — 115 tools surveyed,
  15 datasets, 32 metrics, almost no standardisation
- **"Co-Writing with AI, on Human Terms"** (PACM HCI, [10.1145/3757566](https://dl.acm.org/doi/10.1145/3757566),
  [arXiv:2504.12488](https://arxiv.org/html/2504.12488v2)) — maps research effort against what users
  actually ask for across the writing process
- **"'It's OK Because…': The Wild West of Student Rationalization of AI Use in Academic Writing"**
  ([arXiv:2605.29090](https://arxiv.org/pdf/2605.29090)) — the norms side of the same question

## 7. How AI writing quality is now evaluated

- **LitBench** ([arXiv:2507.00769](https://arxiv.org/pdf/2507.00769); EACL 2026,
  [2026.eacl-long.362](https://aclanthology.org/2026.eacl-long.362/)) — 2,480 debiased held-out human-labelled
  story comparisons + 43,827 training pairs. Best off-the-shelf judge reached **73%** agreement with
  humans; trained Bradley-Terry and generative reward models **78%**.
- **The Human Creativity Benchmark** ([arXiv:2606.30561](https://arxiv.org/abs/2606.30561v1),
  [Contra Labs](https://contralabs.com/research/human-creativity-benchmark)) — ~15,000 professional
  judgments, and a genuinely useful conceptual move: separating **convergence** (where professionals
  agree on best practice) from **divergence** (where taste legitimately varies).
- **Benchmarking LLM-as-a-Judge for Long-Form Output Evaluation**
  ([arXiv:2606.01629](https://arxiv.org/pdf/2606.01629)).
- **"Can Good Writing Be Generative? Expert-Level AI Writing Emerges through Fine-Tuning on High-Quality
  Books"** ([arXiv:2601.18353](https://arxiv.org/html/2601.18353v1)) — the counterweight to §2: the
  flattening documented there is largely a *post-training* artefact, not an inherent limit.

That last pairing is the most interesting open tension in the field. If flattening is a post-training
artefact, then both the homogenization findings **and** the detectability of AI text are contingent on
current alignment practice — and both could move sharply when that practice changes.

---

## Gaps worth noting

Things repeatedly gestured at but not, as far as this search found, actually done:

1. **No standardised co-writing evaluation.** The CHI 2026 meta-analysis (115 tools, 32 metrics) says so
   explicitly. This is the clearest open opportunity in the human-side literature.
2. **Prevalence estimators are never validated against ground truth.** Every figure in §1 is an
   inference from aggregate vocabulary drift. Nobody has calibrated one against a corpus of known
   provenance.
3. **Detector fairness audits are almost all single-axis** (native vs non-native). The 2026 multi-axis
   work is new and thin.
4. **The performance-vs-resilience dichotomy has no standard reporting format** — which is squarely what
   untell's harness produces, and a reason its measurements are worth publishing in that vocabulary.
5. **Homogenization and detection are not studied together**, despite being two views of one phenomenon.
   A study measuring FPR as a function of a writer's distance from the model's stylistic centre of mass
   would connect §2 and §4 directly, and would explain the L2 result mechanistically rather than by
   correlation.

## Verification status

| Claim class | Status |
|---|---|
| Paper titles, arXiv IDs, venues | Located via search indexes; **not** confirmed by fetching the papers (arxiv.org is egress-blocked here) |
| Numbers from journal/preprint abstracts | As-reported in search snippets; check the source before quoting |
| Items marked *(secondary)* | Blog, vendor or press sources; directional only |
| Liang et al. 2023, DIPPER, Adversarial Paraphrasing, StealthRL | Cross-checked against untell's own prior verified survey |

Anything from this map that lands in untell's public claims should be re-read at source first — the same
standard the repo already applies to its own numbers.
