# Measured: who a detector fails, on 21,211 essays nobody wrote with a machine

Every number here is a **false-positive rate on known-human writing**. The corpora are essays by
real students, so a flag is an error by construction — there is no labelling to dispute and no
ground truth to argue about. That is what makes false positives the cleanest measurement available
against a detector, and it is the only regime this document reports.

Companion to [`strategy-the-audit-position.md`](strategy-the-audit-position.md), which argues why
this is the work. This file is the evidence, in the shape
[`free-ceiling-measured.md`](free-ceiling-measured.md) uses: numbered results, intervals attached,
withdrawals kept visible.

**Reproduce anything below:**

```bash
untell-subgroup-audit --corpus ellipse --tier lite --sweep
untell-subgroup-audit --corpus asap --tier lite --by ell_status
untell-subgroup-audit --corpus ellipse --ablate
untell-ngram-lm train && untell-ngram-lm score --csv <corpus>.csv --by ell_status
```

Raw rows: `.claude/measurements.jsonl`, recipes `ellipse-*`, `asap-subgroup-fpr`,
`burstiness-formulation-robustness`, `true-ngram-perplexity-contrast`.

## The corpora

| | ELLIPSE | ASAP 2.0 |
|---|---|---|
| essays (≥60 words) | 3,904 train + 2,571 held-out | 17,307 |
| writers | **all** English language learners | mixed; 2,269 ELL, 14,798 non-ELL |
| task | independent writing | source-based writing |
| labels | proficiency, race, gender, SES, grade | ELL status, race, gender, SES, disability, grade |
| licence | CC BY-NC-SA 4.0 | CC BY 4.0 |
| vendored? | **no** — fetched on demand | **no** — fetched on demand |

Neither is committed. ELLIPSE's licence forbids it in an MIT package; ASAP's does not, but a 46 MB
CSV does not belong in a repository either.

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

## What these results do not establish

- **Nothing about a transformer detector.** Every route to weights was tried and blocked in the
  environment these were run in: huggingface.co and four mirrors, Google Drive, ONNX-on-GitHub,
  and pypi. Whether a modern neural detector learned the same correlation is **open**, and it is
  the single most valuable next measurement.
- **Nothing about any commercial detector.** Those need keys and are out of scope here exactly as
  they are in `free-ceiling-measured.md`.
- **Nothing outside US school-age writing.** Both corpora are US students in grades 6–12. Adult,
  non-US and professional writing are unmeasured, and the effect sizes on ASAP are already
  materially smaller than on ELLIPSE, so domain sensitivity is demonstrated rather than assumed.
- **Nothing about any individual document.** Every rate here describes a *detector*. A per-group
  false-positive rate says nothing about whether a particular text was machine-written, and must
  never be quoted at a person. The tool prints that line in its own output.

## Defects these measurements exposed in the instrument

Kept because a measurement tool that hides its own bugs is the thing this repository exists to
argue against. All are fixed and pinned by tests.

| defect | how it showed | what it would have caused |
|---|---|---|
| `NA` treated as a subgroup | ASAP codes missing demography as `"NA"`; 4,019 rows scored 19.1% against 30–38% for real groups | missing data became the "best" arm and produced a phantom **2.01x** disparity |
| `--csv` dropped label columns | `ell_status` vanished, the axis rendered as a bare heading | an empty heading reads as "no disparity here" |
| confident rows broke at scale | 3/3 on 23 repos became 6/9 on 111 | a vendor rule matched a repo's **own name** |
| delta inflated itself | 73 of 435 census names are not bare `owner/repo` | 85 "new" repos where the true figure was 97 of a larger sweep |
| monotonicity over-claimed | held-out split did not reproduce it | a 1.57x headline the data could not support |
| "perplexity" was a stoplist | a real LM pointed the other way | a mechanism story built on a misnamed proxy |

Four of the six surfaced only by pointing the instrument at a corpus it was not built around. That
is the argument for the second corpus, restated as evidence.
