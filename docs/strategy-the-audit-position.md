# The audit position — the one move that changes the category

**Written 2026-09-01**, with every number in it evidenced in
[`detector-fairness-measured.md`](detector-fairness-measured.md).

Written from a re-run of the census ([131 repos, 13 angles](research-tooling-survey.md))
and from the detection literature as it stands today.

[`what-would-make-this-the-top-repo.md`](what-would-make-this-the-top-repo.md) answered "how do we
win this category" and answered it honestly: we mostly already have, the category is worth 0.3% of
the field's attention, and every remaining lever inside it is either measured-and-dead (beam
search, Result 48), defended-by-nothing (a seventh meaning gate, Result 46), or blocked on a native
speaker. Its closing instruction was **"trust none of this without re-deriving it — a census is a
snapshot of a field that moves."**

Re-derived. The field moved, and it moved in a direction the census could not see, because the
census surveyed humanizers and this repo is not really one.

---

## 1. The census measured one half of a field that has split in two

The 2026-08-05 sweep enumerated repos that *rewrite text to evade detection*. The 2026-09-01 re-run
added an angle it never had, and the angle is populated:

| repo | ★ | what it is |
|---|---|---|
| [`scanaislop/aislop`](https://github.com/scanaislop/aislop) | 589 | 50+ deterministic rules, 10 languages, CI gate, **no LLM at runtime**, MIT |
| [`berelevant-ai/slopless`](https://github.com/berelevant-ai/slopless) | 323 | deterministic textlint rules for **prose** slop in English Markdown |
| [`seyedehsanhadi/sloptrim`](https://github.com/seyedehsanhadi/sloptrim) | 205 | scores every prose file an agent writes; **Python stdlib only, no network, no model** |
| [`Laith0003/ux-skill`](https://github.com/Laith0003/ux-skill) | 65 | 152 deterministic rules, offline, never calls an LLM |
| [`ItsssssJack/SlopMonster`](https://github.com/ItsssssJack/SlopMonster) | 44 | lint for AI tells → rewrite with a rival model → lint again |

That last one is a detector-in-the-loop by another name, built in the open three days before this
was written. And `sloptrim` — stdlib-only, zero-dependency, no model, scoring prose for AI tells —
is a near-description of untell's own lite tier, arrived at independently.

**The field bifurcated.** The same machinery — a tell catalogue, a score, a rewrite — is being
pointed at two opposite goals: *evade a detector* (humanizers) and *improve prose* (slop linters).
The census counted only the first branch, so every segment size it reports ("184 prompt guides",
"our category has 38 repos") describes one half of the picture. That is not a flaw in the census;
it is the boundary it was drawn with.

It matters because **untell is already in both halves and leads with the wrong one.** The README's
own first line calls it a detector-auditing toolkit. Its headline result is a false-positive rate.
Its rewriting loop is explicitly "the probe, not the product". And yet the census placed it in
`rule-based-rewriter` — a category the previous strategy doc correctly measured as worth 0.3% of
the field's attention, with a 413★ ceiling.

We have been benchmarking ourselves against the wrong field.

---

## 2. The category that is actually empty, and has institutional demand

Point the same question at *detector auditing* and the picture inverts.

**The evidence of need is published, large, and getting larger.**

- Liang et al. (2023): AI detectors flagged **61.3%** of non-native TOEFL essays as AI-generated,
  while classifying native-speaker essays nearly perfectly. **97.8%** of TOEFL essays were flagged
  by at least one detector.
- A 2026 ACL study (Pindrop) testing **16 detectors** found non-White English-language learners
  flagged far more often than their peers, and that **no detector was uniformly fair**.
- [arXiv:2603.20254](https://arxiv.org/pdf/2603.20254), Garland 2026 — *AI Detectors Fail Diverse
  Student Populations* — makes the structural argument: in a university there is no single "human
  distribution". Each student writes differently, the assessor does not know the individual
  student's distribution, so the null hypothesis is **composite** and the false positives are
  mathematically unavoidable. Its worked figure: roughly **750 of 10,000** students wrongly flagged.
- Vendors claim the opposite. Turnitin publishes 98%+ accuracy and <1% false-positive rate — on
  internal testing over curated samples.
- Institutions have already moved. The University of Melbourne's guidance states an AI writing
  detection report **is not sufficient evidence** for an allegation on its own. There are named
  false-accusation cases in the press.

So: a consequential decision is being made about individual people, on the output of a tool whose
error rate is disputed by an order of magnitude, and which the literature says fails *unevenly by
who the writer is*.

**The idea is not novel. The instrument is.**

An earlier draft of this document claimed the category was empty. That claim was checked and it is
**wrong**, and the correction is worth more than the original claim:

- **[BAID: A Benchmark for Bias Assessment of AI Detectors](https://arxiv.org/abs/2512.11505)**
  (Basu, Zhang, Raheja; arXiv 2512.11505, Dec 2025; AAAI 2026 workshop,
  [ACL Anthology](https://aclanthology.org/2026.customnlp4u-1.1/)) does exactly bias assessment of
  AI text detectors — 200k+ samples across seven sociolinguistic dimensions (demographics, age,
  grade level, dialect, formality, political leaning, topic), four open-source detectors, and it
  finds consistent disparities. Anyone claiming to have invented this question has not looked.

So the question is being asked in the literature. What is still missing is different, and narrower:

1. **BAID's subgroup text is synthetic.** Its method generates versions of each sample "with
   carefully crafted prompts to preserve the original content while reflecting subgroup-specific
   writing styles". That measures how a detector responds to *an LLM's imitation of how a group
   writes*. ELLIPSE is 3,904 essays actually written by actual English language learners, carrying
   their real demographic and proficiency metadata. Both are legitimate; they answer different
   questions, and only one of them is evidence about real students.
2. **The instrument existed, and this document said it did not.** No code repository for BAID
   was findable — that part holds. The rest of this point used to say that of the 435 census
   repos plus 131 in the re-run, *zero* ship a tool that measures a detector's false-positive
   rate by writer subgroup. **That was false, and it was false about two repositories in the
   sweep it cites.** Both were invisible for the same reason: the census read READMEs, and
   neither repository advertises this in its README. Reading source found them.

   **[`satyamshivam13/AI_Text_Detector`](https://github.com/satyamshivam13/AI_Text_Detector)**
   ships `scripts/fpr_by_population.py`, dated July 2026 and therefore predating this document.
   It runs an analyzer over a human-only corpus so that any flag is a false positive by
   construction; reports the rate **per population with Wilson 95% intervals**; builds its corpus
   from **Liang et al. (2023)** directly — the same TOEFL non-native, US 8th-grade, college
   admission and CS224N essays, plus five HC3 domains; holds GPT-4-polished TOEFL essays out as
   machine-edited and *not* a plain false positive; applies an **n ≥ 30 floor** before comparing;
   and prints worst-served population, best-served population and a disparity ratio, with the
   divide-by-zero case handled. That is this instrument's design, arrived at independently, and
   in one respect a better one: it used Liang's canonical corpus, which this repository did not.
   **That gap is now closed** — `--corpus liang` loads the same five populations, and running the
   analyses that repository does not have on them produced
   [Results 12 and 13](detector-fairness-measured.md): a paired within-writer contrast showing
   GPT-4 polishing makes untell's detector *less* likely to flag an essay (96.7% → 78.0%,
   intervals separate), and a threshold sweep showing the population disparity widening from
   1.65x to 6.93x as the overall error rate falls.

   **`suraj-ranganath/StealthRL`** — the repository this repo's ROADMAP quotes for its evasion
   numbers, cited from the paper and never located until 2026-09-01 — ships
   `stealthrl/rewards/fairness_reward.py`, computing the **ESL-versus-native false-positive-rate
   gap** at a threshold on human-written text, wired into the composite reward as `−w₄·F′` with
   `fairness_weight: 0.2`, commented "Minimize ESL bias". Not an instrument: it shapes an
   evader's training objective and is reported to nobody. But it computes the number.

   **What is actually left of the differentiation**, stated without the inflation:

   - *Subgroups within a corpus, not corpora as subgroups.* `AI_Text_Detector` splits by
     population-of-origin — TOEFL vs 8th grade vs CS224N. This instrument splits by demographic
     attributes recorded *inside* one corpus: ELLIPSE's race/ethnicity, gender, SES and grade,
     ASAP's `ell_status`. Both are legitimate and they answer different questions; only the
     second supports a claim about groups of writers holding genre constant, which is what made
     [the essay-form finding](detector-fairness-measured.md) legible as a confound rather than a
     result.
   - *Four things it does that neither does.* Component ablation at equal power, a threshold
     sweep, saturation detection, and per-subgroup false-NEGATIVE rates for equalised odds. The
     fourth is no longer a capability without data: Liang ships GPT-3 essays on the same prompts
     as its human ones, and running it found that this project's own published "safe" threshold
     catches nothing at all ([Result 15](detector-fairness-measured.md)), and that at 0.50 a
     false-positive gap too small to reach significance sits beside a false-negative gap of 4.10x
     that does. **An FPR-only audit calls that operating point clean.** It is the clearest case
     this project has for why one error rate is not an audit — and it was found by turning the
     instrument on the tool it belongs to.
   - *And one claim this document should stop making.* "A tool a university could point at the
     detector it is about to license" is not shipped **here either**. `audit()` calls
     `untell.scripts.score` and audits untell's own tiers, exactly as `fpr_by_population.py`
     audits its own four analyzers. Neither has a seam for a commercial detector. That is a
     roadmap item, not a differentiator, and it was being quoted as one.

3. **Nobody reports at the detector's own shipped threshold.** Papers report AUROC or curves. The
   number that decides whether a student is accused is the rate at the operating point the vendor
   ships, and that is what this instrument reports.
4. **The generic fairness toolkits are still unconnected.** [Aequitas](https://arxiv.org/pdf/1811.05577),
   IBM AIF360 (70+ metrics) and Microsoft Fairlearn compute exactly the right statistics and none
   is wired to a text detector; they expect a tabular classifier with subgroup columns.
5. **The benchmarks that ship code measure the other thing.** RAID, IMGTB,
   [`kinit-sk/mAO`](https://github.com/kinit-sk/mAO), its group's ACL 2025
   [MultiSocial](https://github.com/kinit-sk/multisocial) benchmark, and Toloka/beemo rank
   detector accuracy or obfuscation strength. Ranking AUROC is not "who does this detector fail,
   and by how much".

6. **And the strongest open detector in the field does not ask either — which is the version of
   this argument that is worth making.** [`pablocaeg/sloptotal`](https://github.com/pablocaeg/sloptotal),
   found by reading the census sweep's own queue on 2026-09-01, runs 23 detection engines entirely on the user's own hardware
   (Binoculars, Fast-DetectGPT, GLTR, log-rank, plus nine neural classifiers), reports AUC 0.974,
   and publishes its harness and raw per-sample results. It even arrives independently at this
   document's central measurement idea: its control corpus is Project Gutenberg prose from
   1532–1915, chosen because a flag there "cannot be anything but an error", and it reports 0 of
   26 flagged. That is real discipline, applied to the right kind of evidence.

   Its corpora are **domains and eras, not writers**. Searched across its source and docs: zero
   occurrences of *subgroup*, *non-native*, *ESL*, *demographic* or *dialect*. It answers "how
   accurate is this detector" with more rigour than most published work and never asks **who it
   fails**.

   Nor is it alone in either respect. The census sweep's entire 93-repo read queue was read at
   source on 2026-09-01 ([the survey](research-tooling-survey.md) has the pass): 34 of the 93 are
   detector- or benchmark-flavoured, including a self-hostable Fast-DetectGPT with
   bring-your-own-**domain** calibration, two multilingual benchmarks from a lab publishing at
   EMNLP and ACL, and a method for detecting human–AI *collaborative* text. Across all 93, the
   number of READMEs mentioning any fairness word at all — bias, fairness, subgroup, demographic,
   dialect, non-native, false positive — is **three**, each in passing; across all 131 repos read
   at source, the number using any algorithmic-fairness vocabulary is **zero**.

   So the gap this document describes is not a gap in the field's competence, and after this
   session's corrections it is not a claim that the work does not exist. **It is a gap in the
   question being asked.** The field has excellent answers to "is this text AI" and no habit of
   asking who its errors land on — and that, stated against the best case rather than an empty
   one, is the whole position.

This document used to rest on "the research exists and the instrument does not". Point 2 retired
that sentence: the instrument exists, someone built a good one first, and the census missed it
because the census read READMEs. **What is left is narrower and still worth having: this
instrument opens the detector up.** Every tool named above — BAID, `fpr_by_population.py`,
Aequitas, RAID — treats the scorer as a black box and reports a rate per group. The next section
is what stops being invisible when you take the scorer apart instead, and it is the one claim in
this document that no other artifact in the sweep can make.

### The literature, searched properly for the first time

Everything above was, until 2026-09-01, built on papers encountered *incidentally* — cited in a
README, or already in this repository. Four papers had URLs in the whole repo. A systematic search
had never been run, and calling that "the research" was a category error this document was making:
what had been surveyed thoroughly was the **software**, 131 repositories read at source. The
literature is a different corpus and it says more than the software does.

| work | what it establishes | what it does to this document |
|---|---|---|
| **[Identifying Bias in Machine-generated Text Detection](https://aclanthology.org/2026.acl-long.109.pdf)** (Pindrop, **ACL 2026 Main**) — 16 detectors against a demographically labelled corpus | English-language learners flagged more, and **non-White ELL students flagged far more than their White peers**. Bias is real, **model-specific**, and worst where attributes intersect; no detector was uniformly fair or unfair | The strongest prior art there is, and a **peer-reviewed main-conference** version of this audit. It also names the mechanism this repo measured independently: non-native writing is **lower-perplexity and lower-burstiness**, which is [Result 14](detector-fairness-measured.md)'s two channels |
| **[AI Detectors Fail Diverse Student Populations](https://arxiv.org/abs/2603.20254)** (Garland, 2026) | Reframes detection as **composite** hypothesis testing: there is no single "human distribution", the null varies per writer and is unknown, so the limits are **structural** rather than a tuning failure | The theory this instrument is the empirical half of. It argues *why* no threshold works; [Result 15](detector-fairness-measured.md) measures a detector for which none does |
| **[The accuracy-bias trade-offs in AI text detection tools](https://doi.org/10.7717/peerj-cs.2953)** (Pratama, *PeerJ CS* 2025; via PubMed, PMID 40989485) — GPTZero, ZeroGPT, DetectGPT on human vs LLM-generated and **LLM-enhanced** abstracts | Accuracy and bias trade off against each other, disproportionately hitting non-native speakers and some disciplines; **the most accurate tool carried the strongest bias** | Independent confirmation of [Result 13](detector-fairness-measured.md) — the aggregate improves while the disparity widens — on different tools and a different corpus. Its LLM-enhanced arm is Results 12 and 18's question |
| **[GPT detectors are biased against non-native English writers](https://doi.org/10.1016/j.patter.2023.100779)** (Liang et al., *Patterns* 2023) | 61.3% mean false-positive rate on 91 TOEFL essays across seven detectors; near-zero on US student essays | Already used — it is the corpus behind Results 12–18. Now cited as the paper, not just the data |
| [Towards Possibilities & Impossibilities of AI-generated Text Detection](https://arxiv.org/abs/2310.15264) · [Contra generative AI detection in higher education](https://arxiv.org/abs/2312.05241) | survey, and the case against detection in assessment | Context for §1's "we cannot win raw evasion" |

**Two of these change what this document may claim.**

First, **the audit exists in the literature at main-conference quality.** BAID was already named
here; ACL 2026 long paper 109 is stronger — 16 detectors, real demographic labels, an
intersectional finding. Combined with the two repositories found in the census sweep that compute
per-population false-positive rates, the honest position is now narrow and stable: *the research
is well established, the measurements have been made by better-resourced groups, and what remains
scarce is a runnable instrument a school can point at a detector.* Nothing in this document should
imply the question is unasked. It is asked, and answered, in venues this repository does not
publish in.

Second, **the strongest finding in that paper was one this instrument could not have produced.**
Pindrop's result is intersectional — the gap appears at *non-White* × *ELL*, and neither axis
shows it alone. `subgroup_audit` reported one axis at a time until 2026-09-01. It now crosses
them (`--by "race_ethnicity*ell_status"`), with the missing-data rule applied to every part so a
row lacking either lands nowhere rather than in a cell named after absent data.

### Who this is actually for — the framing was wrong, and the correction is good news

This document has said throughout that the instrument is "a tool a university could point at the
detector it is about to license". Searched 2026-09-01, that sentence describes a market which is
moving the other way.

**As of August 2026, more than fifty universities across the US, Canada, the UK, Australia and
South Africa have formally banned, disabled, or recommended against AI detection tools** — MIT,
Yale, UCLA, Vanderbilt, the University of Toronto among them. Turnitin publishes a sub-1%
false-positive claim; independent work puts it at 5–20% on native English writing and up to 61% on
non-native, and a 2026 peer-reviewed evaluation on 192 texts reports overall accuracy of 0.61.
Students have begun filing suit over false accusations.

**Read [Vanderbilt's published reasoning](https://www.vanderbilt.edu/brightspace/2023/08/16/guidance-on-ai-detection-and-why-were-disabling-turnitins-ai-detector/)
and it is this document's own argument, made by the customer.** They cite: the arithmetic that
75,000 annual submissions at a claimed 1% false-positive rate is ~750 students wrongly flagged;
bias against non-native English speakers and first-generation students; disproportionate impact on
international students, disciplines with rigid formatting conventions, and writers who received
editing support; and — the line that matters most here — **"no insight into how it works"**.

So the position is not wrong, but the buyer and the transaction were. Three corrections:

1. **The decision is usually whether to use a detector at all, not which one to buy.** An
   instrument that produces local evidence serves that decision in either direction, and the
   institutions making it are already reaching for exactly this evidence class — they are just
   citing other people's studies, on other people's students, because they have no way to run it
   on their own.

2. **"No insight into how it works" is a capability this repository has and almost nobody else
   does.** Component ablation ([Result 14](detector-fairness-measured.md)) opens the scorer: it
   showed one channel flagging 100.0% of non-native TOEFL essays and 0.7% of Stanford CS224N
   essays, with the two halves pulling in opposite directions and partly cancelling in the
   aggregate. A black-box benchmark structurally cannot report that, and it is precisely the
   complaint Vanderbilt raised.

3. **[Result 15](detector-fairness-measured.md) is the same conclusion reached from the other
   end.** Fifty universities concluded from institutional experience that these scores should not
   carry accusations. This instrument concluded from 391 paired essays that its own lite tier is a
   usable ranking signal and not an accusation instrument at any threshold — AUROC 0.8012, and no
   operating point with tolerable error on both sides. The two arguments are independent and they
   agree.

**What that changes about the work.** It stops the strategy resting on a procurement story that
the evidence does not support, and it makes the honest pitch narrower and more defensible: not
"choose better", but *"here is what this detector does to writing like your students', measured
on your corpus, with the mechanism visible and every rate carrying an interval"*. That is useful
to an institution banning a tool, one keeping it under constraints, and one defending either
decision — and it is the same artifact in all three cases.

### What the 2026-09 results changed about this argument

Five results landed after this document was last revised, and three of them move it.

**The strongest evidence here is now about other people's detectors, not ours.**
[Results 21 and 23](detector-fairness-measured.md) read RAID's public leaderboard — 46 real
detectors including GPTZero, RADAR, QuillBot and Binoculars — and found two things that fit
together. Every submission must publish the threshold at which its false-positive rate on human
text is 5%, **per text domain**, and the median detector needs those thresholds to span **0.610 of
its entire score range** across eight domains. Then RAID's own evaluator explains why the
leaderboard looks so good: `run_evaluation(..., per_domain_tuning=True)`. Every published accuracy
figure is earned with a threshold fitted separately per domain, and **no deployed detector swaps
thresholds by document type.** A student submits an essay and gets a score.

So the field's headline numbers are an upper bound achievable only under a calibration step its
users do not have, and the missing step is exactly the one whose absence the threshold spread
measures. That is a stronger claim than anything this repository can make about its own tier, it
concerns tools that actually accuse people, and it needs no API key, no GPU and no gated dataset —
`untell-detector-calibration report` reproduces it in six seconds from a committed snapshot.

**And one finding is directly actionable for an institution.**
[Result 22](detector-fairness-measured.md) shows homoglyph substitution costs the median detector
0.7% accuracy and destroys 14 of 43 — two fall below 5%, one to zero. The defence is Unicode
normalisation before tokenisation, which is one line, and a third of the field has not written it.
An institution evaluating a detector can ask that question directly.

**The self-audit is the credential, and it cost us a result.** [Results 24 and 25](detector-fairness-measured.md)
pointed this instrument at M4 and found *our own* detector scoring German at full confidence while
missing 82.8% of the machine text in it — and the audit module itself reading an abstention as a
wrong answer, which published a false figure for an hour. Both are fixed, both are documented with
the wrong version kept visible, and the detector now abstains on six languages rather than
answering. That is the argument this document has always made, applied inward first: **the useful
thing is not a better score, it is knowing when there is no signal and saying so.**

It also sharpens the pitch in §"Who this is actually for". Vanderbilt's stated complaint was *"no
insight into how it works"*. What this repository can now put in front of an institution is not a
rival score. It is: here is the threshold your candidate detector needs per document type, from its
own authors' numbers; here is whether it survives a character swap; here is what it does to writing
like your students'; and here is what it does when it has nothing to say.

### The one measurement with no better-resourced prior version

Everything else in this document is a narrowing. BAID benchmarks detector bias across seven
dimensions; Pindrop's ACL 2026 paper does 16 detectors against real demographic labels;
`satyamshivam13/AI_Text_Detector` shipped per-population false-positive rates in July 2026;
Garland publishes the institutional auditing protocol itself. Better-resourced groups got there
first on every axis this repository measures.

**Except one.** Searched 2026-09-01: the non-native English bias is quantified — Liang's 61.3%,
replicated repeatedly. The bias against **neurodivergent writers** is not. The literature
describes the mechanism (repeated phrasing, constrained vocabulary, the writing patterns of
autistic, ADHD and dyslexic students reading as machine-like), documents individual cases, and
says plainly that **no peer-reviewed study puts a rate on it.**

[Result 20](detector-fairness-measured.md) puts a rate on it: 1,921 ASAP essays by students
identified as having a disability, flagged **38.3%** against 34.8%, separating at 95%; and
crossed with ELL status, **1.48x** — because this detector's apparent protection for
English-language learners disappears for students with disabilities. Neither single axis shows
that.

**Why this one and not the others.** Not insight. The corpus was already on disk for other
results, the label was already in the file, and the axis was one line of configuration away —
`student_disability_status` simply was not in the default axes, so nobody had asked. The
generalisable point is the uncomfortable one: **the gap in the field was not a hard measurement,
it was an unasked question**, and the same was true here until the default was changed. That is
the whole audit position in one result, and it is also the warning attached to it.

**Its limits are as important as the number.** ASAP records an administrative category —
*identified as having a disability* — which includes physical and sensory disability and misses
every undiagnosed student, so it is a proxy for neurodivergence and not a measurement of it. It is
one detector, and bias is model-specific. And 1.10x on the single axis is small; the intersection
is where it matters. A serious version of this needs a corpus labelled for neurodivergence
specifically, which does not appear to exist publicly — and that, rather than another detector or
another threshold, is the most valuable thing anyone could build next in this area.

### The thing a black-box benchmark structurally cannot report

BAID, RAID, IMGTB and every other benchmark audits a detector as an opaque scorer. Run
`untell-subgroup-audit --ablate` and the picture changes. Each half of `perplexity_burstiness`,
thresholded at its own median so both flag about half the corpus and neither is handicapped by a
lopsided operating point:

| component | low proficiency | high proficiency | worse for | ratio | separate |
|---|---|---|---|---|---|
| vocabulary (predictable words ⇒ AI) | **63.4%** | 40.3% | **low** | 1.57x | yes |
| burstiness (uniform sentences ⇒ AI) | 40.2% | **57.1%** | **high** | 1.42x | yes |

Held-out: 1.59x and 1.35x, same directions, both still separated.

**The two halves of one detector are biased in opposite directions against opposite groups.** In
the combined score they partly cancel, which means **any aggregate fairness number for this
detector understates both of its biases**, and a benchmark that treats the detector as a black box
cannot recover them. Averaging two large opposing biases yields a small number and a false
reassurance.

### A third signal family, and it corrects what I said about the second

An earlier version of this section read the vocabulary term as "reproducing Liang et al.'s
perplexity account exactly". It reproduces the *shape* of that account, but it is not perplexity —
it is the fraction of tokens appearing in a 120-word stoplist. So the account was tested properly,
against a **real** language model: an interpolated bigram LM trained on NLTK's Brown and Reuters
corpora (2,001,501 tokens, 56,424 types), fetched from GitHub, stdlib only, independent of both
essay corpora.

| signal | penalises | ELLIPSE *d* | ASAP *d* |
|---|---|---|---|
| common-word ratio (our "perplexity" proxy) | **low** proficiency / ELL | −0.476 | — |
| burstiness | **high** proficiency / non-ELL | −0.394 | — |
| **true n-gram perplexity** | **high** proficiency / non-ELL | **−0.320** | **−0.491** |

More fluent writers produce more *conventional* English, so a genuine LM finds them more
predictable and assigns them **lower** perplexity — the machine-like end. **Two of the three signal
families penalise the more fluent writer, and the odd one out is our stoplist proxy.**

The consequence for this repository is direct and unflattering: **the lite tier's "perplexity"
channel is anti-correlated with actual perplexity on this population.** It is not a valid stand-in
for the thing it is named after, and any reasoning that treated it as one — including mine, two
sections ago — was reasoning about a stoplist.

Shipped as [`eval/ngram_lm.py`](../eval/ngram_lm.py) / `untell-ngram-lm`, 12 tests, so the check
is repeatable rather than a number somebody once produced:

```bash
untell-ngram-lm train                                  # fetches NLTK corpora, builds the model
untell-ngram-lm score --csv essays.csv --by ell_status # mean log-perplexity per group
```

Its output carries the citation and the limitation in the payload, because a perplexity number
quoted without either is the exact failure this module was built to expose.

**Limitation, and it is real.** The LM is 1961 American English plus newswire, a domain mismatch
with school essays; non-native writing being less predictable to *that* model is partly expected.
A modern in-domain LM could differ, and testing one needs weights this environment's egress policy
blocks. What the result does establish is that the *direction* attributed to "perplexity" in the
earlier decomposition came from the proxy, not from perplexity.

### The bias is in the features, not in our calibration

The obvious objection to all of this is that it is a bug report about one weak stdlib detector.
It is not, and the check is cheap: measure the **raw signals** before any detector touches them.

| signal | low proficiency | high proficiency | Cohen's *d* | held-out *d* |
|---|---|---|---|---|
| sentence-length CV (burstiness) | 0.5214 | 0.4555 | **−0.394** | **−0.363** |
| common-word ratio | 0.6045 | 0.5803 | **−0.476** | **−0.537** |

More proficient learners are measurably **less bursty** and use measurably **fewer common words**,
both replicated on held-out data. Nothing about untell is involved in those numbers — they are
properties of the writing and of the two features.

So the generalisation is not about our implementation: **any detector that treats low
sentence-length variance as machine-like inherits a penalty on writing maturity**, and any
detector that treats predictable vocabulary as machine-like inherits the opposite penalty. A
detector carrying both, weighted differently from ours, lands somewhere else on that line — which
is precisely why the operating point and the component weighting have to be *measured* per
detector rather than assumed.

**Is it an artifact of our formula?** No, and this is the obvious next objection so it was
tested. Five different measures of sentence-length dispersion, on both corpora:

| measure | ELLIPSE (low vs high proficiency) | ASAP (ELL vs non-ELL) |
|---|---|---|
| CV (what we ship) | *d* +0.467 | +0.119 |
| raw standard deviation | +0.568 | +0.306 |
| median absolute deviation | +0.486 | +0.247 |
| normalised entropy | −0.647 * | −0.292 * |
| range / mean | +0.059 | −0.108 |

\* entropy over length proportions is *maximised* by uniformity, so its sign is inverted by
construction and it agrees with the rest.

**Four of five agree, on both corpora, in the same direction**: the more fluent group writes
sentences of less variable length. Only range-over-mean fails, and it is a max-minus-min statistic
dominated by one outlier sentence. So the disparity is a property of the **writing**, not of our
CV formula, and any burstiness signal built on a standard dispersion measure inherits it.

**Scope, stated because it would otherwise be overclaimed.** Burstiness is the feature GPTZero
popularised and still explains publicly, but GPTZero migrated to a deep-learning architecture in
autumn 2023, so none of this is a claim about current GPTZero. It applies to detectors that still
use the heuristic — untell's own lite tier, and much of the open-source tier the census
enumerated. Whether a modern neural detector has learned the same correlation is an open question
this instrument is built to answer and has not yet answered, because the weights need a download
this environment cannot make.

That is the defensible position, and it is narrow enough to be true: *component-level* fairness
auditing of text detectors, on real learner writing, at shipped thresholds, as a runnable tool.
The tool detects the opposed-bias condition itself and says so in its own output rather than
leaving it to be noticed.

---

## 3. The move

> **untell becomes the instrument that answers "who does this detector fail?" — false-positive
> rate by writer subgroup, on public learner corpora, reproducibly, at a detector's own shipped
> threshold.**

Not "does this detector work". **Who does it fail.**

This is one axis added to a measurement the repo already makes. Today `untell-detector-audit`
classifies detectors DEAD / INVERTED / WEAK / OK, and `eval/ceiling.py` reports a pooled
false-positive rate on human writing. The move is to stop pooling.

### Why this is the optimal move and not merely a good one

1. **It is the position we already occupy and fail to claim.** The README leads with detector
   auditing. The rewriting loop is documented as a probe. No repositioning fiction is required —
   only that the artifact match the claim.
2. **Everything needed is already built.** Detector ensemble, shipped thresholds
   (`untell/references/thresholds.md`), false-positive measurement on human writing, the audit
   lanes, `.claude/measurements.jsonl` as a ledger, 9,000+ tests, `--json` everywhere. The delta is
   a corpus loader with subgroup labels plus a group-by on a number already computed.
3. **It wins on the axis the repo can actually win.** ROADMAP §1 rules out raw evasion strength as
   architecturally out of reach without a GPU. Correctness, measurement and honesty is the stated
   opening. This is the sharpest available expression of it, and unlike beam search it has not been
   measured to death.
4. **It converts the headline negative result from a liability into the product.** "The loop moves
   detectors it optimises against and does not move one it has never seen" is a *finding about
   detectors*. In a humanizer that is an admission of failure. In an auditing instrument it is
   exactly the kind of result the instrument exists to produce.
5. **The demand is institutional, not hobbyist.** A university deciding whether to license a
   detector, a student contesting an allegation, and a vendor defending a fairness claim all need
   the same artifact: a reproducible per-subgroup false-positive number computed at the detector's
   own threshold. The previous strategy doc showed stars do not follow engineering in the humanizer
   category. This is a different audience, which does not pay in stars and does pay in citation and
   adoption by people who must justify a decision.
6. **It is defensible against the thing that killed the last position.** `Vladimir-Human/humanizer-ru`
   (120★, found in the re-run) already ships a detectability-delta-before/after axis *with
   false-positive control*, 193 tests, a PyPI package. The "measured and tested humanizer" position
   is no longer empty. The audit position still is.

### The asset that makes it buildable today

[`scrosseye/ELLIPSE-Corpus`](https://github.com/scrosseye/ELLIPSE-Corpus) — the English Language
Learner Insight, Proficiency and Skills Evaluation corpus (Crossley et al. 2023, *IJLCR* 9(2)
248–269).

- **~6,500 essays** by English language learners, written under state-wide standardized testing.
- Per-essay **subgroup metadata: race/ethnicity, gender, economic status, grade level (8–12)**.
- Per-essay **proficiency scores**: overall, plus cohesion, syntax, vocabulary, phraseology,
  grammar, conventions — so results can be reported against proficiency, not just demography.
- Known-human by construction. That is the whole requirement for a false-positive measurement: every
  flag is by definition an error.
- Hosted on **GitHub**, which is reachable even from a restricted remote session.

**License, and it is a real constraint: CC BY-NC-SA 4.0.** Non-commercial, share-alike, attribution.
untell is MIT. The corpus therefore **must not be vendored into this repository** — that would
relicense the package. The correct shape is the one `eval/datasets.py` already uses for HC3, RAID
and MAGE: a loader that fetches on demand under an extra, with the citation and licence printed at
load time, and the data never committed.

---

## 4. What this does not fix, stated before anyone else says it

- **It does not make untell a better humanizer.** Nothing here narrows the gap to per-token
  detector-guided decoding. That gap is still architectural and still needs a GPU.
- **It will not move the star count.** The previous doc's data is unchanged: 92% of this field's
  stars sit on prompt guides. An audit instrument is if anything *less* starrable. Anyone
  approving this work should expect citation and institutional use, not a chart.
- **One corpus is not a population.** ELLIPSE is US school-age learners under standardized testing
  conditions. A false-positive disparity measured there does not license a claim about TOEFL
  candidates, professional writers, or any other language. The honest headline is bounded by the
  corpus, exactly as every other number in this repo is.
- **Subgroup labels invite over-claiming, and this is the failure mode to fear.** Reporting "this
  detector flags group X at N×" is a strong claim about a real population of people. It needs
  confidence intervals, a minimum group size, and a refusal to report a rate for a group too small
  to support one. A repo that ships that carelessly does more harm than the detectors it audits.
  This is the single most important engineering constraint in the whole proposal.
- **It cannot settle a specific accusation.** A per-group rate is evidence about a *detector*, never
  about a *document*. The tool must say so in its own output, or it will be misused in exactly the
  way its existence is meant to prevent.

---

## 5. First step — done, and it found something

Built and run on 2026-09-01, before this document was committed, because a strategy whose first
step has not been tried is a guess.

- **`eval/datasets.py: load_labelled()`** — fetches ELLIPSE on demand, caches outside the tree,
  prints the CC BY-NC-SA licence and the Crossley et al. citation at load. Nothing vendored.
- **`eval/subgroup_audit.py`** — false-positive rate by subgroup, Wilson intervals, a `MIN_GROUP`
  floor of 30 below which a group gets a count and no rate, and a threshold `--sweep`.
- **`tests/test_subgroup_audit.py`** — 34 tests, all on the ways the module could overstate.
- One row in `.claude/measurements.jsonl`, recipe `ellipse-subgroup-fpr`.

### The result

3,904 known-human essays. Every flag is an error by construction.

| threshold | false-positive rate | 95% CI | state |
|---|---|---|---|
| **0.30 — untell's shipped lite default** | **97.4%** | 96.9–97.9% | saturated |
| 0.50 | 38.7% | 37.2–40.2% | measurable |
| 0.70 | 3.2% | 2.7–3.8% | measurable |
| 0.80 | 0.8% | 0.6–1.1% | saturated low |

**Finding 1 — about us, not about them.** untell's own lite tier flags **97.4% of known-human
English-language-learner essays** at the threshold it ships with. The documented lite figure is
**30% on conversational prose**. On school-age ESL writing it is 97.4%. The lite tier is not a
weak detector on this population; it is a detector that says yes to everyone, and the repo has
been shipping it with a threshold tuned on a corpus that does not resemble the writers most likely
to be accused. That is exactly the class of finding this repository exists to produce, and it was
produced by the first run of the first tool built under this strategy.

**Finding 2 — the axis that separates, replicated on held-out data.** Race, gender, economic
status and grade produced no separated disparity: point estimates 1.00x–1.66x, every Wilson
interval overlapping. **English proficiency does separate.** Banding low (≤2.5) against high
(≥3.5) proficiency at the 0.50 operating point, on the training split and then on the 2,571-essay
held-out split that had never been scored:

| split | low proficiency | high proficiency | ratio | intervals separate |
|---|---|---|---|---|
| train (n=2,519 banded) | 33.2% | **44.2%** | 1.33x | yes |
| **held-out (n=1,618 banded)** | 34.8% | **43.0%** | 1.24x | **yes** |

Overall false-positive rate was 38.7% on *both* splits. **The better a learner's English, the more
likely our lite tier calls their writing machine-generated** — and that holds on data the finding
was not derived from.

**What did *not* replicate, stated because it was in an earlier draft of this document.** The
first run reported a *monotonic* rise across all six proficiency levels (33.7% → 53.1%, 1.57x).
On held-out data the ordering is not monotonic and the top level alone (4.5, n=55) does not
separate. The six-level monotonic version was an artifact of the larger split's sample sizes. The
banded contrast above is the claim the data actually supports, and it is the one that survived.

**The mechanism, measured rather than guessed.** The lite tier is one detector,
`perplexity_burstiness`, and it combines two stdlib proxies: a common-word ratio standing in for
perplexity (high ⇒ predictable ⇒ AI-like) and the coefficient of variation of sentence lengths
standing in for burstiness (**low** ⇒ uniform ⇒ AI-like). Decomposed across the same 3,904 essays,
the two halves pull in **opposite directions**:

| rated proficiency | 2 | 2.5 | 3 | 3.5 | 4 | 4.5 |
|---|---|---|---|---|---|---|
| common-word ratio (high ⇒ AI-like) | 0.606 | 0.605 | 0.601 | 0.585 | 0.579 | **0.563** |
| burstiness CV (**low** ⇒ AI-like) | 0.519 | 0.519 | 0.498 | 0.465 | 0.451 | **0.416** |
| mean length (words) | 354 | 394 | 421 | 457 | 488 | 533 |

Both fall monotonically with proficiency. The vocabulary term therefore *protects* stronger
writers — richer word choice reads as more human, exactly as the perplexity account in the
literature predicts. **The burstiness term overwhelms it.** More proficient learners write in
more evenly-measured sentences, and evenness is what the burstiness half is built to punish.

So this is not a counterexample to the perplexity story; it is a decomposition of it. Liang et
al.'s account is visible here in the vocabulary axis and points the way they say. The disparity
comes from the *other* half of the same detector, and it points the opposite way and wins. **The
burstiness term penalises writing maturity**, and any detector carrying one should be assumed to
do the same until measured.

An earlier draft of this section asserted the lite tier was "tells-keyed, not perplexity-keyed"
and explained the result that way. That was wrong — the detector is named `perplexity_burstiness`
and is exactly what it says. The table above is what replaced the guess.

**Finding 3 — the disparity reverses with the threshold.** At 0.70 the ordering is no longer
monotonic and the worst group flips to the *lowest* proficiency (6.2% vs 1.9%, ratio 3.25x, also
separated). So which students a detector wrongly accuses is not a fixed property of the detector:
it is a function of the operating point somebody chose, often without knowing that is what they
were choosing. A single-threshold audit would have reported one of these two directions and
never seen the other. This is the strongest argument in the document for why `--sweep` is not a
convenience feature.

**Finding 4 — no demographic axis separated *in ELLIPSE*, and a second corpus explains why.** On
race, gender, economic status and grade, no ratio separated at 95% in ELLIPSE. That is the
expected shape for that corpus: 71% of its writers are Hispanic/Latino and *all* of them are
English language learners, so it is close to demographically homogeneous and cannot compare
learners to anyone but each other.

**Finding 5 — the independent corpus, and it separates on everything.** [ASAP 2.0](https://github.com/scrosseye/ASAP_2.0)
(Crossley et al., **CC BY 4.0**, hosted on GitHub) is 17,307 source-based essays — a different
writing task, a different sample, 4.4x the size, demographically diverse, and it carries
`ell_status`, the native-versus-learner contrast ELLIPSE structurally cannot provide. At the same
0.50 operating point, overall false-positive rate 31.6%:

| axis | flagged more | flagged less | ratio | separate |
|---|---|---|---|---|
| **ELL status** | **non-ELL 32.2%** (n=14,798) | ELL 26.7% (n=2,269) | 1.21x | yes |
| economic status | **not disadvantaged 38.1%** | disadvantaged 33.7% | 1.13x | yes |
| race/ethnicity | White 33.1% (n=6,989) | Asian/Pacific Islander 23.4% | 1.41x | yes |
| disability | **identified 38.3%** | not identified 34.8% | 1.10x | yes |

**All four separate at 95%.** And the first row is the one that matters: **non-native English
speakers are flagged *less* than native ones** — the reverse of the finding that made detector
bias a public issue.

This is not a refutation of Liang et al. They tested commercial detectors on TOEFL essays and
found 61% false positives on non-native writing. This is a burstiness-weighted heuristic, a
different class of tool, and it carries the **opposite** bias. Three of the four axes point the
same way once you read them together — the more fluent or more advantaged writer is flagged more
— which is exactly what the burstiness mechanism predicts, now shown on two independent corpora.
Disability is the exception and points the other way.

**And the largest gap found is not between demographic groups at all.** At one threshold the
same detector scores 1.4–3.8% on published professional prose (Gutenberg, Brown, Reuters) and
31.6–39.1% on student writing — roughly **tenfold**, an order of magnitude beyond any subgroup
disparity in this work. A detector validated on edited professional text will look excellent and
then fail on students, who are the population it is deployed against. Confounded by genre,
editing and task, and reported that way — but it means **any published false-positive rate that
does not name its population is uninformative about the students it will judge.**

**And it is not editing, nor adulthood — it is the essay form.** Unedited adult writing (forum
posts 2.5%, wine reviews 0.0% at 0.30) scores better than *edited* professional prose (42.6%).
The gradient runs informal adult < consumer reviews < formal published essays < student essays,
which is exactly what a burstiness-weighted detector predicts: a formal assigned essay is the
most structurally uniform text a person produces. **The detector penalises the essay form, and
the essay is the artifact students are required to produce and be judged on.**

**A third corpus made this sharper still.** PELIC — adult university ESL, 20+ first languages
— shows the false-positive rate varying by the writer's **first language** (Arabic 40.9% vs
Turkish 29.7%, 1.38x, separated), and shows the proficiency effect running the *opposite* way to
ELLIPSE's. Same detector, same kind of subgroup, opposite direction, because the population and
the task differ. Disparity direction is not a property of a detector at all — it is a property of
a detector *applied to a population*.

**The practical consequence is the point of the whole instrument.** "Detectors are biased against
non-native speakers" is true of the tools that were measured and false of this one, and nobody can
tell which they have without measuring. A published bias direction does not transfer across
detector classes, so it has to be measured per detector — which is the argument for shipping a
tool rather than citing a paper.

**Two defects in the instrument surfaced doing this, and both are now pinned by tests.** ASAP
codes missing demography as the string `"NA"`; 4,019 rows carried it, they scored 19.1% where
every real group scored 30–38%, and the tool made that the "best" group and reported a 2.01x
disparity against a data-collection artifact. And a `--csv` label filter silently dropped
`ell_status`, rendering an empty axis — a heading with nothing under it, which reads as "no
disparity here". Both were found only by pointing the tool at a corpus it was not built around.

**The methodological finding that makes the tool worth having.** At 0.30 the detector flags
everyone, so it cannot discriminate between groups — a disparity ratio computed there is not "no
bias found", it is "this measurement had no room to find any". A naive implementation would have
reported `race_ethnicity = 1.04x, no disparity` and been badly wrong about what it had shown.
`saturation()` detects both ends and `--sweep` finds the operating band where a comparison means
anything. This is the part a fairness toolkit bolted onto a detector would not have got right,
and it is the reason this belongs in a repo that already knows how to measure its own limits.

### What it cost

Two files, one loader, 28 tests, and 45 seconds of CPU for the full corpus. No GPU, no key, no new
dependency. The instrument the previous strategy doc could not find inside the humanizer category
was one group-by away in the auditing one.

## 6. What this replaces

Nothing in the ROADMAP is cancelled. But the framing changes for two open items:

- **Item 13, the per-language catalogues**, is currently blocked on native speakers because a
  *rewriter* needs a tell catalogue. An *auditor* does not: measuring a detector's false-positive
  rate on Korean or Spanish human writing needs a corpus and a threshold, not a catalogue. The
  audit position unblocks the multilingual claim that the rewriter position could not reach.
- **Items 15–17, the GPU work**, were the only path to competing on evasion. They stay blocked and
  stay optional. Under this framing they are no longer the critical path to anything.

The one-line version, if only one line survives:

> The 435-repo census measured whether untell is the best humanizer. It is roughly the best in a
> category worth 0.3% of the field. Nobody has measured whether it is the best detector auditor,
> because nobody else is building one — and that is the question the literature, the institutions,
> and this repo's own README are all already asking.
