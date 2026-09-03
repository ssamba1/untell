# Measured: who a detector fails — 39,290 human texts, and 176 that a machine wrote

Results 1–14 are **false-positive rates on known-human writing**. The corpora are essays by real
students, so a flag is an error by construction — there is no labelling to dispute and no ground
truth to argue about. That is what makes false positives the cleanest measurement available
against a detector.

[Results 15 and 16](#result-15--both-error-rates-and-why-result-11s-threshold-recommendation-was-wrong)
add the other half, on 176 GPT-3 essays written to the same prompts as the human ones. They are
the two that matter most, because measuring only one error rate is what let this document publish
a "safe" threshold that catches nothing.

Companion to [`strategy-the-audit-position.md`](strategy-the-audit-position.md), which argues why
this is the work. This file is the evidence, in the shape
[`free-ceiling-measured.md`](free-ceiling-measured.md) uses: numbered results, intervals attached,
withdrawals kept visible.

**Reproduce anything below:**

```bash
untell-subgroup-audit --corpus ellipse --tier lite --sweep
untell-subgroup-audit --corpus asap --tier lite --by ell_status
untell-subgroup-audit --corpus ellipse --ablate
untell-subgroup-audit --corpus liang --tier lite --n 0                          # Results 12, 13
untell-subgroup-audit --corpus liang --n 0 --ablate --band-axis population      # Result 14
untell-subgroup-audit --corpus liang-paired --n 0 --odds --threshold 0.775      # Results 15, 16
untell-subgroup-audit --corpus asap --n 0 --by "race_ethnicity*ell_status"      # Result 19
python -c "from eval.datasets import load_liang_paired as L; print(len(L(prompt_engineered=True)))"  # Result 17
untell-ngram-lm train && untell-ngram-lm score --csv <corpus>.csv --by ell_status
untell-gpt2-ppl fetch && untell-gpt2-ppl score --csv <corpus>.csv --by ell_status
```

Raw rows: `.claude/measurements.jsonl`, recipes `ellipse-*`, `asap-subgroup-fpr`,
`burstiness-formulation-robustness`, `true-ngram-perplexity-contrast`,
`gpt2-transformer-perplexity-contrast`, `pelic-l1-and-level`, `published-vs-student-fpr`,
`published-vs-student-threshold-sweep`,
`genre-controlled-professional-vs-student`, `ellipse-threshold-for-target-fpr`,
`unedited-adult-writing`, `liang-population-fpr`, `liang-paired-gpt4-polish`,
`liang-threshold-sweep`, `liang-component-ablation`, `liang-paired-equalised-odds`,
`liang-paired-separation`, `liang-paired-fnr-disparity`,
`liang-prompt-engineered-evasion`, `liang-gpt-simplify-reversal`,
`asap-intersectional-race-by-ell`, `asap-disability-and-ell`.

## The corpora

| | ELLIPSE | ASAP 2.0 | Liang et al. 2023 |
|---|---|---|---|
| essays | 3,904 train + 2,571 held-out (≥60 words) | 17,307 (≥60 words) | 485 (no floor — see below) |
| writers | **all** English language learners | mixed; 2,269 ELL, 14,798 non-ELL | five populations, incl. 91 non-native TOEFL |
| task | independent writing | source-based writing | TOEFL, 8th-grade, college admission, CS224N |
| labels | proficiency, race, gender, SES, grade | ELL status, race, gender, SES, disability, grade | population; and 91 essays paired unedited/GPT-4-polished |
| licence | CC BY-NC-SA 4.0 | CC BY 4.0 | see upstream repository |
| vendored? | **no** — fetched on demand | **no** — fetched on demand | **no** — fetched on demand |

None is committed. ELLIPSE's licence forbids it in an MIT package; ASAP's does not, but a 46 MB
CSV does not belong in a repository either.

Liang's loader applies **no minimum-word floor**, unlike the other two. These are the essays the
published bias figures were computed on, and quietly dropping some of them would make any
comparison against those figures meaningless. It also carries the only *paired* contrast in this
document: `toefl_gpt4_polished` is the same 91 essays as `toefl_nonnative`, run through GPT-4.

---

## Result 1 — the shipped lite threshold flags 97.4% of known-human ESL writing

ELLIPSE, 3,904 essays, tier `lite`, threshold **0.30 — the value untell ships**.

| threshold | false-positive rate | 95% CI | state |
|---|---|---|---|
| **0.30 (shipped)** | **97.4%** | 96.9–97.9% | saturated |
| 0.50 | 38.7% | 37.2–40.2% | measurable |
| 0.70 | 3.2% | 2.7–3.8% | measurable |
| 0.80 | 0.8% | 0.6–1.1% | saturated low |

The documented lite figure is **30% on conversational prose**. On school-age ESL writing it is
97.4%. The tier is not weak on this population; it says yes to almost everyone, and its threshold
was calibrated on a corpus that does not resemble the writers most likely to be accused.

**Methodological point, and the reason `--sweep` exists.** At 0.30 the detector cannot discriminate
between *anyone*, so a subgroup ratio computed there is not "no bias found" — it is "this
measurement had no room to find any". A naive implementation reports `race_ethnicity = 1.04x, no
disparity` and is badly wrong about what it has shown. `saturation()` detects both ends.

## Result 2 — false-positive rate rises with English proficiency, replicated held-out

ELLIPSE at threshold 0.50, banding low (≤2.5) against high (≥3.5) rated proficiency.

| split | low proficiency | high proficiency | ratio | intervals separate |
|---|---|---|---|---|
| train (n=2,519 banded) | 33.2% | **44.2%** | 1.33x | yes |
| **held-out (n=1,618 banded)** | 34.8% | **43.0%** | 1.24x | **yes** |

Overall FPR was 38.7% on *both* splits. **The better a learner's English, the more likely the lite
tier calls their writing machine-generated.**

**Withdrawn.** The first run reported a *monotonic* rise across all six proficiency levels
(33.7% → 53.1%, 1.57x). On held-out data the ordering is not monotonic and the top level alone
(4.5, n=55) does not separate. That was an artifact of the larger split's sample sizes. The banded
contrast is what survived, and it is the only version that should be quoted.

## Result 3 — the two halves of the detector are biased against opposite groups

ELLIPSE. Each component of `perplexity_burstiness` thresholded at its **own median**, so both flag
about half the corpus and neither is handicapped by a lopsided operating point.

| component | low proficiency | high proficiency | worse for | ratio | held-out ratio |
|---|---|---|---|---|---|
| vocabulary (common-word ratio) | **63.4%** | 40.3% | **low** | 1.57x | 1.59x |
| burstiness (sentence-length CV) | 40.2% | **57.1%** | **high** | 1.42x | 1.35x |

All four rows separate at 95%. In the combined score the two partly cancel, so **any aggregate
fairness number for this detector understates both of its biases**. Averaging two large opposing
biases yields a small number and a false reassurance — and a benchmark that treats the detector as
an opaque scorer cannot recover either. This is the single strongest argument for component-level
auditing.

## Result 4 — the bias is in the features, not in untell's calibration

Raw signals, before any detector touches them, low vs high proficiency band.

| signal | low | high | Cohen's *d* | held-out *d* |
|---|---|---|---|---|
| sentence-length CV | 0.5214 | 0.4555 | −0.394 | −0.363 |
| common-word ratio | 0.6045 | 0.5803 | −0.476 | −0.537 |

Nothing about untell is involved in those numbers. **Any detector that treats low sentence-length
variance as machine-like inherits a penalty on writing maturity**, and any detector that treats
predictable vocabulary as machine-like inherits the opposite penalty.

**Scope.** Burstiness is the feature GPTZero popularised and still explains publicly, but GPTZero
migrated to a deep-learning architecture in autumn 2023. None of this is a claim about current
GPTZero. It applies to detectors still using the heuristic — untell's own lite tier included.

## Result 5 — it is not an artifact of one formula

Five measures of sentence-length dispersion, both corpora.

| measure | ELLIPSE (low vs high) | ASAP (ELL vs non-ELL) |
|---|---|---|
| CV (shipped) | +0.467 | +0.119 |
| raw standard deviation | +0.568 | +0.306 |
| median absolute deviation | +0.486 | +0.247 |
| normalised entropy | −0.647 \* | −0.292 \* |
| range / mean | +0.059 | −0.108 |

\* entropy over length proportions is *maximised* by uniformity, so its sign is inverted by
construction and it agrees with the other three.

**Four of five agree, on both corpora, in the same direction.** Only range-over-mean fails, and it
is a max-minus-min statistic dominated by a single outlier sentence.

## Result 6 — on an independent corpus, non-native writers are flagged LESS

ASAP 2.0, 17,307 essays, threshold 0.50, overall FPR 31.6%. `NA` excluded from every group.

| axis | flagged more | flagged less | ratio | separate |
|---|---|---|---|---|
| **ELL status** | **non-ELL 32.2%** (n=14,798) | ELL 26.7% (n=2,269) | 1.21x | yes |
| economic status | not disadvantaged 38.1% | disadvantaged 33.7% | 1.13x | yes |
| race/ethnicity | White 33.1% (n=6,989) | Asian/Pacific Islander 23.4% | 1.41x | yes |
| disability | identified 38.3% | not identified 34.8% | 1.10x | yes |

**All four separate at 95%**, where ELLIPSE showed no demographic separation at all — the expected
shape for a corpus that is 71% Hispanic/Latino and entirely learners.

The first row reverses the finding that made detector bias a public issue. This is **not** a
refutation of Liang et al., who measured commercial detectors on TOEFL essays and found 61% false
positives on non-native writing. This is a burstiness-weighted heuristic, a different class of
tool, carrying the opposite bias.

**The consequence is the whole argument for the instrument:** "detectors are biased against
non-native speakers" is true of the tools that were measured and false of this one, and nobody can
tell which they have without measuring. **A published bias direction does not transfer across
detector classes.**

## Result 7 — untell's "perplexity" channel is anti-correlated with real perplexity

Interpolated bigram LM, 2,001,501 tokens from NLTK Brown + Reuters, independent of both essay
corpora, no model download. Lower log-perplexity = more predictable = the machine-like end.

| corpus | groups | mean log-perplexity | Cohen's *d* | lower (more machine-like) |
|---|---|---|---|---|
| ELLIPSE | low vs high proficiency | 6.5816 / 6.4406 | −0.320 | **high proficiency** |
| ASAP | ELL vs non-ELL | 7.0837 / 6.8778 | −0.491 | **non-ELL** |

Across three signal families: the stoplist ratio penalises low-proficiency and ELL writers, while
burstiness **and true perplexity** both penalise the more fluent writer. **Two of three point at the
more fluent writer, and the odd one out is ours.**

**Correction this supersedes.** An earlier draft described the vocabulary term as "reproducing
Liang et al.'s perplexity account exactly". It reproduces the *shape*, but it is the fraction of
tokens in a 120-word stoplist, and on this population it is anti-correlated with the real thing. The
lite tier's perplexity channel is not a valid stand-in for what it is named after.

**Limitation.** The LM is 1961 American English plus newswire — a weak model and a domain mismatch
with school essays, so non-native writing being less predictable to *that* model is partly expected.
A modern in-domain LM could differ.

---

## Result 8 — a real transformer shows it more strongly, and the "blocker" was my error

GPT-2 124M (`gpt2-lm-head-10.onnx`, 664,871,060 bytes), n=250 per group, seed 0, 384-token cap.
Mean negative log-likelihood; lower = more predictable = the machine-like end.

| corpus | groups | mean NLL | Cohen's *d* | bigram *d* (Result 7) |
|---|---|---|---|---|
| ASAP | ELL / non-ELL | 3.8748 / **3.5533** | **−0.671** | −0.491 |
| ELLIPSE | low / high proficiency | 3.7733 / **3.1725** | **−1.320** | −0.320 |

Same direction as the stdlib bigram model, and **larger in both cases** — on ELLIPSE, four times
larger and a very large effect. So the direction is not an artifact of a weak n-gram model over
1961 newswire: **scaling the language model amplifies it.** Any perplexity-based detector — which
is most neural detectors — should be expected to flag the more fluent writer more on this
population until measured otherwise.

**How this was obtained, recorded because I reported it as blocked twice.** huggingface.co and
four mirrors are egress-blocked. But the ONNX model zoo keeps GPT-2 in **GitHub LFS**, LFS objects
for public repos are served by `media.githubusercontent.com`, the BPE vocabulary is published on
GitHub, and `onnxruntime` installs from pypi — which this environment does not proxy. My earlier
403 came from a `github.com/...` URL hitting this session's *repository scoping*, and I read a
permission error as a network one and stopped. The correct lesson is not "the environment was
generous"; it is that **I called something impossible after four probes and it took a fifth.**

**Limits.** GPT-2 small, sampled at n=250 per group, 384-token cap. A perplexity *signal*, never a
detector verdict.

## Result 9 — a third corpus, a new axis, and a direction reversal

[PELIC](https://github.com/ELI-Data-Mining-Group/PELIC-dataset) — 17,144 texts (of 46,204) from
**adult university ESL** students across 20+ first languages. A different age band, a different
task, and a different L1 mix from both corpora above. Overall FPR 39.1%.

**New axis: your first language changes your false-positive rate.**

| L1 | n | FPR |
|---|---|---|
| Arabic | 5,818 | **40.9%** |
| Japanese | 1,115 | 41.2% |
| Spanish | 784 | 39.5% |
| Korean | 3,556 | 39.3% |
| Chinese | 3,226 | 38.1% |
| Thai | 583 | 33.6% |
| Turkish | 536 | **29.7%** |

Arabic vs Turkish is **1.38x, intervals separate**, and both are well sampled. (The tool's own
worst-vs-best line reports German 59.6% against Hebrew 26.2%, 2.27x — but those rest on n=52 and
n=61, and the large-n pair is the figure that should be quoted.)

> **Re-derived under the [selection correction](#result-19--crossing-finds-less-not-more-the-headline-is-retracted), and the caution above was right.**
> This axis has **20 language groups**, so a worst-vs-best pick comes from 190 pairs and needs
> z = 3.65. The tool's 2.27x German-vs-Hebrew headline **does not survive** — it separated only at
> a plain 95%, exactly as its sample sizes suggested. The hand-picked Arabic-vs-Turkish pair
> **does survive at that same z = 3.65**, on n=5,818 and n=536. Declining the tool's own headline
> in favour of the well-sampled pair was an editorial judgement made before the correction existed,
> and the correction agrees with it. That is the most reassuring thing in this document: the
> instrument's caution and its statistics reached the same answer independently.

**And the proficiency effect runs the opposite way to Result 2.**

| PELIC level | 2 | 3 | 4 | 5 |
|---|---|---|---|---|
| FPR | **52.9%** | 40.9% | 39.9% | **36.5%** |

Monotonically *decreasing* with proficiency, 1.45x, separated — and it **holds under the
correction** (four levels, six pairs, z = 2.64) — where ELLIPSE showed it *increasing*
(33.2% → 44.2%). Same detector, same kind of subgroup, **opposite direction**.

ELLIPSE is US school students writing full independent essays; PELIC is adult university ESL
classroom writing. So the direction of a proficiency disparity is **not a property of the detector
alone** — it depends on the population and the task.

**This is the strongest form of the argument for the instrument.** You cannot predict who a
detector fails from a published result, *even a published result about the same detector and the
same kind of subgroup*. It has to be measured on the population that will actually be judged.

Gender does not separate here (1.03x, overlapping) — consistent with ELLIPSE and ASAP.

**Caveat.** PELIC's median text is 23 words, so the ≥60-word floor keeps 37% of it and may select
for longer, more elaborated answers.

## Result 10 — the largest disparity here is not demographic, it is professional-vs-student

Same detector, same 0.50 threshold, every flag an error.

| population | n | FPR | 95% CI |
|---|---|---|---|
| Gutenberg literary classics | 144 | **1.4%** | 0.4–4.9% |
| Brown 1961 published American prose | 280 | **3.2%** | 1.7–6.0% |
| Reuters newswire | 26 | 3.8% | 0.7–18.9% |
| ASAP — US school students | 17,307 | **31.6%** | — |
| ELLIPSE — US school ESL | 3,904 | **38.7%** | — |
| PELIC — adult university ESL | 17,144 | **39.1%** | — |

**Roughly a tenfold gap** — an order of magnitude larger than any subgroup disparity in this
document, which topped out at 2.27x and at 1.55x among well-sampled groups.

The practical reading: **a detector validated on "human writing" — which in practice usually means
published, edited, professional text — will look excellent and then fail catastrophically on
students, who are the population it is actually deployed against.** That is a plausible mechanism
for vendors publishing sub-1% false-positive rates that nobody can reproduce in a classroom.

**The gap holds at every operating point, and is worst at the shipped one.**

| threshold | Brown | Gutenberg | ELLIPSE students |
|---|---|---|---|
| **0.30 (shipped)** | 25.0% | 47.2% | **97.4%** |
| 0.50 | 3.2% | 1.4% | 38.7% |
| 0.70 | 0.0% | 0.0% | 3.2% |

So it is not an artifact of threshold choice. (Gutenberg scoring worse than Brown at 0.30 is left
unexplained rather than rationalised: 19th-century literary prose is its own genre, and the
ordering *among* professional corpora is not stable — only their distance from student writing is.)

**Genre does not explain it — controlling for genre makes the gap wider.** Brown carries genre
codes, so its *editorial* section is argumentative prose, the genre match for student
argumentative essays. Chunked to ~400 words to match the median student essay (ELLIPSE 402).

| population | n | FPR @ 0.30 | FPR @ 0.50 |
|---|---|---|---|
| Brown **editorial** (argumentative) | 162 | 42.6% | **0.6%** |
| Brown essays / belles-lettres | 450 | 54.9% | 4.7% |
| Brown press reportage (narrative control) | 267 | 30.0% | 2.2% |
| **ELLIPSE student argumentative** | 3,904 | **97.4%** | **38.7%** |

At 0.50 the genre-matched contrast is **0.6% vs 38.7% — a 64x ratio**, wider than the
un-matched comparison, because editorial prose is the *lowest*-scoring professional category.
Matching the genre made the professionals look better, not worse.

**Editing is ruled out too, and the answer is sharper than "professionals vs students".** I said
separating "professional" from "edited" needed unpublished professional drafts that no reachable
corpus contained. NLTK ships them: forum posts and consumer reviews are unedited adult first-draft
writing.

| population | edited? | n | FPR @ 0.30 | FPR @ 0.50 |
|---|---|---|---|---|
| Wine reviews | **no** | 64 | **0.0%** | 0.0% |
| Firefox forum posts | **no** | 80 | **2.5%** | 0.0% |
| Product reviews | **no** | 80 | 26.2% | 1.2% |
| Brown editorial | yes | 162 | 42.6% | 0.6% |
| Brown essays / belles-lettres | yes | 450 | 54.9% | 4.7% |
| **ELLIPSE student essays** | **no** | 3,904 | **97.4%** | 38.7% |

Unedited adult writing scores like professionals — better, in fact. Forum posts at 2.5% beat
*edited* Brown editorial at 42.6%. **Editing is not the driver.**

What the ordering actually tracks is **essay register**: informal adult writing (0.0–2.5%) <
consumer reviews (26.2%) < formal published essays (42.6–54.9%) < student essays (97.4%). That is
a gradient in formality and structural uniformity, and it is exactly what the burstiness mechanism
predicts — informal writing has wildly varied sentence lengths, and a formal assigned essay is the
most uniform text a person produces.

**So the sharpest statement of this result is not "professionals vs students". It is that the
detector penalises the essay form — and the essay is precisely the artifact students are required
to produce and be judged on.**

Limits: n=64–80 per unedited population, so those intervals are wide, and register now covaries
with population in the opposite direction from before. Reuters n=26 must not be quoted alone.

What it does establish: **the population a detector is validated on can differ from its deployment
population by an order of magnitude in false-positive rate.** Any published FPR that does not name
its population is uninformative about the students it will be used on.

## Result 11 — the thresholds that reach a target false-positive rate on student writing (recommendation withdrawn)

Empirical quantiles of the shipped lite scorer over 3,904 known-human ESL essays.

| target false-positive rate | threshold required |
|---|---|
| 30% | 0.532 |
| 10% | 0.625 |
| 5% | 0.671 |
| **1%** | **0.775** |
| *shipped 0.300* | *actual 97.4%* |

> **WITHDRAWN as a recommendation, 2026-09-01.** See [Result 15](#result-15--both-error-rates-and-why-result-11s-threshold-recommendation-was-wrong).
> Measured against machine-written text, 0.775 misses **100%** of 176 GPT-3 essays — because the
> highest score anything in that corpus receives is 0.7655, so the threshold sits above the
> scorer's entire range. The quantiles below are correct and the inference drawn from them was
> not: derived from a human-only corpus, they cannot distinguish a safe threshold from an inert
> one. The table stands as a measurement; do not use it to pick an operating point.

**This is not a recommendation to change the default.** Raising the threshold trades false
positives for false negatives, and the rewriting loop's behaviour is calibrated around 0.30
throughout the package. It is the number a maintainer needs in order to make that choice
deliberately rather than inherit it.

## Result 12 — Liang et al.'s own corpus, and the first paired contrast in this document

The corpus every "detectors are biased against non-native writers" claim descends from is
[Liang et al. 2023](https://github.com/Weixin-Liang/ChatGPT-Detector-Bias): 485 human-authored
essays in five populations. It was added on 2026-09-01 after reading
`satyamshivam13/AI_Text_Detector`, which had been measuring per-population false-positive rates on
it since July 2026 — see [the strategy doc](strategy-the-audit-position.md) for the claim of ours
that falsified. Every essay is human-written, so every flag is an error.

Lite tier, at the **shipped 0.30 threshold**, all 485 essays:

| population | n | false-positive rate | 95% CI |
|---|---|---|---|
| TOEFL, non-native writers | 91 | **96.7%** | 90.8–98.9% |
| US 8th-grade students | 88 | 88.6% | 80.3–93.7% |
| *the same 91 TOEFL essays, GPT-4 polished* | 91 | *78.0%* | *68.5–85.3%* |
| Stanford CS224N students | 145 | 73.1% | 65.4–79.7% |
| US college admission essays | 70 | **58.6%** | 46.9–69.4% |
| **overall** | 485 | **79.2%** | 75.3–82.5% |

Liang's ordering reproduces against untell's own detector: non-native writers are flagged most,
and the gap to the best-served population is 1.65x with separated intervals.

**The new part is the third row, and it is the first properly paired comparison in this
document.** `toefl_gpt4_polished` is not another population — it is *the same 91 essays* by the
same 91 writers, run through GPT-4. Same writers, same prompts, same everything except the
editing, which is the contrast every result above had to approximate with a control. Unedited
they are flagged **96.7%**; after a large language model rewrites them, **78.0%**, and the
intervals do not overlap.

**Passing a non-native writer's essay through GPT-4 makes untell's detector less likely to call
it AI.** Not more. The detector is not detecting machine involvement in these essays; whatever it
is keyed to, GPT-4's editing removes some of it. That is a stronger form of Result 10's finding —
the penalty is on a way of writing, not on machine provenance — and here it is established by a
within-writer paired design rather than by a between-corpus contrast.

> **SCOPE CORRECTION ([Result 18](#result-18--result-12-does-not-generalise-on-a-second-population-llm-editing-makes-it-worse)).**
> This holds for TOEFL essays and does **not** generalise. On the second machine-edited arm Liang
> ships — 8th-grade essays simplified by GPT — the effect reverses: 88.6% → 94.3%, d = +0.646.
> The numbers above stand; the sentence "a language model editing an essay makes it look like a
> more fluent human wrote it" was drawn from one population and is withdrawn as a general claim.

## Result 13 — raising the threshold cuts the error rate and widens the gap

Untell's threshold sweep and saturation check, run on Liang's corpus. Neither
`fpr_by_population.py` nor BAID reports this, because both fix an operating point:

| threshold | overall FPR | worst-vs-best population | state |
|---|---|---|---|
| **0.30** *(shipped)* | 79.2% | 1.65x * | measurable |
| 0.50 | 25.6% | **6.93x** * | measurable |
| 0.70 | 2.3% | not distinguishable | measurable |
| 0.80 | 0.6% | — | saturated |
| 0.90+ | 0.2% | — | saturated |

`*` = a real difference — the intervals do not overlap once widened for the fact that these two
groups were *selected* as the extremes of five ([the correction](#result-19--crossing-finds-less-not-more-the-headline-is-retracted)).
Both starred rows were re-derived under it and hold.

The overall rate falls monotonically. **The disparity does not.** It more than quadruples between
0.30 and 0.50 — at 0.50 the TOEFL non-native essays are flagged 49.5% (39.4–59.5) against 7.1%
(3.1–15.7) for college admission essays — before the detector stops flagging enough of anything
for a difference to be measurable at this sample size.

This is what an aggregate false-positive rate hides. Moving 0.30 → 0.50 looks like an unambiguous
improvement: three quarters of the errors disappear. The errors that remain are concentrated on
the population that was already worst served, and a maintainer reading only the overall number
would take that trade without seeing it. The honest reading of the last two rows is *not* "0.80
is fair" — it is that the detector has stopped discriminating between anything, which the
saturation flag says rather than letting a clean-looking ratio imply fairness.

## Result 14 — the two channels rank the populations in nearly opposite orders, and that is what decides the direction of an edit

Component ablation on Liang's 485 essays. Each half of `perplexity_burstiness` is thresholded at
its **own median**, so both flag about half the corpus and neither can look fairer merely by
having less room to differ.

| population | vocabulary channel | burstiness channel |
|---|---|---|
| TOEFL, non-native | **100.0%** (96.0–100) | 46.2% (36.3–56.3) |
| US 8th-grade | 95.5% (88.9–98.2) | 15.9% (9.7–24.9) |
| college admission | 64.3% (52.6–74.5) | **12.9%** (6.9–22.7) |
| *TOEFL, GPT-4 polished* | *24.2%* (16.5–33.9) | *74.7%* (64.9–82.5) |
| Stanford CS224N | **0.7%** (0.1–3.8) | **75.9%** (68.3–82.1) |
| worst-vs-best | **144.93x**, separated | **5.9x**, separated |

The orderings are close to inverted. The channel untell calls "perplexity" — in fact the fraction
of tokens drawn from a 120-word stoplist — flags **every single** non-native TOEFL essay and
**0.7%** of Stanford CS224N essays, a 145-fold spread at equal power. The burstiness channel puts
CS224N at the top and college admission essays at the bottom. Each channel's worst-served
population is near the other's best-served, and both gaps separate at 95%. This is Result 3 on a
third corpus with five bands instead of two, and it is much larger here.

**It also explains Result 12's paradox — and, in [Result 18](#result-18--result-12-does-not-generalise-on-a-second-population-llm-editing-makes-it-worse),
predicts where that paradox reverses.** GPT-4 polishing the same 91 TOEFL essays moves them *down*
the vocabulary channel, 100.0% → 24.2%, and *up* the burstiness channel, 46.2% → 74.7%. The model
replaces the common-word-heavy vocabulary of a learner writing in a second language, which is most
of what this detector is keyed to, while regularising sentence lengths, which is what the smaller
channel penalises. Here the vocabulary effect is larger, so the composite flag rate falls: 96.7% →
78.0%.

The general form is what matters, because the balance is not fixed: **an edit moves a text on two
channels that disagree, and the net direction is decided by which movement is larger.** On
8th-grade essays simplified by GPT the burstiness collapse dominates instead and the flag rate
*rises*. Same mechanism, opposite outcome.

## Result 15 — both error rates, and why Result 11's threshold recommendation was wrong

Every result above this one measures **false positives only**. This document said plainly why:
equalised odds needs machine-written text from the same writers on the same prompts, and RAID,
MAGE and HC3 are all HuggingFace-hosted and unreachable here. That was true of those three and
false in general. **Liang ships the machine half in the same repository** —
`Data_and_Results/GPT_Data`, one directory across from the human essays this document had already
been loading for two results: 145 GPT-3 essays on the CS224N prompts, 31 on the college-admission
prompts, domain-matched to their human counterparts.

215 human and 176 machine essays, lite tier. A false positive is a human essay flagged; a false
negative is a GPT-3 essay missed:

| threshold | false-positive rate | false-negative rate | total error |
|---|---|---|---|
| 0.25 | 80.9% | 0.6% | 81.5% |
| **0.30** *(shipped)* | **68.4%** | **1.7%** | 70.1% |
| 0.35 | 55.3% | 8.0% | 63.3% |
| 0.40 | 35.3% | 19.3% | 54.7% |
| **0.43** *(minimum total error)* | 24.2% | 27.3% | **51.5%** |
| 0.50 | 11.6% | 57.4% | 69.0% |
| 0.60 | 0.5% | 86.9% | 87.4% |
| **0.775** *(Result 11's recommendation)* | **0.0%** | **100.0%** | 100.0% |

**Result 11 is withdrawn as a recommendation.** It reported that a threshold of 0.775 gives a 1%
false-positive rate on ELLIPSE, and offered that as the number "a maintainer needs in order to
make that choice deliberately". Measured against machine text, 0.775 misses **every one** of 176
GPT-3 essays. The reason is not a trade-off: **the highest score any essay in this corpus
receives, human or machine, is 0.7655.** The recommended threshold sits above the entire range
the scorer produces. Its 0% false-positive rate is not safety, it is a detector that has been
switched off.

Result 11 was derived from FPR quantiles on a human-only corpus, where *any* threshold above the
score range scores a perfect zero. **With one error rate, "safe" and "inert" are the same
number.** That is this repository's own argument about detectors, and it went unnoticed in its
own published recommendation for as long as only half the audit could run. `equalised_odds` now
refuses to report a near-total false-negative rate quietly: at or above 99% it attaches an
explicit note that a 0% false-positive rate bought by catching nothing is an off switch.

**What the detector is actually worth.** It is not noise — the ranking carries real signal:

- **AUROC 0.8012** on this corpus (0.5 would be a coin flip).
- Human scores mean **0.3548**, machine **0.4820**. Both distributions sit in a narrow band and
  overlap heavily: human 5th–95th percentile 0.154–0.548, machine 0.335–0.652.

So the problem is calibration, not discrimination. A score that ranks well but compresses both
classes into a 0.15–0.65 band has no threshold that separates them cleanly, which is why the best
achievable total error is 51.5%. **On this evidence the lite tier is a usable ranking signal and
is not usable as an accusation instrument at any threshold** — and that, rather than a number to
move the default to, is the answer to "what should the threshold be".

## Result 16 — false-positive parity looked acceptable while the false-negative gap was 4.1x

The failure mode `equalised_odds` was built to catch, observed on real data rather than in a
fixture. At threshold 0.50:

| population | false-positive rate | false-negative rate |
|---|---|---|
| college admission | 7.1% (3.1–15.7) | 16.1% (7.1–32.6) |
| Stanford CS224N | 13.8% (9.1–20.4) | **66.2%** (58.2–73.4) |
| disparity | 1.93x, intervals **overlap** | **4.10x, intervals separate** |

An FPR-only audit at this operating point reports a 1.93x gap that does not reach significance,
and concludes there is no demonstrated disparity. The detector is in fact missing **two thirds**
of the machine-written CS224N essays against one sixth of the machine-written college essays, and
that gap is real. The two populations are not being served equally; the half of the audit that
could see it is the half that could not be run until the corpus above was found.

## Result 17 — the cheapest possible evasion multiplies the miss rate, and costs nothing

Liang generated each machine arm twice: GPT-3 asked to write on the prompt, and GPT-3 asked to
write on the prompt *in a way that does not look machine-generated*. Same model, same prompts,
same 176 essays — the only variable is the instruction. No fine-tuning, no rewriting tool, no
paraphraser. The human essays are unchanged, so the false-positive rate is identical in both
columns and only the miss rate moves.

| threshold | FNR, plain GPT-3 | FNR, prompt-engineered | FPR (same in both) |
|---|---|---|---|
| **0.30** *(shipped)* | 1.7% (0.6–4.9) | **10.2%** (6.6–15.6) | 68.4% |
| **0.43** *(minimum total error)* | 27.3% (21.2–34.3) | **49.4%** (42.1–56.8) | 24.2% |
| 0.50 | 57.4% | 76.7% | 11.6% |

Both gaps separate at 95%. Mean score falls from **0.4820** to **0.4302**, Cohen's **d = −0.522** —
a medium effect, in the direction of looking more human.

**At the shipped threshold this detector flags 68.4% of real students while missing one in ten
machine essays that were merely asked to be discreet.** At the best-total-error threshold it
misses **half** of them. The attack is one sentence added to a prompt: it needs no tool, no
budget, no technical skill, and it is the first thing anyone actually trying would do.

Two things follow that matter beyond this document. `ROADMAP.md` treats raw evasion strength as a
race untell cannot win and should stop spending on, which stands — but the reason is stronger than
"the state of the art is ahead of us". **The baseline attack already works**, so evasion strength
was never the axis. And Result 15's finding sharpens: the lite tier is not merely miscalibrated
for accusation, it is miscalibrated against an adversary who does nothing but ask nicely.

## Result 18 — Result 12 does not generalise: on a second population, LLM editing makes it *worse*

Result 12 found that GPT-4 polishing made non-native TOEFL essays *less* likely to be flagged, and
drew a general conclusion: "a language model editing an essay does not make it look
machine-written to this detector — it makes it look like a more fluent human wrote it." Liang
ships a second machine-edited arm, `HewlettStudentEssay_GPTsimplify_88`, which was not used. Run
on it, **the effect reverses.**

| population | treatment | FPR before | FPR after | Cohen's d |
|---|---|---|---|---|
| TOEFL, non-native | GPT-4 **polished** | 96.7% | **78.0%** | negative — editing helped |
| US 8th-grade | GPT **simplified** | 88.6% | **94.3%** | **+0.646** — editing hurt |

**The general claim is withdrawn.** Editing an essay with a language model does not reliably make
it look more human to this detector; on 8th-grade writing it made things measurably worse. Result
12's numbers stand for TOEFL and its inference beyond TOEFL does not.

**What survives is the mechanism, and it is not the one I would have guessed.** The obvious
explanation — that polishing and simplifying push vocabulary in opposite directions — is wrong.
Measured on the raw channels, both treatments move *both* channels the same way:

| population | treatment | common-word ratio | burstiness |
|---|---|---|---|
| TOEFL | polished | 0.5614 → 0.4411 (**−0.120**) | 0.4022 → 0.3269 (−0.075) |
| 8th grade | simplified | 0.5618 → 0.4763 (−0.086) | 0.4969 → 0.3086 (**−0.188**) |

A *higher* common-word ratio reads as machine-like; a *lower* burstiness reads as machine-like. So
in both cases the edit makes the essay look more human on vocabulary and more machine on
burstiness — the two channels pull against each other exactly as
[Result 14](#result-14--the-two-channels-rank-the-populations-in-nearly-opposite-orders-and-that-explains-result-12)
describes, and **the net direction is decided by which movement is larger.** For TOEFL the
vocabulary shift dominates (−0.120 against −0.075) and the score falls. For the 8th-graders the
burstiness collapse dominates (−0.188 against −0.086) and the score rises.

So the opposed-channel finding is confirmed, and strengthened by predicting a reversal rather than
only describing a static ranking. What is refuted is the tidier story built on top of it. The
honest form of Result 12 is: **an LLM edit moves a text along two channels that disagree, and
whether the detector then flags it more or less is a property of the population and the edit, not
of language models in general.**

## Result 19 — crossing finds *less*, not more: the headline is retracted

**This result originally claimed the opposite and was wrong.** It is kept in full because the way
it failed is worth more than the finding would have been.

Added after [Identifying Bias in Machine-generated Text Detection](https://aclanthology.org/2026.acl-long.109.pdf)
(Pindrop, ACL 2026 Main) found bias "most dangerous where attributes intersect". All 17,307 ASAP
essays, lite tier at threshold 0.50:

| axis | cells | ratio | separated at plain 95% | **separated, corrected** |
|---|---|---|---|---|
| `ell_status` | 2 | 1.21x | yes | **yes** |
| `race_ethnicity` | 6 | 1.55x | yes | **no** |
| `race_ethnicity*ell_status` | 10 | 2.14x | yes | **no** |

The original write-up reported the bottom row as a demonstrated 2.14x and concluded "cross the
axes, because single-axis reporting understates". Both halves are withdrawn.

**What went wrong.** `separated` compared the worst and best cells — two groups the data itself
selected — against a plain 95% interval. With 10 reportable cells that pick comes from 45 pairs,
and the yardstick has to widen accordingly ([the correction](#) uses Bonferroni: z = 3.28 at 45
pairs, 3.41 at 78). Under it, the crossed axis loses its verdict, and so does `race_ethnicity`
alone at six levels. The only ASAP claim left standing on this corpus is the two-level
`ell_status` axis at 1.21x.

**The corrected lesson is the opposite of the one I drew, and more useful.** Crossing buys
resolution and *pays for it in statistical power*, because the correction scales with the number
of cells the cross produces. A 6-level axis crossed with a 2-level one yields ten cells and a
z of 3.28; the extra resolution does not come close to covering that. **Cross axes with few
levels.** [Result 20](#result-20--students-with-disabilities-are-flagged-more-and-it-cancels-the-ell-effect)
is the same technique on a 2×2 and survives comfortably — not because the effect is larger, but
because four cells cost almost nothing to correct for.

**And the ELLIPSE run is the clean warning.** Five crossed axes were tried there. Four found
nothing. The fifth, `race_ethnicity*grade`, separated at 1.59x across **13 cells** while *no
single ELLIPSE axis separates at all* — and it does not survive correction either. Trying five
crosses and reporting the one that fires, over thirteen post-hoc cells, is how a measurement tool
manufactures a finding. This document caught it in its own instrument, which is the only reason
it is not in it.

## Result 20 — students with disabilities are flagged more, and it cancels the ELL effect

The literature names neurodivergent students — autism, ADHD, dyslexia — as disproportionately
flagged by AI detectors, and says the mechanism is reliance on repeated phrasing and vocabulary.

**It also says the rate has never been measured.** Searched 2026-09-01: unlike the non-native
English bias, which Liang et al. put at 61.3% and half a dozen groups have since replicated, there
is **no peer-reviewed study quantifying how often neurodivergent writers are falsely flagged**.
The evidence is documented mechanisms and individual cases — a student with autism given a zero on
a detector's say-so — not a rate with an interval on it.

ASAP labels 1,921 essays *Identified as having disability* against 11,367 *Not identified*, and
this instrument had never looked: `student_disability_status` was not in the default axes, so a
default ASAP run reported nothing about it. All 17,307 essays, threshold 0.50:

| axis | worst | best | ratio | intervals |
|---|---|---|---|---|
| `student_disability_status` | identified **38.3%** | not identified 34.8% | 1.10x | **separate** |
| `economically_disadvantaged` | **not** disadvantaged 38.1% | disadvantaged 33.7% | 1.13x | separate |
| `student_disability_status*ell_status` | identified × non-ELL **38.5%** | not identified × ELL **26.0%** | **1.48x** | **separate** |

**This is the first axis in this document where the direction matches the field's expectation.**
Everything above reverses it — non-ELL flagged more than ELL, non-disadvantaged more than
disadvantaged, professionals more than students. Here the disadvantaged group really is the one
paying: students identified as having a disability are flagged more, and the gap separates.

**The crossed row is the finding, and it survives the correction.** This detector treats ELL
status as *protective* — 26.7% for ELL against 32.2% for non-ELL, a two-level axis that separates
uncorrected and corrected alike. That protection is essentially absent for students with
disabilities: not-identified ELL writers are flagged **26.0%**, identified ELL writers **36.9%**.
Being identified as having a disability cancels the only thing that was helping. Neither single
axis shows this: disability alone is 1.10x, and the ELL axis alone points the other way entirely.

All three rows above hold under the selection correction that
[retracted Result 19](#result-19--crossing-finds-less-not-more-the-headline-is-retracted) — and
for a reason worth stating, because it is not that this effect is bigger. **The cross is 2×2.**
Four cells means six pairs and z = 2.64, against ten cells, forty-five pairs and z = 3.28 for
Result 19's `race_ethnicity*ell_status`. Crossing two binary axes is nearly free; crossing a
six-level axis with a binary one is not. That is the whole difference between a result that
stands and one that does not, and it is a property of the design rather than of the world.

It is the one case in this document where crossing changed the answer rather than refining it —
Result 19 tried the same technique on a wider axis and lost the claim to the correction — and it
is why the defaults now follow the corpus: `--corpus asap` reports `ell_status`, `student_disability_status` and their cross
without being asked, because a heading a caller never thinks to request is a group nobody measures.

**What this is, and three things it is not.** It is a rate with an interval, on a labelled corpus
of 13,288 essays, for a population the literature describes qualitatively and has not quantified.
That is the one result in this document with no better-resourced prior version, and it exists
because the corpus was already on disk and the axis was one line of configuration away.

It is **not** a measurement of neurodivergence. ASAP records *identified as having a disability*,
an administrative category that includes physical and sensory disabilities and misses every
undiagnosed or unregistered student. The overlap with autism, ADHD and dyslexia is real but
partial and unmeasured here.

It is **not** a general claim about detectors. Bias is model-specific — Pindrop's 16-detector
study says so and every reversal in this document demonstrates it. This is untell's lite tier and
nothing else.

And 1.10x is **not** a large disparity. It separates because n is large; the intersectional gap
at 1.48x is the one that matters. A single-axis reading of this result would understate it, which
is the point of the row below it.

## Every multi-group claim, re-derived under the correction

The [selection correction](#result-19--crossing-finds-less-not-more-the-headline-is-retracted)
changes the verdict on every axis with more than two groups, so all of them were re-run rather
than assumed. `separated` below is the corrected verdict; a two-group axis is unaffected by
construction.

| result | axis | cells | ratio | plain | **corrected** |
|---|---|---|---|---|---|
| 12 | Liang `population` @0.30 | 5 | 1.65x | yes | **holds** |
| 13 | Liang `population` @0.50 | 5 | 6.93x | yes | **holds** |
| 14 | ablation, vocabulary channel | 5 | 144.93x | yes | **holds** |
| 14 | ablation, burstiness channel | 5 | 5.90x | yes | **holds** |
| 20 | ASAP `student_disability_status` | 2 | 1.10x | yes | **holds** |
| 20 | ASAP `disability*ell_status` | 4 | 1.48x | yes | **holds** |
| 20 | ASAP `economically_disadvantaged` | 2 | 1.13x | yes | **holds** |
| — | ASAP `ell_status` | 2 | 1.21x | yes | **holds** |
| 19 | ASAP `race_ethnicity` | 6 | 1.55x | yes | **retracted** |
| 19 | ASAP `race_ethnicity*ell_status` | 10 | 2.14x | yes | **retracted** |
| 9 | PELIC `level_id` | 4 | 1.45x | yes | **holds** |
| 9 | PELIC `L1`, Arabic vs Turkish *(hand-picked, tested at z=3.65)* | 20 | 1.38x | yes | **holds** |
| — | ELLIPSE `race_ethnicity*grade` | 13 | 1.59x | yes | **retracted** |
| 9 | PELIC `L1`, tool's worst-vs-best German vs Hebrew | 20 | 2.27x | yes | **retracted** (n=52, n=61) |

This is now every multi-group claim in the document; none is taken on trust.

**The pattern is the reassuring one.** Everything with a mechanism behind it survives — the
144.93x vocabulary-channel spread, the threshold sweep's 6.93x, the disability gap and its
intersection. What the correction removes is precisely the class of claim it was built to remove:
marginal ratios found by crossing many-level axes and reporting the extremes. Three retractions,
all of them mine, all from this session, and none of them touching a result that had a mechanism
attached.

`Result 14` is worth noting specifically. It has five cells and a 45-pair correction, and it
clears it by a distance — a channel that flags 100.0% of one population and 0.7% of another is not
a marginal finding, and the correction says so. **A conservative test is only useful if it still
passes real effects**, and this is the evidence that it does.

## Result 21 — 46 real detectors, and their own calibration data says one threshold cannot work

Every result above measures untell's own lite tier, and the document has said repeatedly that this
generalises to nothing. **This one is about 46 real detectors, including GPTZero, QuillBot, RADAR,
Binoculars and Fast-DetectGPT**, and it needs no access to any of them.

[RAID](https://github.com/liamdugan/raid)'s public leaderboard requires every submission to
publish, for each of eight text domains, **the threshold at which that detector's false-positive
rate on human-written text equals 5%**. The calibration is per domain by construction —
`find_threshold` in `raid/evaluate.py` fits it separately on each domain's human, unattacked
texts. So the numbers are the detectors' authors' own answer to: *what do I have to set my
threshold to, on this kind of writing, to accuse 5% of innocent people?*

**If a detector were domain-stable, those eight numbers would be nearly identical.** They are not.

| | span of the required threshold, across 8 domains, on a 0–1 scale |
|---|---|
| **median across 46 detectors** | **0.610** |
| span > 25% of the scale | 33 / 46 |
| span > 50% | 25 / 46 |
| span > 90% | 13 / 46 |

Named ones:

| detector | lowest domain | highest domain | span |
|---|---|---|---|
| RADAR | 0.0159 (recipes) | 0.9984 (reviews) | **0.982** |
| RoBERTa (ChatGPT) | 0.0055 (abstracts) | 0.9986 (books) | 0.993 |
| QuillBot | 0.0001 (abstracts) | 0.9359 (reviews) | 0.936 |
| **GPTZero** | **0.0033 (reddit)** | **0.7797 (poetry)** | **0.776** |
| Fast-DetectGPT | 0.7296 | 0.9200 | 0.190 |
| **Binoculars** | 0.0787 (abstracts) | 0.1091 (reviews) | **0.030** |

**What this means.** These tools ship *one* threshold. A student gets one score and one verdict.
But their own submitted calibration says that holding the false-positive rate at 5% requires a
threshold that moves across most of the score range depending on what kind of text it is given. A
single deployed threshold therefore cannot hold a uniform false-positive rate — it is necessarily
close to right for one or two domains and wrong for the rest, and "wrong" here means a
false-accusation rate that is some unknown multiple of the advertised one.

This is [Result 13](#result-13--raising-the-threshold-cuts-the-error-rate-and-widens-the-gap)'s
finding — that an operating point which looks fine in aggregate is not fine per group — established
on commercial and research detectors that actually accuse people, from numbers their own authors
published.

**Reproduce it yourself, free.** This is a shipped command, not an ad-hoc script:

```bash
untell-detector-calibration report            # from the committed snapshot, offline
untell-detector-calibration report --fetch    # re-read the live leaderboard first
```

`--fetch` is a blobless, non-cone sparse checkout of *only* the 46 `results.json` files — 205 MB
against 3.4 GB for the full repository, because the sibling `predictions.json` files carry a score
per example. No API key, no GPU, no gated dataset, no account. A fetch failure falls back to the
snapshot rather than dying, so the numbers reproduce on a machine with no network at all.

**It is not an artifact of the 5% target.** RAID publishes the same calibration at a 1%
false-positive target, and the finding survives: median span **0.551** against 0.610, with 24
detectors over half the scale instead of 25. `untell-detector-calibration report --target 0.01`
reproduces it.

**Two things keep it honest.** The spread is *not* universal: **Binoculars needs a span of 0.030**,
and is genuinely domain-stable. That one detector behaves well is what makes the other 45
credible rather than an artifact of the method. And the domains are ordered consistently —
averaged over all 46 detectors, `recipes` needs the most permissive threshold and `books` and
`reviews` the strictest, which is a property of the text rather than of any one model.

**What it does not show.** RAID's domains are text *types*, not writer groups, so this is the
generalisation of Result 13 and not of Results 19–20. And a large span is not itself a measure of
harm — it says the calibration is domain-specific, not what any particular deployment's error rate
actually is. Establishing that needs the score distributions, which the leaderboard does not
publish. The dataset itself is hosted at `raid-bench.xyz`, which this environment's egress policy
denies; only the leaderboard submissions travel with the repository.

## Result 22 — the same leaderboard on attacks: a third of the field is one line of code from collapse

RAID's submissions also publish detection accuracy at a fixed 5% false-positive rate for every
combination of eight domains, eleven generator models and twelve adversarial attacks — 10,749 rows
per detector. Two things fall out, and the first is a lesson about aggregates that this document
has taught before and still nearly got wrong.

**Attack effectiveness, mean across ~43 detectors, at a fixed 5% FPR:**

| attack | mean accuracy | | attack | mean accuracy |
|---|---|---|---|---|
| **homoglyph** | **72.5%** | | article deletion | 86.3% |
| paraphrase | 82.1% | | perplexity misspelling | 87.6% |
| zero-width space | 84.2% | | insert paragraphs | 87.8% |
| synonym | 84.8% | | number swap | 88.6% |
| upper/lower | 85.0% | | alternative spelling | 88.6% |
| whitespace | 85.4% | | *(no attack)* | *89.2%* |

**But the mean is the wrong statistic and it hides the shape.** Per detector, the median loss to
homoglyph substitution is **0.7%**. The distribution is bimodal:

| | detectors |
|---|---|
| effectively immune (loses < 2 points) | **23 / 43** |
| loses > 20 points | **14 / 43** |

| detector | clean | homoglyph | loses |
|---|---|---|---|
| AIDetector.review | 90.6% | **4.3%** | 86.3 |
| e5-small-lora | 93.9% | 11.1% | 82.7 |
| BERT-tiny-4M | 91.1% | 27.5% | 63.6 |
| **Binoculars** | 79.0% | 36.1% | **42.9** |
| RoBERTa (ChatGPT) | 42.5% | **0.0%** | 42.5 |
| Desklib v1.01 | 94.9% | 99.7% | *−4.9* |

Homoglyph substitution — swapping Latin characters for identical-looking Cyrillic or Greek ones —
is defeated by Unicode normalisation before tokenisation, which is one line of code. **A third of
the field has not written it**, and for those detectors the attack is not a degradation but an
erasure: two drop below 5% and one to zero. For the other 23 it costs nothing at all.

**And robustness does not transfer.** Binoculars is the most domain-stable detector in
[Result 21](#result-21--46-real-detectors-and-their-own-calibration-data-says-one-threshold-cannot-work)
— a threshold span of 0.030 where the median is 0.610 — and is among the *most* homoglyph-
vulnerable here, losing 42.9 points. Being well calibrated across text types says nothing about
surviving a character swap.

**This corrects something in this repository's own census.** `docs/humanizer-census.md` treats
`unicode-trickery` as a marginal category, and
[the survey](research-tooling-survey.md) noted that five of six such repos in the re-run were
general steganography tools "with nothing to do with the AI-detector question". On the evidence
here that dismissal was too quick: hidden-character manipulation is the *most* effective attack in
RAID's suite against the detectors it beats. The census was right that those particular repos were
built for covert communication rather than evasion, and wrong to treat the mechanism as
uninteresting.

**Generator detectability, no attack, mean across 44 detectors:**

| generator | detected | | generator | detected |
|---|---|---|---|---|
| cohere | **80.4%** | | gpt4 | 89.9% |
| mpt | 83.3% | | gpt3 | 91.9% |
| mistral | 83.6% | | mistral-chat | 93.6% |
| cohere-chat | 87.5% | | chatgpt | 93.8% |
| gpt2 | 89.3% | | **llama-chat** | **94.7%** |

**Instruction tuning makes text more detectable, consistently.** Every base/chat pair moves the
same way: mistral 83.6% → mistral-chat 93.6%, mpt 83.3% → mpt-chat 90.0%, cohere 80.4% →
cohere-chat 87.5%. And the strongest models are not the hardest to catch — GPT-4 is detected at
89.9% while base Cohere sits at 80.4%. Whatever these detectors key on, RLHF adds it rather than
removing it, which is consistent with
[Result 14](#result-14--the-two-channels-rank-the-populations-in-nearly-opposite-orders-and-that-explains-result-12)
finding this repository's own detector keyed to a register rather than to machine provenance.

*Reproduce: `untell-detector-calibration report --fetch` pulls the same leaderboard; the attack
and generator tables come from the `scores` field of each submission.*

## Result 23 — every number on that leaderboard assumes a calibration step nobody deploys

The last three axes of RAID's `scores` field, and then the thing that reframes all of it.

**Decoding and sampling make text harder to catch.** Clean text, 5% FPR, mean across ~43 detectors:

| | detected | | | detected |
|---|---|---|---|---|
| greedy decoding | 92.5% | | no repetition penalty | 90.5% |
| **sampling** | **85.8%** | | **repetition penalty on** | **86.8%** |

Both point the same way as [Result 22](#result-22--the-same-leaderboard-on-attacks-a-third-of-the-field-is-one-line-of-code-from-collapse)'s
generator finding: whatever makes text *more predictable* makes it more detectable. Greedy
decoding and no repetition penalty both raise predictability, and both cost the writer about 4–7
points of cover.

**A negative result worth keeping.** A standard criticism of detection papers is that AUROC
flatters a detector relative to its behaviour at a usable operating point. On this benchmark it
does not: median AUROC 0.984 against median accuracy 0.972 at a 5% false-positive rate, and
exactly **one** detector of 43 has AUROC above 0.90 while scoring under 75%. The critique is
sound in general and does not apply here, and saying so costs nothing.

**Now the reframing.** Those accuracy figures are excellent — a median detector catches 97.2% of
machine text while accusing 5% of humans. That looks like a solved problem. It is not, and the
reason is in RAID's own evaluator:

```python
def run_evaluation(..., per_domain_tuning=True, ...)   # raid/evaluate.py:226
```

**Every published figure is computed with a threshold fitted separately on each domain.** RAID
takes the human, unattacked texts of one domain, finds the threshold that puts *that domain's*
false-positive rate at 5%, and scores that domain with it. Then the next domain, with its own
threshold.

No deployed detector does this. Turnitin does not ask what kind of document it is given and swap
thresholds; a student submits an essay and gets a score. And
[Result 21](#result-21--46-real-detectors-and-their-own-calibration-data-says-one-threshold-cannot-work)
measured what those per-domain thresholds actually look like: a median span of **0.610 of the
score range** across eight domains.

So the leaderboard numbers are an **upper bound achievable only with per-domain calibration**, and
the calibration they assume is exactly the thing whose absence Result 21 measures. A detector
advertising 97% accuracy at a 5% false-positive rate earned that figure under conditions its users
do not have.

**What this does not say.** It does not quantify the shortfall. Converting a threshold span into a
deployed error rate needs the score distributions, which the leaderboard does not publish and the
dataset host is behind this environment's egress policy. The claim here is narrow and, within it,
firm: *the published numbers assume per-domain calibration, deployment does not provide it, and
the gap between those thresholds is large.*

## Result 24 — the missing half, measured: the abstention works where the text is obviously foreign, and fails where it is not

Every result above this one measures false positives, because this repository had no corpus pairing
human and machine text. [M4](https://github.com/mbzuai-nlp/M4) (SemEval-2024 Task 8) ships one in
its GitHub repository — a prompt, the human answer and a machine answer per record, labelled by
generator and domain, in eight languages. 4,993 rows, balanced by construction, lite tier at the
shipped 0.30 threshold.

> **This result was published wrong and is restated from a re-measurement.** The first version
> reported a 99.6% false-negative rate on Urdu and concluded the detector "is not operating at all,
> and it does not say so". The second half was false, and the error was in this repository's
> *instrument*, not its product — see
> [the defects table](#defects-these-measurements-exposed-in-the-instrument). The numbers below are
> the corrected ones.
>
> **And the German and Indonesian rates below no longer describe the shipped detector.** They are
> what it did *before* this result; the fix they prompted landed the same day and is described at
> the end. They are kept as measured because a defect and its repair are only legible together —
> the fix's threshold is derived from these numbers, and re-measuring them away would leave the
> constant unexplained.

**The detector refuses to answer on Urdu, and is right to.** Counted separately from the rates,
because a refusal is neither a hit nor a miss:

| language | detector produced no score |
|---|---|
| **Urdu** | **495 / 496 — 99.8%** |
| German | 0 / 500 |
| Indonesian | 0 / 498 |
| English | 0 / 3499 |

`score_text` marks those results `scored: False` and warns that `max` is a placeholder;
`untell/scripts/verify.py` reads that flag and reports `ai: None` instead of a pass. The safety
behaviour is real and it works.

**On the 4,498 rows it did score: false-positive rate 28.6%, false-negative rate 34.1%.**

| language | FPR | FNR | n |
|---|---|---|---|
| English | **36.0%** | 21.4% | 1750 / 1749 |
| Indonesian | 4.0% | **74.8%** | 248 / 250 |
| German | 1.6% | **82.8%** | 250 / 250 |
| Urdu | *insufficient — 1 row survived* | | |

FPR disparity 22.5x, FNR disparity **3.87x**, both separated after the selection correction.

**And here is the finding, which is the opposite of the one I first published.** The abstention is
**script-gated, not language-gated**. The lite tier's word regex is `[A-Za-z']+`: Arabic script
yields no tokens, the detector opts out, and the user is told. German and Indonesian tokenise
perfectly well — so the detector scores them with full confidence and **misses 83% and 75% of the
machine-written text respectively**, against 21% for English.

So the guard fires exactly where the text is *obviously* foreign and stays silent exactly where it
is not. Latin-script non-English is the dangerous case: it looks English enough to tokenise and is
not English enough to score. Nothing in the output distinguishes a confident German verdict from a
confident English one.

### What was done about it

The lite tier now **abstains on text it cannot read**, rather than returning a floor score. The
gate is the measurement above, turned into a constant: text of 40+ words whose common-word ratio
falls below **0.15** gets no score and a warning, because English's 1st percentile is 0.1765 and
German's *median* is 0.0323.

The ratio alone was not enough, which the other four M4 languages showed. Cyrillic, Arabic and Han
text carries too few `[A-Za-z']+` tokens to reach the ratio test's 40-word floor, so a ratio-only
gate still scored **18% of Bulgarian and 26% of Russian** — the rows with enough transliterated
names, numerals or English loanwords to clear the floor while being no more readable than the rest.
Script and ratio are each necessary: script alone passes German, ratio alone passes Russian.

Measured across all eight M4 languages, before and after:

| language | script | abstains before | after |
|---|---|---|---|
| English | Latin | 0.0% | **0.0%** |
| German | Latin | 0.0% | **99.7%** |
| Indonesian | Latin | 0.0% | **99.7%** |
| Bulgarian | Cyrillic | 18.0% | **99.0%** |
| Russian | Cyrillic | 26.3% | **99.3%** |
| Arabic | Arabic | 12.3% | **100.0%** |
| Urdu | Arabic | 99.7% | **99.7%** |

`untell/languages.py` had already reached this conclusion for the tells catalogue — it prints
*"the text is mostly non-Latin script — a score of N tells means the patterns did not apply, NOT
that the text reads as human"*. The same sentence was true of this detector, and it was not saying
it.

The 0.5% of English that now abstains gets *"no evidence"* instead of a number, which is the
recoverable direction of the error. **No result in this document moves**: the minimum common-word
ratio is 0.2899 on ELLIPSE, 0.4207 on ASAP and 0.2743 on Liang, all far above the cut, and a test
holds the constant below 0.2743 so a future tightening cannot silently revise the record.

One thing the first version of the gate got wrong, caught by two tests that already existed:
returning "no signal" whenever the *English* channel was blind also threw away degenerate
repetition, which is machine-like in any language — `"test test test …"` scores 1.0000 on that
term where real German and Indonesian prose score 0.0000. The gate now reports that term alone
rather than abstaining.

### By domain

| domain | FPR | FNR |
|---|---|---|
| arxiv abstracts | **61.6%** | 17.8% |
| reddit | 28.4% | **1.2%** |
| peerread reviews | 14.0% | 45.4% |
| wikipedia | 6.2% | 43.6% |
| Indonesian newspaper | 4.0% | 74.8% |

FNR disparity **62.33x**, separated. Reddit machine text is caught almost perfectly; Indonesian
newspaper text almost never. And **61.6% of human-written scientific abstracts are flagged** —
[Result 10](#result-10--the-largest-disparity-here-is-not-demographic-it-is-professional-vs-student)'s
formal-register finding, on a fourth corpus.

### By generator — reported with its confound

| generator | FPR | FNR |
|---|---|---|
| BLOOMZ | 61.6% | 39.6% |
| text-davinci-003 | 61.6% | **13.7%** |
| GPT-3.5-turbo | 21.3% | 32.6% |
| Cohere | 14.0% | 16.0% |
| FLAN-T5 | 14.0% | **74.8%** |

**The FPR column here is not about generators.** Each M4 file pairs one generator with one domain,
so the human halves differ: BLOOMZ and davinci both sit on arxiv, and their 61.6% is arxiv's 61.6%
exactly. Only FNR is a statement about generators, and FLAN-T5's output is missed 74.8% of the time
against davinci's 13.7% — a **5.48x** gap surviving correction, and the same direction as
[Result 22](#result-22--the-same-leaderboard-on-attacks-a-third-of-the-field-is-one-line-of-code-from-collapse)'s
finding across 46 detectors that instruction tuning makes text more detectable.

## Result 25 — after the gate: the domain gap is real within one language, and so is the generator gap

[Result 24](#result-24--the-missing-half-measured-the-abstention-works-where-the-text-is-obviously-foreign-and-fails-where-it-is-not)
measured the detector before it learned to abstain. This is the same corpus through the shipped
one, and it is what the tool now actually does.

**Abstention, 5,193 rows across seven languages:**

| ar | bg | de | id | ru | ur | **en** |
|---|---|---|---|---|---|---|
| 100.0% | 98.2% | 99.8% | 99.7% | 99.2% | 99.7% | **0.1%** |

Six languages are now **"not reported"** rather than carrying a wrong rate. That is the whole
change: the instrument declines instead of answering. Four English rows of 2,799 abstain too, and
those are the price.

**English, 2,808 rows: false-positive rate 37.4%, false-negative rate 21.8%.** Every figure below
is English-only, because that is the only language this detector still claims to speak.

### The domain gap is not carried by the language mix

| domain | FPR | FNR |
|---|---|---|
| arxiv abstracts | **62.5%** | 18.7% |
| reddit | 30.5% | **1.5%** |
| peerread reviews | 16.0% | **45.0%** |
| wikipedia | 11.2% | 5.0% |

FNR disparity **30.0x**, separated, entirely within English. Result 24's domain spread survives the
removal of every non-English row, so it was never an artifact of the corpus's language mix — and
62.5% of human scientific abstracts are still flagged.

### Crossing domain with generator turns a disclaimed number into a real one

Result 24 reported generator rates with a warning that the FPR column was confounded: each M4 file
pairs one generator with one domain, so BLOOMZ and davinci both showed arxiv's false-positive rate.
Crossing the two axes does better than warning — **it isolates the cases where the confound does
not apply.**

| cell | FPR | FNR |
|---|---|---|
| **arxiv** × GPT-3.5-turbo | 62.5% | **0.0%** |
| **arxiv** × davinci | 62.5% | 13.6% |
| **arxiv** × BLOOMZ | 62.5% | **42.5%** |
| **peerread** × Cohere | 16.0% | 15.5% |
| **peerread** × FLAN-T5 | 16.0% | **74.5%** |
| wikipedia × GPT-3.5-turbo | 11.2% | 5.0% |
| reddit × GPT-3.5-turbo | 30.5% | 1.5% |

Read the first three rows together: **same domain, same human text, same 62.5% false-positive
rate — and false negatives running from 0.0% to 42.5%.** The next two do it again on peerread,
15.5% against 74.5%. Domain is held constant, so those are generator effects and nothing else.

And the last three rows show the reverse, on the one generator that appears in more than one
domain: GPT-3.5-turbo is missed 0.0% of the time on arxiv, 1.5% on reddit and 5.0% on wikipedia.
Generator held constant, domain varying, and the effect is small.

So the two factors are separable after all, and they are not the same size. **Which model wrote the
text matters far more to this detector than what kind of text it is** — 0.0% to 74.5% across
generators, against 0.0% to 5.0% across domains for a fixed generator. That is the opposite of
what the uncrossed table suggested, where the domain column carried the larger visible spread
purely because it was standing in for the generator behind it.

The generators also rank the way [Result 22](#result-22--the-same-leaderboard-on-attacks-a-third-of-the-field-is-one-line-of-code-from-collapse)
predicted across 46 other detectors: the instruction-tuned GPT-3.5-turbo is caught almost
perfectly, and the older, weaker FLAN-T5 and BLOOMZ are the ones that get through.

## Result 26 — no usable operating point, replicated on nine times the data

[Result 15](#result-15--the-shipped-lite-tier-is-a-ranking-signal-not-an-accusation-instrument)
concluded from 391 paired Liang essays that the lite tier is a ranking signal and not an accusation
instrument: AUROC 0.8012, and no threshold with tolerable error on both sides. M4 tests that on
**3,493 paired English texts** — nine times the data, seven generators, four domains, and no
overlap with the corpus the original claim came from.

**AUROC 0.7745.** The full sweep, human against machine on the same prompts:

| threshold | FPR (human) | FNR (machine) | usable? |
|---|---|---|---|
| 0.20 | 70.8% | 10.6% | no |
| **0.30** *(shipped)* | **36.1%** | **21.4%** | no |
| 0.40 | 15.4% | 40.2% | no |
| 0.45 | 9.7% | 53.9% | no |
| 0.50 | **5.2%** | **69.6%** | no |
| 0.60 | 0.5% | 92.3% | no |
| 0.70 | 0.0% | 99.5% | no |
| 0.775 | 0.0% | **99.9%** | no |

Nothing on that curve is a defensible operating point. The best available trade sits near 0.50 —
accuse one human in twenty, and miss seven machine texts in ten. Push false accusations to zero and
the detector stops catching anything at all: at 0.70 it has flagged **0 of 1,744** humans and
**8 of 1,749** machine texts.

**The replication is the point.** 0.8012 on Liang, 0.7745 on M4 — two independent corpora, one of
essays and one of abstracts, reviews, wiki articles and forum posts, from seven generators rather
than one, agreeing to within 0.03. The conclusion was not an artifact of the first corpus, and it
was not an artifact of GPT-4-polished text.

It also sets a ceiling on what any threshold change could achieve. [Result 11](#result-11--the-threshold-that-would-make-the-lite-tier-safe-on-student-writing)
gives the threshold that would make the lite tier safe on student writing — 0.775 for a 1%
false-positive rate. On this corpus 0.775 misses **99.9%** of machine-written text. There is no
setting of one number that makes this detector both safe and useful, which is
[Garland's structural argument](https://arxiv.org/abs/2603.20254) arriving as an empirical curve.

## Result 27 — the same question, asked of ourselves: consistently calibrated, consistently wrong

[Result 21](#result-21--46-real-detectors-and-their-own-calibration-data-says-one-threshold-cannot-work)
measured 46 real detectors needing thresholds that span a median **0.610** of their score range to
hold a 5% false-positive rate across text types, and used it to argue their published accuracy
assumes a calibration nobody deploys. It is only fair to ask the same of this repository's own
detector, on every human corpus it can reach.

| corpus | threshold for 5% FPR | FPR at the shipped 0.30 |
|---|---|---|
| PELIC — adult ESL, Pittsburgh | 0.6866 | 85.5% |
| ELLIPSE — ESL student essays | 0.6707 | **98.0%** |
| ASAP — US school essays | 0.6549 | 89.0% |
| Liang — TOEFL / 8th grade / CS224N | 0.6342 | 79.4% |
| M4 — arxiv, wiki, reddit, peerread | **0.5126** | 37.1% |

**Span 0.174**, against RAID's 0.610 median. On this axis the lite tier behaves well — nearer
Binoculars' 0.030 than RADAR's 0.982 — and it does **not** have the defect Result 21 documents in
two thirds of the field.

**Read the comparison honestly, though.** RAID's eight domains include poetry, recipes and books;
these five are all academic, student or web prose, four of them student writing. A narrower range
of text produces a narrower range of thresholds, so this number flatters the lite tier and is not
a like-for-like 0.174-against-0.610.

**And the stability is around the wrong point.** Every corpus here wants a threshold between
**0.51 and 0.69** for a 5% false-positive rate. The tool ships **0.30**. That is not a
corpus-specific tuning problem — the four student corpora agree to within 0.05 — it is one number
being roughly 0.3 too low everywhere at once.

Which is a more useful statement of the threshold problem than
[Result 11](#result-11--the-threshold-that-would-make-the-lite-tier-safe-on-student-writing) made
from ELLIPSE alone: the fix is not *per corpus*, it is *global*, and it is large. It also does not
rescue the detector, because [Result 26](#result-26--no-usable-operating-point-replicated-on-nine-times-the-data)
prices the move — at 0.60 the false-negative rate is already 92.3%. The lite tier is consistently
calibrated, and consistently calibrated to a point where it accuses most human writers; moving it
to where it stops doing that is moving it to where it detects nothing.

## Result 28 — length is not the hidden variable

None of Results 1–27 control for document length, and the tool's own output warns that short text
is unreliable. If false positives tracked length, and the corpora differ in length — they do, from
Liang's ~300 words to ASAP's ~380 — then some of what this document calls a corpus or subgroup
effect would be a length effect wearing a label.

1,500 ASAP essays, lite tier at the shipped 0.30:

| words | n | FPR | 95% CI |
|---|---|---|---|
| 0–200 | 151 | 89.4% | 83.5–93.4% |
| 200–300 | 404 | 89.6% | 86.2–92.2% |
| 300–400 | 374 | 88.5% | 84.9–91.4% |
| 400–550 | 384 | 90.9% | 87.6–93.4% |
| 550+ | 187 | 87.2% | 81.6–91.2% |

Flat. Every interval overlaps every other, and the correlation between length and score is
**r = −0.136** across 1,500 essays — weak, and in the direction that would *reduce* rather than
create the reported effects.

**This is a control that could have cost a lot and did not.** A strong length effect would have
put every cross-corpus comparison in this document in question. It is reported because a null
result from a test that could have gone the other way is evidence, and because the alternative —
not running it — leaves the same doubt sitting silently under every table above.

Within the range these corpora occupy, at least: 151 essays under 200 words is the thinnest band,
and nothing here speaks to the very short text the tool already refuses to judge.

## What these results do not establish

- **Nothing about a transformer *detector*.** Result 8 measures a transformer *language model*,
  which is the mechanism, not a shipped detector. No commercial or neural detector was run.
- **Nothing about any commercial detector.** Those need keys and are out of scope here exactly as
  they are in `free-ceiling-measured.md`.
- **No clean professional-vs-student contrast.** Result 10 measures published prose, but genre,
  editing and task vary alongside the population, and the effect sizes on ASAP are already
  materially smaller than on ELLIPSE, so domain sensitivity is demonstrated rather than assumed.
- **Half of the audit went unmeasured for as long as it did because I looked in the wrong place.**
  Results 1–14 are false-positive rates. This section used to say equalised odds was blocked for
  want of a corpus pairing human and machine text from the same writers on the same prompts, and
  that RAID, MAGE and HC3 — the nearest candidates — are HuggingFace-hosted and unreachable here.
  All of that was true and the conclusion drawn from it was wrong: **Liang ships the machine half
  in the same repository as the human half**, and two results had already been computed from the
  directory next to it. [Results 15 and 16](#result-15--both-error-rates-and-why-result-11s-threshold-recommendation-was-wrong)
  are what it showed, including that this document's own threshold recommendation was for a
  setting that catches nothing.

  What is still missing is narrower, and this time it was **checked rather than assumed** — twice
  in one day a claim of unreachability here turned out to be a claim nobody had tested. The paired
  corpus covers **two populations**, CS224N and college admission. TOEFL has no machine
  counterpart, so the population this document is most concerned with — non-native English
  writers — is exactly the one whose false-negative rate cannot be measured. Searched on
  2026-09-01, all reachable by `git clone` through this environment's proxy:

  | source | machine-written half? |
  |---|---|
  | `Weixin-Liang/ChatGPT-Detector-Bias` | yes, but CS224N and college essays only — no TOEFL |
  | `scrosseye/ELLIPSE-Corpus` | no — human essays only |
  | `scrosseye/ASAP_2.0` | no — human essays only |
  | `scrosseye/persuade_corpus_2.0` (25k essays, ELL-labelled) | no — human only, and the CSVs are on Google Drive |
  | RAID / MAGE / HC3 | HuggingFace unreachable here — **verified**, `curl` fails to connect, not a policy 403 |

  So the gap is real rather than unexamined. Inventing a pairing by scoring TOEFL humans against
  another domain's machine text would measure the distance between two datasets and report it as
  a property of a detector, which is the error this whole document is built to avoid. **The
  measurement that would most change these conclusions is a machine-written counterpart to TOEFL
  essays, and it is a data problem, not a tooling one** — `--corpus liang-paired --odds` would
  report it the day such a corpus exists.

- **Nothing about any individual document.** Every rate here describes a *detector*. A per-group
  false-positive rate says nothing about whether a particular text was machine-written, and must
  never be quoted at a person. The tool prints that line in its own output.

## Defects these measurements exposed in the instrument

Kept because a measurement tool that hides its own bugs is the thing this repository exists to
argue against. All are fixed and pinned by tests.

| defect | how it showed | what it would have caused |
|---|---|---|
| **an abstention was read as a wrong answer** | `score_text` returns `max: 0.0` with `scored: False` when every detector opts out; this instrument read the placeholder as a score | **Result 24's headline, published wrong.** A 99.6% false-negative rate on Urdu that was 99.8% abstentions. The product says so twice and `verify.py` already honoured it; the audit did not |
| **`separated` ignored that the extremes were selected** | ELLIPSE's 13-cell crossed axis separated at 1.59x while no single axis on that corpus separates at all | **Result 19's headline.** Reported, then retracted by the fix — a worst-vs-best pick from 78 pairs judged against a 95% interval |
| Result 12 generalised from one population | a second machine-edited arm reversed it, d = +0.646 | "LLM editing makes text look human" as a general claim, from n=1 population |
| equalised odds reported no pooled pair | a 100% false-negative rate sat unremarked beside ordinary per-group rows | a threshold that catches nothing reading as a threshold that is safe |
| an axis no row carries rendered empty | `Overall` beside two real axes, groups `{}` | an empty heading reads as "looked here, found nothing" |
| ablation assumed a numeric band axis | `--band-axis population` printed "no rows fell into a band" | a real 145x disparity looking like an absence of data |
| separation computed only for two bands | five populations reported 145x beside `separated: null` | the largest disparity in the project quoted with no significance attached |
| `NA` treated as a subgroup | ASAP codes missing demography as `"NA"`; 4,019 rows scored 19.1% against 30–38% for real groups | missing data became the "best" arm and produced a phantom **2.01x** disparity |
| `--csv` dropped label columns | `ell_status` vanished, the axis rendered as a bare heading | an empty heading reads as "no disparity here" |
| confident rows broke at scale | 3/3 on 23 repos became 6/9 on 111 | a vendor rule matched a repo's **own name** |
| delta inflated itself | 73 of 435 census names are not bare `owner/repo` | 85 "new" repos where the true figure was 97 of a larger sweep |
| monotonicity over-claimed | held-out split did not reproduce it | a 1.57x headline the data could not support |
| "perplexity" was a stoplist | a real LM pointed the other way | a mechanism story built on a misnamed proxy |

Four of the original six surfaced only by pointing the instrument at a corpus it was not built
around. That is the argument for the second corpus, restated as evidence — and the five added on
2026-09-01 make it twice over: every one of them surfaced on the *first run against a third
corpus*, four of them within an hour of that corpus becoming loadable. A measurement tool is
tested by the data it has not seen, and this one had been reporting confidently on two corpora
while carrying a branch that could not band a categorical axis and a report with no pooled rates
in it.

The top two rows are the ones worth keeping in view, because neither is a coding defect. Both are
inference defects, and both are the kind this document catches detectors making. A result measured
on one population was written up as a fact about language models, and it took a second population
to see — exactly as Result 2's monotonicity claim needed a held-out split. And a comparison
between the two extremes of thirteen post-hoc cells was judged against the yardstick for a
pre-registered pair, which is the classic way to find something that is not there.

The first of them is the sharpest example this document has of a defect the *instrument* had and
the *product* did not. `untell/scripts/verify.py` already read the `scored` flag and reported
`ai: None` rather than a clean pass, with a comment explaining that fabricating one on a verdict
surface is the worst possible place to do it. The same check, in the same repository, written by
someone thinking about the same failure — and the audit module went straight past it to
`result["max"]`.

The second one was caught *after* Result 19 had been written, committed and pushed. It survived a
full write-up, a measurement record and a strategy citation before the arithmetic of the
correction was worked out, which is worth being uncomfortable about: nothing in the process
flagged it, and only re-deriving the statistic did.
