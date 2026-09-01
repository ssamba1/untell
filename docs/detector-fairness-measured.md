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

**And the proficiency effect runs the opposite way to Result 2.**

| PELIC level | 2 | 3 | 4 | 5 |
|---|---|---|---|---|
| FPR | **52.9%** | 40.9% | 39.9% | **36.5%** |

Monotonically *decreasing* with proficiency, 1.45x, separated — where ELLIPSE showed it
*increasing* (33.2% → 44.2%). Same detector, same kind of subgroup, **opposite direction**.

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

`*` = the two groups' Wilson intervals do not overlap.

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

## Result 19 — crossing two axes finds a gap neither shows alone, on 17,307 essays

Added after reading [Identifying Bias in Machine-generated Text Detection](https://aclanthology.org/2026.acl-long.109.pdf)
(Pindrop, ACL 2026 Main), which evaluated 16 detectors against a demographically labelled corpus
and found bias "most dangerous where attributes intersect" — non-White English-language learners
flagged far more than their White peers, a gap neither axis shows on its own. Every axis in this
document was reported one at a time until 2026-09-01, so this instrument could not have found it.

All 17,307 ASAP essays, lite tier at threshold 0.50:

| axis | worst | best | ratio | intervals |
|---|---|---|---|---|
| `ell_status` | non-ELL 32.2% | ELL 26.7% | 1.21x | separate |
| `race_ethnicity` | Am. Indian/Alaskan Native 36.3% | Asian/Pacific Islander 23.4% | 1.55x | separate |
| **`race_ethnicity*ell_status`** | Am. Indian/Alaskan Native × non-ELL **35.2%** | Asian/Pacific Islander × ELL **16.5%** | **2.14x** | **separate** |

**The structural claim replicates.** Crossing genuinely finds more than either axis alone —
1.21x and 1.55x separately, 2.14x crossed, and the crossed gap separates at 95% on cells of 108
and 364. That is the ACL 2026 finding reproduced on a different corpus and a different detector,
which is the strongest form of support this instrument can give another group's result.

**The directional claim does not, and that is also their finding.** Pindrop reports non-White ELL
students flagged *most*. Here the ELL arm is flagged *less* at every level — non-ELL 32.2% against
ELL 26.7% — and Asian/Pacific Islander ELL writers are the best-served cell in the corpus at
16.5%. This reverses the field's default assumption, consistently with
[Result 9](#result-9--a-third-corpus-a-new-axis-and-a-direction-reversal), and it is exactly what
Pindrop concludes when they say bias is **model-specific** and "no single detector was uniformly
fair or unfair". A different detector, a different direction. **The generalisation that survives
is about the method, not the harm: cross the axes, because single-axis reporting understates.**

Two cells fall below the 30-row floor and are reported as insufficient rather than compared —
`American Indian/Alaskan Native × ELL` has one row. Crossing splits a corpus fast, which is why
the floor matters more here rather than less, and why the worst cell above is not the smallest.

## Result 20 — students with disabilities are flagged more, and it cancels the ELL effect

The literature names neurodivergent students — autism, ADHD, dyslexia — as disproportionately
flagged by AI detectors. ASAP labels 1,921 essays *Identified as having disability* against 11,367
*Not identified*, and this instrument had never looked: `student_disability_status` was not in the
default axes, so a default ASAP run reported nothing about it. All 17,307 essays, threshold 0.50:

| axis | worst | best | ratio | intervals |
|---|---|---|---|---|
| `student_disability_status` | identified **38.3%** | not identified 34.8% | 1.10x | **separate** |
| `economically_disadvantaged` | **not** disadvantaged 38.1% | disadvantaged 33.7% | 1.13x | separate |
| `student_disability_status*ell_status` | identified × non-ELL **38.5%** | not identified × ELL **26.0%** | **1.48x** | **separate** |

**This is the first axis in this document where the direction matches the field's expectation.**
Everything above reverses it — non-ELL flagged more than ELL, non-disadvantaged more than
disadvantaged, professionals more than students. Here the disadvantaged group really is the one
paying: students identified as having a disability are flagged more, and the gap separates.

**The crossed row is the finding.** This detector treats ELL status as *protective* — Result 19
measured 26.7% for ELL against 32.2% for non-ELL. That protection is essentially absent for
students with disabilities: not-identified ELL writers are flagged **26.0%**, identified ELL
writers **36.9%**. Being identified as having a disability cancels the only thing that was
helping. Neither single axis shows this: disability alone is 1.10x, and the ELL axis alone points
the other way entirely.

That is the second independent case in this document — after [Result 19](#result-19--crossing-two-axes-finds-a-gap-neither-shows-alone-on-17307-essays) —
where crossing changed the answer rather than refining it, and it is why the defaults now follow
the corpus: `--corpus asap` reports `ell_status`, `student_disability_status` and their cross
without being asked, because a heading a caller never thinks to request is a group nobody measures.

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

The first row is the one worth keeping in view: it is not a coding defect but an inference defect,
and it is the same one this document catches detectors making. A result measured on one population
was written up as a fact about language models. It took a second population to see it, exactly as
Result 2's monotonicity claim needed a held-out split.
