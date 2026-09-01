# The audit position — the one move that changes the category

**Written 2026-09-01**, from a re-run of the census ([131 repos, 13 angles](research-tooling-survey.md))
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

**The tooling for that question does not exist.**

- Of the 435 repos the census read, and the 131 in the re-run, **zero** measure a detector's
  false-positive rate by writer subgroup.
- Generic fairness toolkits do exist and are mature — [Aequitas](https://arxiv.org/pdf/1811.05577),
  IBM AIF360 (70+ metrics), Microsoft Fairlearn. All three compute exactly the right statistics:
  false-positive-rate parity across population subgroups. **None of them is wired to an AI-text
  detector**, because they expect a tabular classifier with subgroup columns, and nobody has
  connected the two.
- The benchmarks that do exist measure the opposite thing. RAID, IMGTB, [`kinit-sk/mAO`](https://github.com/kinit-sk/mAO),
  Toloka/beemo all rank *detector accuracy* or *obfuscation strength*. Ranking a detector's AUROC
  is not the same question as "who does this detector fail, and by how much".

The gap is not that the idea is hard. It is that the two halves — the fairness statistics and the
text detectors — live in different fields and nobody has joined them.

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
- **`tests/test_subgroup_audit.py`** — 24 tests, all on the ways the module could overstate.
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

**Finding 2 — the axis that separates, and it inverts the literature.** Race, gender, economic
status and grade produced no separated disparity: point estimates 1.00x–1.66x, every Wilson
interval overlapping. **English proficiency does separate**, and the direction is the surprise.
At the 0.50 operating point the false-positive rate rises *monotonically across all six
reportable proficiency levels*:

| rated proficiency | 2 | 2.5 | 3 | 3.5 | 4 | 4.5 |
|---|---|---|---|---|---|---|
| false-positive rate | 33.7% | 34.0% | 37.0% | 42.7% | 45.4% | **53.1%** |

1.57x worst-to-best, intervals separate. **The better a learner's English, the more likely our
lite tier calls their writing machine-generated.**

That is the opposite of the story the literature tells. The perplexity account — Liang et al.,
and the reason TOEFL essays get flagged at 61% — says *low*-proficiency writing is predictable,
therefore low-perplexity, therefore machine-like. Our lite tier is not perplexity-keyed; it is
tells-keyed, and it scores polish. Standard, fluent, well-formed prose is what an AI-tells
catalogue is built to recognise, so within a learner population the most accomplished writers
look most artificial to it. Both mechanisms produce false accusations. **They accuse opposite
students.**

**Finding 3 — the disparity reverses with the threshold.** At 0.70 the ordering is no longer
monotonic and the worst group flips to the *lowest* proficiency (6.2% vs 1.9%, ratio 3.25x, also
separated). So which students a detector wrongly accuses is not a fixed property of the detector:
it is a function of the operating point somebody chose, often without knowing that is what they
were choosing. A single-threshold audit would have reported one of these two directions and
never seen the other. This is the strongest argument in the document for why `--sweep` is not a
convenience feature.

**Finding 4 — the demographic axes showed nothing, and that is worth stating plainly.** On race
and ethnicity, gender, economic status and grade, **no ratio separated at 95% confidence at any
threshold**. Point estimates ran 1.00x to 1.66x and every Wilson interval overlapped. The honest
reading is *no demonstrated demographic disparity in this corpus* — not "none exists", and not
the 1.66x. It is also the expected shape: ELLIPSE is one population of US school-age learners, and
the separating variable turned out to be how well they write English, not who they are.

**The methodological finding that makes the tool worth having.** At 0.30 the detector flags
everyone, so it cannot discriminate between groups — a disparity ratio computed there is not "no
bias found", it is "this measurement had no room to find any". A naive implementation would have
reported `race_ethnicity = 1.04x, no disparity` and been badly wrong about what it had shown.
`saturation()` detects both ends and `--sweep` finds the operating band where a comparison means
anything. This is the part a fairness toolkit bolted onto a detector would not have got right,
and it is the reason this belongs in a repo that already knows how to measure its own limits.

### What it cost

Two files, one loader, 24 tests, and 45 seconds of CPU for the full corpus. No GPU, no key, no new
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
