# Roadmap — how untell becomes the best, and what "best" can honestly mean

Restored and rewritten 2026-08-05 against the [435-repo census](docs/humanizer-census.md). The
previous version was deleted on 2026-07-28 inside an unrelated commit, together with
`humanizer-research-report.md`, while the README, `CHANGELOG.md` and `why-best-open-repo.md` kept
linking to both.

**Honest framing.** "Best ever" is not "passes everything forever" — detectors update, disagree, and
re-score the same text differently. The goal is the best point on three axes at once:
**evasion strength × meaning integrity × trust (honest, reproducible numbers)**. No shipping tool
holds all three. That is the opening.

Legend: ✅ shipped · 🔜 buildable now · ⛔ needs a GPU · ❌ ruled out, with the measurement that ruled it out.

---

## Status — what is left, and who it is waiting on

Every item below is enumerated from the sections that follow, and
`tests/test_roadmap_status.py` fails if this table disagrees with them. A status summary that
drifts from the plan it summarises is worse than none, because it is the part people read.

**Nothing actionable without a decision from you remains open.**

| # | item | status | waiting on |
|---|---|---|---|
| 1 | `untell-audit` — every derivable claim re-checked in CI | ✅ done | — |
| 2 | Every category must prove it fires | ✅ done | — |
| 3 | Publish the negative results as a first-class artifact | ✅ done | — |
| 4 | Make the default configuration the good one | ✅ done | — |
| 5 | Retire or rehabilitate the dead weight | ✅ done — nothing retired, and the measurement says why | — |
| 6 | Finish the surgical objective | ✅ done — the competitor row stays faithful | — |
| 7 | LaTeX preserve-locking | ✅ done | — |
| 8 | BibTeX-aware verification | ✅ done | — |
| 9 | `.tex` round-trip | ✅ done | — |
| 10 | Structure-aware skipping | ✅ done | — |
| 11 | Refuse to fake non-English input | ✅ done | — |
| 12 | Per-language catalogue **registry** | ✅ done — additive, ships with English only | — |
| 13 | The per-language **catalogues** | 🔜 open | **people who speak those languages.** Not ours to write: Korean 번역체 calques and Chinese academic-register tells are not guessable from outside, and a catalogue needs the paired-corpus precision measurement every English figure has. [How to add one](CONTRIBUTING.md#adding-a-language). |
| 14 | `pip install untell` claims the top-level names `eval` and `training` | 📦 open | **your decision.** The fix is mechanical — move them under `untell/` — but it is 179 references across 47 files and breaks anyone importing `eval.ceiling` directly. A published package's import surface is not something to change in passing. |
| 15 | Surrogate distillation | ⛔ blocked | a GPU |
| 16 | RL-against-ensemble | ⛔ blocked | a GPU |
| 17 | Alignment rewriter | ⛔ blocked | a GPU |
| 18 | **The audit position** — false-positive rate by writer subgroup | ✅ done — instrument built, first measurement taken | — |

Three things are ruled out rather than pending, each with the measurement that ruled it out: raw
evasion strength against GPU-trained policies, adoption, and beating GPTZero / Originality /
Turnitin for free. They are in §1 and are not counted as open work.

---

## 0. What the competition actually is

The census read 435 of 1287 repos. The single most useful finding is what the field is *made of*:

| segment | n | what it means for us |
|---|---|---|
| prompt guides | 184 | a Markdown file instructing an LLM. No detector, no measurement, no tests |
| API wrappers | 75 | bills for someone else's humanizer |
| adversarial-perturbation | 39 | the real technical competition |
| rule-based rewriters | 38 | our weight class, mostly weaker |
| research code | 19 | stronger evasion, not products |
| fine-tuned models | 11 | the actual ceiling, GPU-bound |

**60% of the field either instructs a humanizer or resells one.** Star counts are therefore almost
uncorrelated with capability — the largest repo in the space is a 298k-star Chinese rewrite prompt.
Competing on "features" against that segment is meaningless; competing on *correctness* is where the
field is empty.

---

## 0b. ✅ The audit position — the move that changes the category

Full argument and evidence: [`docs/strategy-the-audit-position.md`](docs/strategy-the-audit-position.md).

The census measured whether this is the best *humanizer*. That is a category
[worth 0.3% of the field's attention](docs/what-would-make-this-the-top-repo.md) with a 413★
ceiling, and every lever inside it is now measured-and-dead, defended-by-nothing, or blocked on a
native speaker. The 2026-09-01 re-run found the field had split in two — humanizers chasing
evasion, and prose "slop linters" chasing quality with the same machinery — and that the census
had only ever counted the first branch.

Meanwhile this repo's own README leads with *detector auditing*, its headline is a false-positive
rate, and its rewriting loop is documented as the probe rather than the product. We were
benchmarking against the wrong field.

**The move: answer "who does this detector fail?"** — false-positive rate by writer subgroup, on
public learner corpora, at a detector's own shipped threshold.

The idea is **not** novel and the strategy doc says so: [BAID](https://arxiv.org/abs/2512.11505)
(AAAI 2026 workshop) benchmarks detector bias across seven sociolinguistic dimensions on 200k+
samples. What is missing is the instrument. BAID's subgroup text is **synthetic** — LLM
imitations of how a group writes — where ELLIPSE is real essays by real learners; no code
repository for BAID was findable; and of 435 repos in the census plus 131 in the re-run, **zero**
ship a tool a university could point at the detector it is about to license. Aequitas, AIF360 and
Fairlearn compute the right statistic and none is wired to a text detector. RAID, IMGTB and
`kinit-sk/mAO` rank accuracy or obfuscation strength, a different question. **The research exists;
the instrument does not.**

Built and measured 2026-09-01 (`untell-subgroup-audit`, `eval/subgroup_audit.py`, 28 tests,
ELLIPSE fetched not vendored because it is CC BY-NC-SA and this package is MIT). On 3,904
known-human ESL essays, where every flag is an error by construction:

- **Our own lite tier flags 97.4%** of them at its shipped 0.30 threshold, against a documented
  30% on conversational prose. Its threshold was tuned on a corpus that does not resemble the
  writers most likely to be accused.
- **False-positive rate rises with English proficiency** at the 0.50 operating point.
- **Replicated on held-out data.** Banding low (<=2.5) vs high (>=3.5) proficiency: 33.2% vs
  44.2% on the training split, **34.8% vs 43.0% on the 2,571-essay held-out split**, separated at
  95% on both. (Strict six-level monotonicity did *not* replicate and has been withdrawn.)
- **The two halves of the detector are biased in OPPOSITE directions.** At equal power, the
  vocabulary term flags low-proficiency writers 1.57x more — Liang et al.'s perplexity account
  exactly — and the burstiness term flags high-proficiency writers 1.42x more. Both separate; both
  replicate. They partly cancel, so **any aggregate fairness number for this detector understates
  both**, and a benchmark treating it as a black box cannot recover them. `--ablate` reports it.
- **The disparity reverses with the threshold** (worst group flips to the *lowest* proficiency at
  0.70, 3.25x). Which students a detector wrongly accuses is a function of an operating point
  somebody chose, usually without knowing that is what they were choosing.
- No demographic axis — race, gender, economic status, grade — separated at 95% confidence.
- **The bias is in the FEATURES, not our calibration.** Raw signals, before any detector touches
  them: more proficient learners are less bursty (Cohen's *d* −0.394, held-out −0.363) and use
  fewer common words (−0.476, held-out −0.537). Any detector treating low sentence-length variance
  as machine-like inherits a penalty on writing maturity. **Scope:** GPTZero popularised the
  feature but moved to a neural architecture in 2023, so this is not a claim about current
  GPTZero — it is about the heuristic tier, ours included. Whether a modern neural detector
  learned the same correlation is the open question, and needs weights this environment's egress
  policy blocks from downloading.

Recorded as `ellipse-subgroup-fpr`, `ellipse-fpr-by-proficiency`,
`ellipse-lite-signal-decomposition`, `ellipse-proficiency-replication`,
`ellipse-component-ablation` and `ellipse-raw-signal-effect-sizes` in
`.claude/measurements.jsonl`.


## 1. What we cannot win — say it once, then stop spending on it

### ❌ Raw evasion strength

| system | result | scale |
|---|---|---|
| `chengez/Adversarial-Paraphrasing` | −87.88% avg TPR@1%FPR, **per-token** detector-guided decoding | MAGE dataset, 6 detectors |
| `StealthRL` | AUROC 0.79 → 0.43, mean TPR@1%FPR 0.024 | **15,310 human / 14,656 AI** |
| **untell**, best real-text figure | 0.774 → **0.285 ± 0.005**, flagged 0.95 → **0.217** | **n = 40, ×3 repeats** |

Not close, and the gap is architectural: token-level guidance needs logit access, which our
black-box rewriter design does not have. Closing it needs the GPU path in §4.

The untell row moved a long way on 2026-08-07 and is worth reading carefully, because it does not
change the conclusion. The old figure was the **`neural`** rewriter on **n = 6**, single run. The
new one is the free CPU-only **`composite`** on **n = 40 with 3 repeats** (120 rewrites), which is
both a stronger result and far better evidence: post 0.285 ± 0.005 against a pre of 0.774, with
21.7% of texts still flagged where 95% were before, at 0.9799 mean similarity. That is the SHIPPED
configuration (`best_of=3`), replicated over 3 runs and 120 rewrites.

The two halves of that row moved in opposite directions on the last change and both are reported.
Adding nominalisation substitutions took the flagged rate from 35.8% to **31.7%** at that step,
while the mean score went 0.300 to 0.312 and the spread doubled to ±0.016, so the score
difference is INSIDE the noise rather than a regression. Quoting only the improvement would be the
kind of selective reporting this document exists to avoid.

The same corpus and settings measured **0.951 post with 39 of 40 still flagged** before that day's
work. The gain came from fixing defects rather than adding capability — a hedge gate vetoing 20% of
candidates over one bad synonym entry, 14 replacements whose output was itself a catalogued tell, a
diversity gate that provided no diversity, and four rewriter constants that no human writer matches
(Results 16-20 in docs/free-ceiling-measured.md).

One caveat on the row. The figure got *worse* during the day at fixed settings — `best_of=1` went
from 0.321 to 0.347 — because Result 22's fragment guards cost roughly 0.026 and 6.6 points of
flagged rate. That was spent deliberately: the rewriter had been emitting broken English, and three
attempts to recover the score without reintroducing it either failed or made the output worse.

The shipped figure was also first measured as a single run at **0.302 / 32.5%** and held back from
this row under the ≥3-repeats rule. Replication put it at 0.327 / 37.5% — the single run was two
standard deviations low, and quoting it would have overstated the product by 5 points of flagged
rate. It then improved to **0.300 ± 0.007** when a length budget stopped the rewriter
inflating sentence length (Result 26); the single run happened to land near the right answer for
the wrong reason, which is what a spread is for.

Real movement, on the axis we said we could not win. It does not win it. StealthRL's AUROC 0.79 →
0.43 stands on **15,310 human and 14,656 AI** samples; n = 40 is not n = 15,310, and a
detector-feedback loop against four open detectors is not the same claim as transfer to unseen
commercial ones. The gap is smaller than this section used to imply, and it is still a gap.

### ❌ Adoption

blader/humanizer is **one Markdown file** with 33.7k stars. We are at ~0. That is distribution, and
no amount of engineering moves it.

### ❌ Beating GPTZero / Originality / Turnitin for free

Nobody does, us included. Independent 2026 testing has StealthGPT — a paid product — still failing
Turnitin (86% AI), Originality (100%) and GPTZero (48%). SICO's paper claims otherwise for a
prompt-optimisation method we have not reproduced; recorded, not adopted.

---

## 2. Priority 1 — be the only one that is provably correct

This is the axis where the field is *empty*, and where one session of probing found this much:

| defect found 2026-08-05 | severity |
|---|---|
| `tells/100w`, the headline naturalness metric, pointed **backwards** on real text — **fixed, and re-derived 2026-08-09** at n=100 pairs per corpus: HC3 **0.551 human vs 7.335 AI**, RAID **1.215 vs 12.884**, correct direction and a wide gap on both, now held by an offline direction guard. The re-derivation also found what the row could not: `repeated_phrasing` is **91% (HC3) / 83% (RAID)** of every tell counted, so the headline number is largely one category, and the nine categories that *look* inverted by rate are 1-4 hits over 200 texts ([Result 45](docs/free-ceiling-measured.md)) | metric inverted |
| `targeted` rewriter did **literally nothing** on the zero-dep path (0/15 texts changed) — **fixed**, via a whole-text fallback that says so on stderr. The fix is confirmed: it now changes 10–12 of 15 on every configuration tried. The originally-quoted 14/15 / −0.186 named no corpus, tier or n and could not be reproduced — see [Result 42](docs/free-ceiling-measured.md), which re-derives it at −0.06 at best. | feature dead |
| `surgical` near-inert there too (16/30 texts, 0 substitutions) — **addressed**: it now optimises the axis word substitution actually controls. Re-measured over 30 HC3+RAID texts it changes **19/30** and moves tells/100w **8.02 -> 7.22 (-10%)**; the detector still barely reacts (-0.004), which is a property of the detector, not of the rewriter. Re-derived 2026-08-09 on the same 15 HC3 + 15 RAID split, with the before value reproducing to the digit: **23/30**, **8.02 -> 6.88**, detector **-0.0212** — better on every axis, plausibly from the map additions in Results 31-32 ([Result 42b](docs/free-ceiling-measured.md)) | feature dead |
| Chinese/Korean/Japanese AI text reported as **perfectly clean** — **fixed and re-derived 2026-08-09**: all three now return 0 tells with `language_supported=False`, an explicit warning that 0 means the patterns did not apply, and humanness 50 (undetermined) rather than a verdict. The re-derivation found the number right and the *message* wrong — a 40-character Chinese paragraph was reported as "shorter than 5 words", because `_WORD_RE` is `[A-Za-z']+` and counts none; now fixed and pinned, with a short-English case guarding the guard | false verdict |
| LaTeX **entirely unprotected** — `lock()` held 0 spans of a paper paragraph — **fixed, and re-derived clean 2026-08-09**: on a real paper paragraph `lock()` holds 10 spans, `restore()` round-trips byte-exact, `cite_keys()` finds every citation spelling, and all nine must-survive tokens (`\cite`/`\citet`/`\citep`, `\ref`, an escaped `%`, inline math, two counts) survive a full rewrite across 30 seeds. Now a regression battery rather than a paragraph | headline promise broken |
| the central competitive claim quoted a sentence **that exists in no commit** — **fixed**, and the claim that replaced it verified 2026-08-09 against all 435 census records: of 56 repos with both fields non-empty, **0** combine a mechanical meaning gate with citation locking, so "no profiled repo combines" holds. Citation locking alone is *not* unique — `marmbiz/humanizer-de` keeps a DOI/anchor ledger — and the page does not claim it is. The re-derivation also corrected the inference-time detector count from 43 to **44**, and every published census count is now machine-checked by `check_census_counts` ([Result 46](docs/free-ceiling-measured.md)) | fabricated citation |
| lite tier flagged **60% of human text** at the shipped threshold — **fixed**: the verdict threshold is now separate from the loop target and calibrated per scoring path, 60% -> 15% pooled (Result 24). Re-derived 2026-08-09 at n=100 per corpus: **30% on HC3, 10% on RAID** — the fix holds but the rate is no longer corpus-independent as the defect was, and the pooled figure describes neither ([Result 43](docs/free-ceiling-measured.md)) | calibration |
| `max` and `ensemble` are the same object, benchmarked as two — **guarded**: they resolve to one class and `max` reports `name="ensemble"`; a test now fails if any single table carries both as separate rows | phantom data point |

No competitor publishes anything comparable, because no competitor looks. Turning that into a
durable advantage means making it **mechanical rather than heroic**.

- ✅ **`untell-audit` — every documented claim re-measured on demand, and in CI.** Shipped
  2026-08-08 and wired into the build. Splits claims into DERIVABLE (registry sizes, which
  rewriters resolve, calibration constants, console scripts, cross-document links, census
  figures quoted outside the census — a drift fails CI) and MEASURED (cannot run in CI, so what
  is enforced is that each states its source). Its first run found **seven dead links in this
  site's own documentation index** and a README whose survey total disagreed with the census's
  own figure; it later caught the README's headline HC3 table overstating the product with
  figures no commit reproduces. Currently: 80 claims attributed, 0 unattributed.
  *(superseded description below kept for the reasoning)*
  `tests/test_docs_claims.py` already does this for ~16 claims (test count, census counts, the
  research-report quote, the lite false-positive rate). Generalise it: each claim in README /
  `why-best` / `free-ceiling-measured.md` carries a machine-checkable assertion, and CI fails when a
  number drifts. **This is the moat.** Effort: days.
- ✅ **Every category must prove it fires.** Extended 2026-08-08 from `tells` to detectors,
  rewriters and the meaning gates — see `tests/test_everything_registered_can_fire.py`. Every
  live detector must return DIFFERENT scores for blatant AI and blatant human prose and stay in
  [0,1]; every CPU rewriter must be able to change text; every hedge class has a positive
  control that drops it. Verified by breaking each on purpose.
  *(original note)* Already shipped for `tells` after six patterns turned
  out to be dead (`\b` written into a non-raw string became U+0008). Extend the same
  reachability guard to detectors, rewriters and meaning gates: anything registered must
  demonstrate it can fire, or it is dead code pretending to be coverage.
- ✅ **Publish the negative results as a first-class artifact.** `docs/index.md` now leads with
  the measurement log and features the refutations by name. *(original note)* `free-ceiling-measured.md` has 15
  results including refutations of our own claims. That document is more persuasive than any
  benchmark table. Give it a landing page.

---

## 3. Priority 2 — free wins already measured, not yet taken

### ✅ Make the default configuration the good one — done, and the answer was the opposite

This section used to read: *the shipped default clears nothing on real text at the full tier, so
auto-select `neural` when `.[full]` is installed.* That was based on six HC3 texts and a single run
per arm. Replicated properly on 2026-08-07 — n = 40 RAID, full tier, same `best_of`:

| rewriter | post | flagged | mean sim | **worst sim** | cost |
|---|---|---|---|---|---|
| **`composite`** (default, 3 repeats / 120 rewrites) | **0.285 ± 0.005** | **21.7%** | 0.9799 | **0.9224** | CPU only |
| `neural` (1 run) | 0.369 | 37.5% | 0.9621 | 0.8716 | T5, hours |

The default was not the problem. It had **fixable defects**, and Results 16–20 removed them: the
same corpus that measured 0.951 post with 39 of 40 flagged now measures **0.285 ± 0.005 with 21.7%
flagged in the shipped `best_of=3` configuration**, replicated over 3 runs (Results 23-32). At
`best_of=1` it is 0.347, up from 0.321 earlier in the day — Result 22's fragment guards cost that,
knowingly.

Be precise about what this does and does not establish. The 0.048 score gap is **smaller than
`neural`'s own ±0.079 run-to-run spread**, so the two are not separable on evasion at this sample
size. `composite` stays the default because it *matches* `neural` there while holding 0.9406
worst-case similarity against 0.8716, varying six times less run to run, and needing no GPU.

### ✅ Retire or rehabilitate the dead weight — done, and nothing gets retired

`ai_vocab` — the "delve / leverage / tapestry" cluster this entire product category is famous for —
measured **0.55 precision on 400 real HC3 pairs**. A coin flip. Five categories fired *more* on
human writing than AI. This item held open on a stated blocker: HC3 is 2022-era, the ten categories
silent on it are exactly the *modern* tells, so the fix is a modern labelled corpus rather than
reweighting against a dated one.

RAID is that corpus — multi-generator, exact human/machine pairing, far more recent — and it has now
been run twice, at 150 pairs and again at 200 pairs on both corpora. It settles the question against
the optimistic reading:

- **`ai_vocab` is not rehabilitated.** 0.615 on HC3, 0.585 on RAID. Two corpora, two eras, two
  generator families, one answer. The flagship cluster of the entire category is a coin flip and a
  modern corpus does not rescue it.
- **The silent categories were right to keep.** `participial_trailer` fires on nothing in HC3 and is
  the *strongest* category on RAID at 0.971; `challenges_section` likewise, at 0.833. Dropping the
  silent ones — which the HC3 numbers alone justified — would have deleted the best pattern in the
  catalogue. The blocker was correct, and acting on the old data would have been a mistake.
- **`em_dash` fired on 0 AI documents** across 200 HC3 pairs and 200 RAID pairs (measured
  2026-08-09; 7 human documents, 0 AI). The most-cited AI tell in public discourse has no
  observations pointing the right way in either corpus. Kept and reported as `weak` with the number
  attached, because a reader looking for the famous tells should see it was checked.
- **Some of the catalogue measures register, not authorship.** `hedge_stacking` runs 0.53 on forum
  answers and 0.88 on abstracts; `formulaic_transition` 0.88 and 0.60 the other way. No single
  quality number for the catalogue means anything without naming the corpus.

So: nothing retired, nothing reweighted, and the evidence tiering is no longer an interim — it is
the answer. The measurement is in the header of `untell/scripts/tells.py`, beside the code it
describes.

### ✅ Finish the surgical objective — done; the competitor row stays faithful

`surgical_substitute` cannot move a detector score at *either* tier (stdlib 0.003, full 0.0002), so
its deletion-importance ranking buys nothing. `prefer_tells=True` ships for our rewriter
(tells/100w 0.571 → 0.233 vs 0.458, and 2.3× faster).

The one open question was whether the competitor baseline row in `eval/compare_humanizers.py`
should also switch to the tells objective. It should not, and the reason is not a close call: that
row exists to report what **PWWS actually does**. Giving it our objective would make the comparison
measure our idea implemented twice and label one of them as the competition — the row would improve
and mean nothing. A baseline that is allowed to be worse than us is the only kind worth publishing.

Closed as decided, not as deferred.

---

## 4. Priority 3 — the academic niche, where our strengths are the buying criteria

**41 of the 111 profiles that beat untell at something named the academic/LaTeX/citation domain** —
the most-cited gap in the census, and the one place where meaning integrity *is* the product rather
than a nicety.

- ✅ LaTeX preserve-locking (`\cite*`, `\ref`, `\label`, math, environments) — shipped 2026-08-05.
- ✅ **BibTeX-aware verification** — `untell-latex --bib` confirms every `\cite` key resolves, and
  `--against` reports any citation a rewrite LOST. Preserve-locking stops a key being edited; it
  cannot stop a whole sentence being merged away with its citation, and the document still
  compiles.
- ✅ **`.tex` round-trip** — and it was worse than unfinished. `latex_env` matched ANY environment,
  and `document` is one, so a real paper masked to two sentinels and the tool returned the input
  UNCHANGED. Scoring the source also under-read it (raw 0.0949 vs prose 0.6261), so the loop
  declared an AI-written paper already passed. Both fixed: 0.6261 → 0.0815 end to end, valid
  LaTeX out, zero citations lost.
- ✅ **Structure-aware skipping** — abstract, theorem, proof, figure, table, caption, all maths and
  verbatim are locked. This was already shipped by the environment lock while the roadmap listed
  it as pending; verified rather than assumed.

What the census says about becoming the *most starred* repo, as opposed to the best one, is
measured in [what would make this the top repo](docs/what-would-make-this-the-top-repo.md):
briefly, engineering raises the floor and not the ceiling, and the one search strategy no
profiled repo uses is beam search.

Nobody in the census targets thesis and paper writers with fact-integrity guarantees. We have the
five meaning gates and byte-exact citation locking that **no profiled repo combines**. This is a
defensible position that does not require beating chengez at evasion.

---

## 5. Priority 4 — the language platform (needs your decision)

**139 of 435 profiled repos (32%) target a language other than English**, and that is *understated*
— 49 reads died on an API spend limit, almost all Spanish, Portuguese, French, Russian and Ukrainian
humanizer skills. Four of the eight largest tools in the field are Chinese or Korean.

Everything here is English-only: the 29-pattern catalogue, the voice matcher's scale constants,
every measurement.

- ✅ **Refuse to fake it** — non-Latin input now returns `language_supported: false` with a warning
  instead of "no catalogued tells found".
- ✅ **The registry, additively** — `untell/languages.py` ships the architecture with exactly one
  entry: English, pointing at the catalogue that already exists. `register(code, scorer,
  script=...)` adds a language, `catalogue_for(text)` routes by dominant script, and a text in a
  script nobody has written for returns **None** rather than falling back to English — because
  running the English catalogue over Korean finds no English tells and reports a clean score for
  text nothing examined.

  Done this way precisely *because* the restructuring version is a decision. `untell/scripts/tells.py`
  is not moved, not renamed and not imported differently by anything; a test asserts it contains no
  reference to the registry at all, so "add a file, touch nothing" stays true rather than being an
  aspiration. If you later want the full `tells/en.py` split, nothing here blocks it.

- 🔜 **The catalogues themselves** — still not ours to write, and unchanged from the position below.

I will not write the catalogues themselves: Korean 번역체 calques and Chinese academic-register tells
need people who speak those languages. But **the architecture is the contribution** — it turns our
largest blind spot into the reason others contribute, which is the only realistic adoption path that
does not depend on marketing.

**This changes a core module. It is a decision, not a task.**

---

### 📦 `pip install untell` claims the names `eval` and `training` — needs your decision

Found 2026-08-09 by building a wheel and installing it into a clean virtualenv. Confirmed
empirically there, not inferred:

```
>>> import eval, training          # after a clean `pip install untell`
>>> eval.__file__
.../site-packages/eval/ceiling.py
```

Seven console scripts point into these two directories (`untell-ceiling`, `untell-compare`,
`untell-prove`, `untell-detector-audit`, `untell-eval-policy`, `untell-distill`,
`untell-surrogate`), and `untell/api_server.py` and `untell/mcp_server.py` import from `eval`
directly. So they must be declared as packages, and being top-level directories they install as
top-level names.

Both directions of this are real. Another distribution shipping a `training` package overwrites
ours or is overwritten by it, and a user with a `training.py` in their working directory shadows
the installed one, so `untell-distill` breaks with an import error that names none of this.

The fix is to move them to `untell/eval/` and `untell/training/`. Mechanical but not small: 179
references across 47 files, and it **breaks anyone importing `eval.ceiling` directly**. The
console-script names would not change, and the documented public surface is `untell.*` plus those
scripts, so the blast radius is probably small — but "probably" is doing work in that sentence and
it is a published package, so it is your call rather than one to make in passing.

`tests/test_packaging.py` does the non-breaking part: it pins the situation so it stays coherent
(no console script pointing outside a declared package, no data file tracked but undeclared) and
does not let it quietly grow.

## 6. The moat — needs a GPU

- ⛔ **Surrogate distillation** (HMGC, COLING 2024 — prior art for what `training/surrogate.py`
  scaffolds). Distil the victim detector, attack the surrogate. Highest ROI of the GPU paths.
- ⛔ **RL-against-ensemble** (StealthRL-style GRPO + LoRA). Reward = evasion vs our ensemble +
  semantic similarity. The literature shows it **transfers to detectors it never trained on**.
- ⛔ **Alignment rewriter** (MASH-style): style SFT → DPO → inference refinement, shipped as a local
  no-key rewriter.

**Known blocker:** free-GPU training stalls on model-load; do not re-attempt blind. Budget a real
GPU or skip. The product works without a trained adapter.

---

## 7. Open questions, already measured

Each of these was investigated to the point of a number and then deliberately left. They are listed
so the next attempt starts from the measurement rather than from the intuition — and in two cases
the measurement is the reason not to proceed.

| question | what is known | what would settle it |
|---|---|---|
| **Should the loop refuse candidates that raise repetition?** | **Closed — no.** Re-measured at n=105 across both corpora: the crossing happens **once in 105 texts**, not the 1-in-10 the first sample suggested. The guard prevents it and costs +0.0063 (HC3) / +0.0026 (RAID), with a paired record of **worse on 5, better on 1** on HC3 ([Result 59](docs/free-ceiling-measured.md)) | Nothing. Three successive samples moved the rate 1/10 → 1/30 → 1/105 |
| **The loop selects on masked text; the metric scores restored text** | **Closed.** All 13 masked reads in `run.py` enumerated by AST walk ([Result 58](docs/free-ceiling-measured.md)): 11 are safe by symmetry or must be masked, the tells tie-break was fixed in Result 57, and sentence targeting is now fixed too — masking moved the flagged set on **25%** of texts on the model-backed path | Nothing. The rule that sorts every case: symmetry cancels, absolutes do not |
| **`untell_text(scrub=False)` leaves the contraction transform dead** | Over 30 seeds the transform produces nothing on U+00A0 input. End-to-end cost **0.0011** against a ±0.013 floor ([Result 53](docs/free-ceiling-measured.md)) | Nothing — this is a decided non-fix. Folding at loop entry would mutate text on the one path where the caller asked for it untouched |
| **Beam search over rewrite candidates** | Closed. At matched budget, paired on the seed, beam **loses more often than it wins** on three of four arm/corpus combinations ([Result 48](docs/free-ceiling-measured.md)) | Nothing. The zero in the census technique table is not an opportunity |
| **Does a second pass help?** | Yes, modestly: **+0.0275**, about 27% of the first pass, better on 6 of 10 texts and worse on none, for 0.0036 extra meaning drift ([Result 54](docs/free-ceiling-measured.md)) | Whether to surface it as a documented recommendation |

Two open items are **not** autonomous and are unchanged: per-language tell catalogues need someone
who reads the language (§5), and three items need a GPU (§6).

## 8. Sequencing

1. **Default rewriter change** — measured, small, currently costs every full-tier user a result.
2. **`untell-audit` + CI claim checking** — converts tonight's one-off discipline into a standing property.
3. **Academic niche** (BibTeX verify, `.tex` round-trip) — where our strengths are the buying criteria.
4. **Language plugin architecture** — pending your decision; biggest ceiling, biggest refactor.
5. **GPU moat** — only with real hardware.
6. **Second corpus for the audit** — one corpus is not a population, and the proficiency finding needs replication outside US school-age learners.

## 9. How we would know it worked

Not stars. These:

- **zero drifted claims** — CI proves every published number still reproduces
- **`neural` default clears ≥ 50% of real HC3 text** at full tier, replicated at `--repeats ≥ 3`
- **a `.tex` file round-trips** and still compiles, with every citation key intact
- **one non-English catalogue contributed by a native speaker** — the platform test
- **a detector audited by someone who does not maintain it** — the audit position's real test is an institution running `untell-subgroup-audit` against a detector it is deciding whether to trust
