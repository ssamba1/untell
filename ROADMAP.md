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

**Rows 1–17 are unchanged: nothing there is actionable without a decision from you.** Rows
18–23 were opened 2026-09-01 from the literature review (§7) and are the exception — they need
no decision, no native speaker and no GPU, only the work.

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
| 18 | Calibrated verdict thresholds (conformal, length-conditioned) | 🔜 open | **nobody — buildable now.** Needs a human-only calibration corpus, which RealDet supplies and RAID's human side approximates. |
| 19 | Beemo + ARB loaders — human-edited and LLM-rewritten-human text | 🔜 open | **nobody — buildable now.** Both corpora are public; Beemo needs a four-way label, not the current pair shape. |
| 20 | The base-vs-instruct audit arm | 🔜 open | **nobody — buildable now.** CPU only, ~1 day, no new dependency. |
| 21 | SynthID-Text detector adapter (Article 50 marking audit) | 🔜 open | **nobody — buildable now.** `synthid-text` is open source and in HF Transformers; the attack side already exists. |
| 22 | Confidence intervals on every published rate | 🔜 open | **nobody — buildable now.** Arithmetic over data already collected. |
| 23 | AI-assisted arm + FAR/MFAR + per-subgroup stratification | 🔜 open | **nobody — buildable now.** Metrics are arithmetic; the fairness corpus is MIT-licensed and public. |

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

## 1. What we cannot win — say it once, then stop spending on it

### ❌ Raw evasion strength

| system | result | scale |
|---|---|---|
| `chengez/Adversarial-Paraphrasing` | −87.88% avg TPR@1%FPR, **per-token** detector-guided decoding | MAGE dataset, 6 detectors |
| `StealthRL` | AUROC 0.79 → 0.43, mean TPR@1%FPR 0.024 | **15,310 human / 14,656 AI** |
| **untell**, best real-text figure | 0.774 → **0.285 ± 0.005**, flagged 0.95 → **0.217** | **n = 40, ×3 repeats** |

Not close, and the gap is architectural: token-level guidance needs logit access, which our
black-box rewriter design does not have. Closing it needs the GPU path in §6.

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

## 7. What the literature establishes — verified at source, and what follows from it

Added 2026-09-01, then **checked rather than trusted**. The survey is
[the literature map](ai-writing-research.md); the buildable part is
[what we can use](docs/research-to-build.md); **the audit trail, verification tiers and the
corrections that checking produced are in
[the verification ledger](docs/research-verification.md)** — read that before quoting any number
here. Publisher and preprint hosts are blocked by organization egress policy in the environment this
was compiled in; PubMed/PMC and github.com are not. The ACL Anthology publishes its abstracts as XML
in its own GitHub repository, which put **seven more papers** under direct reading, and several
arXiv-only results were confirmed from their authors' repositories. ✅ marks a claim read at source.
Six claims changed on contact with their sources; the ledger lists all of them.

### The result that should organise everything else — all of it peer-reviewed and read at source

A systematic pass over **16 ACL Anthology volumes, 20,875 abstracts, 334 detection papers** (method
and counts in [the ledger](docs/research-verification.md)) replaced the earlier framing. Everything
below is refereed and was read from the Anthology's own metadata.

**Start with what the field counts as its own priorities.** Of those 334 detection papers: **102**
address robustness and evasion, **29** watermarking, **18** calibration — and **6** address false
positives, **5** fairness. **The field spends about 30% of its detection effort making detectors
harder to evade and under 2% on what happens when one is wrong about a person.** That is the gap this
repo sits in, now counted rather than asserted.

Five refereed results then fix the shape of the problem:

1. ✅ **Detector failure under domain shift is distributional, not a quality defect.** DivScore
   ([2025.emnlp-main.971](https://aclanthology.org/2025.emnlp-main.971/)) gives a theoretical account
   tying zero-shot detector failure in specialized domains to "the KL divergence between human,
   detector, and source text distributions."
2. ✅ **Moving a writer's style moves the verdict, both ways.** Liang et al. (*Patterns*,
   [DOI](https://doi.org/10.1016/j.patter.2023.100779)): enriching non-native TOEFL vocabulary cut the
   average false-positive rate **61.3% → 11.6%**; simplifying native essays *raised* misclassification.
3. ✅ **Bias is real, multi-attribute, and inconsistent between systems.** *Identifying Bias in
   Machine-generated Text Detection* ([2026.acl-long.109](https://aclanthology.org/2026.acl-long.109/))
   tests **16 detection systems** on student essays across gender, race/ethnicity, ELL status and
   economic status: ELL essays are more likely to be called machine-generated, and **non-White ELL
   essays disproportionately so relative to their White counterparts** — but the biases are "generally
   inconsistent across systems."
4. ✅ **Minimal polishing is already enough to be flagged.** *Almost AI, Almost Human*
   ([2025.findings-acl.1303](https://aclanthology.org/2025.findings-acl.1303/)) evaluates **twelve
   detectors** on 15K graded-involvement samples: they "frequently flag even minimally polished text as
   AI-generated" and cannot distinguish degrees of AI involvement.
5. ✅ **And a detector at 0.00% FPR can be the most biased in the same study.** Pratama (*PeerJ CS*,
   [DOI](https://doi.org/10.7717/peerj-cs.2953)): GPTZero, 97.22% accuracy at **0.00% FPR** on clean
   human-vs-AI, then worst of three for non-native authors on assisted text (**25% vs 11%**
   over-detection). Ensemble exposure: **FAR 44.44%**, **MFAR 4.17%**.

✗ **And one refereed result cuts against us, which is why the conclusion holds.** *Different Time,
Different Language* ([2026.eacl-srw.20](https://aclanthology.org/2026.eacl-srw.20/)) repeats the Liang
test in **Czech** and finds non-native perplexity is *not* lower, **no systematic bias across three
detector families**, and modern detectors not relying on perplexity at all. One language, a student
workshop — it does not overturn Liang. But it does kill "non-native writers are biased against" as a
universal, and our documents had been treating it as one.

**That disconfirmation is the strongest evidence for the thesis, not against it.** Bias appears in
English TOEFL and ICNALE data and not in Czech; detector biases are "inconsistent across systems";
detection is bound to domain and generator; no detector wins across scenarios
([2026.acl-industry.9](https://aclanthology.org/2026.acl-industry.9/)). Every one of those is a
refereed statement that the answer depends on which detector meets which population in which domain.

### Why a false positive is not a recoverable mistake

✅ *Human Bias in the Face of AI* ([2025.findings-acl.1329](https://aclanthology.org/2025.findings-acl.1329/))
ran three experiments on rephrasing, summarization and persuasive writing. Blind, raters **could not
tell human from AI text**. Labelled, they preferred text marked "Human Generated" by **over 30%** —
**and the same pattern held when the labels were deliberately swapped.**

**The label drives the judgment, not the text.** A detector's output is a label. So a false positive
does not merely risk being wrong; it changes how everyone downstream reads that work, in a direction
the work itself cannot correct. It also retires the standard mitigation — "a human will review the
flag" is not a safeguard when the reviewer has already been anchored by it, and round three's finding
that humans detect poorly but **without** significant bias
([2026.acl-long.109](https://aclanthology.org/2026.acl-long.109/)) holds only until a label is put in
front of them.

That is the ethical case for this repo, established by someone else's experiment: the cost of a false
positive is not a corrected mistake, it is a permanently altered reading.

### The number that settles it

A PubMed pass then assembled every refereed study that reports a false-positive rate **on text known
to be human**:

| Setting | Measured FPR | Source |
|---|---|---|
| Anatomy essays, **4 detectors in aggregate** | **~0%** | [DOI](https://doi.org/10.1152/advan.00235.2024) |
| Same study, single detectors | 1.3% | same |
| Same study, **9 human raters** | 5.0% | same |
| *J. Craniofacial Surgery* manuscripts from **2014** — necessarily pre-LLM | **8.6%** | [DOI](https://doi.org/10.1097/SCS.0000000000012366) |
| Behavioral-health articles, free detector | 27.2% | [DOI](https://doi.org/10.1080/08989621.2024.2331757) |
| Abstracts, flagged by ≥1 of 3 tools | 44.44% | [DOI](https://doi.org/10.7717/peerj-cs.2953) |
| TOEFL essays, non-native writers, 7 detectors | 61.3% | [DOI](https://doi.org/10.1016/j.patter.2023.100779) |

**Same technology, on real human writing, from about 0% to 61%.** These do not contradict each other;
each is a correct measurement of a different population, domain, detector set and aggregation rule.

**So: a false-positive rate is not a property of a detector. It is a property of a detector, a
population, a domain, an editing history and an aggregation rule — and it cannot be inherited from
anyone else's paper, ours included.** An institution that reads 1.3% in a physiology journal and
deploys against ESL applicants has imported a number from the wrong end of a 47× range. The only
measurement worth anything is the one taken on the deployment's own corpus, per subgroup. That is the
thesis, and it now rests on refereed results this environment read at source — including two that
disconfirm parts of it.

> **The framing we no longer need.** *AI Detectors Fail Diverse Student Populations*
> ([arXiv:2603.20254](https://arxiv.org/abs/2603.20254)) argues the same conclusion formally from a
> composite null. It is single-authored, arXiv-only, and unreachable from here. DivScore now supplies
> a refereed version of the same idea, so this is kept as an elegant statement of the argument and
> **nothing rests on it.**

**What untell is, restated in one sentence:** the tool that measures what a detector does to *your*
population, per subgroup, at the vendor's threshold and at a calibrated one, and reports the gap.

- 🔜 **The AI-assisted arm, FAR and MFAR — the item that most changes what we output.** ✅ In Pratama
  (*PeerJ CS*, [DOI](https://doi.org/10.7717/peerj-cs.2953)) GPTZero scored **97.22% accuracy at 0.00%
  FPR** on clean human-vs-AI, then proved the *most biased* of three tools on **AI-assisted** text
  against non-native authors (Welch's t = −2.115, p = 0.036), over-detecting **25%** of non-native
  authors against **11%** of native ones. **A detector can be flawless on the benchmark everyone runs
  and unfair on the only case that matters**, and an audit that stops at human-vs-AI — every audit,
  ours included — cannot see it. The same paper supplies two metrics with published names:
  **FAR** (flagged by ≥1 tool; measured **44.44%**), which is exactly what our `max` aggregation
  computes, and **MFAR** (flagged by a majority; **4.17%**). Adopt both verbatim, add an AI-assisted
  arm, and stratify by subgroup — the auditing protocol the literature specifies and nobody ships.

  ✗ **And a refereed result says our aggregation is the wrong verdict rule.** Hyatt et al.
  ([DOI](https://doi.org/10.1152/advan.00235.2024)) found single detectors at **1.3%** false positives
  on 190 students' essays and **~0% when required to agree**. Our `max` is the *union* rule — flag if
  **any** detector flags — which is exactly the FAR measured at 44.44%, and it maximises false
  accusations by construction. It is right as the loop's **stop target** and wrong as a **verdict**.
  So report the spread rather than a number: **union (FAR) / majority (MFAR) / unanimous (consensus)**,
  anchored at 44.44% / 4.17% / ~0%. **The gap between those three rows is the institution's policy
  decision, and nobody puts it in front of them.**

  **Also steal Bohler et al.'s probe** ([DOI](https://doi.org/10.1097/SCS.0000000000012366)): they
  scored 659 manuscripts from **2014**, necessarily pre-LLM, and got **8.6%** — a pure false-positive
  rate with unfalsifiable ground truth and no labelling. A pre-2022 corpus arm is the cheapest honest
  FPR probe in existence and we should ship one.

- 🔜 **Calibrated thresholds, so the negative result stops being only a complaint.** Multiscaled
  conformal prediction ([2025.acl-long.601](https://aclanthology.org/2025.acl-long.601/); Zhu, Ren,
  Cao, Lin, Fang, Li) bounds the FPR from a human-only calibration set. ✅ Read at source: plain
  conformal prediction constrains FPR but "leads to a significant reduction in detection
  performance", and MCP exists to recover it — which is precisely our trade-off. *(The
  "length-conditioned" reading and RealDet's 15-domain / 22-LLM / 847k-text dimensions are **not** in
  the published abstract and remain Tier B — build against the paper, not against our summary.)*
  Today untell can say a shipped
  threshold flags 17% / 40% / 89% of human documents and has no answer to "then what threshold should
  I use". This is that answer, and it is the principled form of something already found by hand: the
  `verdict_threshold` split that took stdlib-path false positives from 52% to 18% is length-and-path
  conditioning, discovered empirically. Prior art to cite rather than reinvent:
  [FPRCal](https://github.com/cisco-ai-defense/fpr-model-calibration) does fixed-FPR score calibration
  as a scikit-learn pipeline — security domain, so the application is still open.

- 🔜 **Beemo and ARB — the corpora that test the claim we actually make.** HC3, RAID and MAGE are all
  human-vs-fully-machine, so "does a verdict survive meaning-preserving editing" is answered only by
  our own rewriter, in-sample by construction — the objection `eval/holdout.py` exists to answer for
  detectors. ✅ **Beemo** ([arXiv:2411.04032](https://arxiv.org/abs/2411.04032), NAACL 2025) is 19.6k
  texts with *human expert* edits of machine output, 11 detectors across 33 configurations, reporting
  that expert editing evades detection while LLM editing does not. **ARB**
  ([arXiv:2607.29539](https://arxiv.org/abs/2607.29539)) supplies H2L — human text an LLM rewrote —
  matched four ways at TPR@1%FPR. ✗ An earlier draft of this section called H2L unpublished; that was
  wrong (Pratama measured it; Karr et al. put light edits at **64–80%** for Pangram and **38–49%** for
  GPTZero against **9–15%** for unmodified originals). The gap is in *our* corpora, not in the
  literature. ✅ Beemo's abstract was read at source and says exactly what we claimed: 33 detector
  configurations, "expert-based editing evades MGT detection, while LLM-edited texts are unlikely to
  be recognized as human-written".

- 🔜 **The base-vs-instruct arm — a day of work for a finding that renames the category.** Base
  (non-instruction-tuned) output is judged overwhelmingly human by GPTZero and Pangram while the
  instruction-tuned counterpart is not ([arXiv:2605.19516](https://arxiv.org/abs/2605.19516); Xu,
  Zhong, Raghunathan, Fang, Kolter). **This is a Tier-B lead and the item does not rest on it**: the
  deliverable is *our* measurement, which is what would expose the claim if it were wrong, and the
  paper states its finding qualitatively so **no number may be quoted from it**. The reason to run the
  arm regardless is Tier A — M4GT-Bench establishes that detection is generator-bound, and a base
  model is the cleanest generator contrast available. If raw base output goes unflagged, the detector
  is keying on
  instruction-tuning register, not machine generation — the same conclusion the homogenization
  literature reaches from the other end, and the reason an L2, autistic or technical writer gets
  flagged for prose that merely sits where RLHF converges. Ship it as
  `untell-detector-audit --arm base-vs-instruct`, matched prompts, matched model family.

- 🔜 **A SynthID-Text adapter, timed to the Article 50 phase-in.** Article 50(2) has applied since
  **2 August 2026**, with systems already on the market covered from **2 December 2026**; providers
  must ensure synthetic text is marked machine-readably and detectable as AI-generated. Nobody audits
  whether that marking survives ordinary use, and the evidence says it does not — ✅ with exact
  numbers, read from the authors' repo ([githshine/SynGuard](https://github.com/githshine/SynGuard)):
  SynthID-Text detection F1 falls from **1.000 to 0.842** under paraphrase, **0.788** under
  copy-and-paste and **0.714** under re-translation.

  ✗ **But do not overstate fragility — a refereed result cuts the other way.** *Sandcastles in the
  Storm* ([2025.acl-long.1436](https://aclanthology.org/2025.acl-long.1436/)) tests random-walk
  erasure empirically: mixing is slow, **100% of perturbed texts retain traces of origin after
  hundreds of edits**, quality oracles misjudge edits (77% accuracy), and automated attacks remove
  watermarks **just 26% of the time, falling to 10% under human quality review**. The reconciled
  position, and the one to build to: **detectability degrades under ordinary editing while complete
  removal stays hard.** Those are different claims and both are Tier A. A mark that mostly survives is
  worth measuring precisely, which makes this item more attractive, not less.

  SynthID's mean score also has a published
  layer-inflation attack ([arXiv:2603.03410](https://arxiv.org/abs/2603.03410)), and a legal-technical
  analysis finds machine-verifiable marks "fragile under standard data processing"
  ([arXiv:2603.26983](https://arxiv.org/html/2603.26983v1), LREC 2026), independently corroborating
  the August 2026 date. ✅ Build against the **HF Transformers** implementation, not the DeepMind
  reference repo, which states it is "not intended for production use". Our
  `untell/attacks/back_translation.py` is already one of the attacks that robustness paper uses.

- 🔜 **Confidence intervals on every published rate.** Fix and report FPR, report TPR@1%FPR alongside
  AUROC, give bootstrap intervals ([RAID, ACL 2024](https://aclanthology.org/2024.acl-long.674/);
  [arXiv:2603.17522](https://arxiv.org/abs/2603.17522)). Our headline rates are point estimates at
  n = 30 and n = 40; a 17% rate on n = 30 carries a 95% Wilson interval of roughly 7–35%. Stating it
  is the only version of the argument this repo is entitled to make, and ARB and Beemo both report at
  TPR@1%FPR, so reporting there is also what makes our numbers comparable to anyone else's.

### What checking changed, and what it cost

✗ **MGTEVAL is a stronger neighbour than the first draft said.** Read at source, its repo advertises
**25+ detectors** and **12+ attack families** — including a **humanization** family — and it already
reports **bootstrap CIs, ECE, Brier, risk-coverage and TPR@FPR**, with CLI and web UI. So we do not
win on detector count, attack count, *or* statistical reporting, and §0's competitive framing must
stop implying otherwise. What remains ours is the composite-null consequence above: FPR measured on
**real human writing**, **per subgroup**, at **vendors' own shipped thresholds**, with a calibrated
threshold returned. MGTEVAL benchmarks detectors; untell audits a deployment. Those are different
products and we should say which one we are.

✗ Two claims in the first draft were wrong and are corrected in the ledger: that nobody publishes
H2L results, and that nobody has connected stylistic distance to false-positive rate. Both were
overstatements that reading the sources removed.

### The rule this section is written under

Publisher and preprint hosts are blocked here by organization egress policy. After exhausting every
legitimate channel — PubMed/PMC, the ACL Anthology's own metadata, authors' repositories, GitHub code
search, arXiv mirror repositories, OpenAlex, Crossref, CORE, OpenReview, `github.io` — a set of
arXiv-only 2026 preprints remains unreadable from here. Calling them validated would be false, and
leaving them load-bearing would be worse.

So this section is written to a rule instead: **every claim a decision rests on is one that was read
at source.** Where a Tier-B result is genuinely useful — the composite-null framing, Karr's
asymmetry, ARB's design, the base-vs-instruct finding — it is cited as a *lead*, marked as such, and
the item it accompanies is justified without it. **The verified set and the load-bearing set are the
same set.** What remains unread is signposted for anyone with unrestricted access, in priority order,
at the end of [the ledger](docs/research-verification.md).

**Two findings that change existing text rather than adding work.** Weber-Wulff et al.
([IJEI 2023](https://link.springer.com/article/10.1007/s40979-023-00146-z)) tested 14 detectors,
found every one below 80% accuracy and only five above 70%, and is the peer-reviewed precedent for
this project — cited nowhere in it. And the *feature-inversion trap*
([arXiv:2510.12476](https://arxiv.org/pdf/2510.12476), ACL 2026, with StyloBench) shows features
separating human from machine **flip sign** under personalization, because training-free detectors
assume human text is the more diverse of the two. `eval/detector_audit.py` already has an `INVERTED`
class for that failure; the paper says it is a systematic regime, not a bug.

---

## 8. Open questions, already measured

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
who reads the language (§5), and three items need a GPU (§6). The five items in §7 are the
opposite case — autonomous, unblocked, and open only because nobody has done them yet.

## 9. Sequencing

Items 1-3 are done; they are kept so the order that produced them is legible.

1. ✅ **Default rewriter change** — measured, small, currently costs every full-tier user a result.
2. ✅ **`untell-audit` + CI claim checking** — converts tonight's one-off discipline into a standing property.
3. ✅ **Academic niche** (BibTeX verify, `.tex` round-trip) — where our strengths are the buying criteria.
4. **Confidence intervals** (§7) — hours, no new data, and every number below inherits the credibility.
5. **FAR/MFAR + the AI-assisted arm** (§7) — the metrics are arithmetic and the corpus is MIT-licensed,
   and it is where the published evidence says the failure actually lives. A detector at 0.00% FPR on
   our current arm was the most biased tool on this one.
6. **Calibrated thresholds** (§7) — the largest single change to what the product *outputs*, and the
   one that converts "your detector is miscalibrated" into "here is the threshold that fixes it".
7. **Beemo + ARB** (§7) — before any further evasion work, because they are what tells us whether the
   loop's numbers describe editing or describe our rewriter.
8. **base-vs-instruct arm** (§7) — a day, and it is the strongest negative result still unclaimed.
9. **SynthID adapter** (§7) — timed to the 2 December 2026 Article 50 phase-in, not before.
10. **Language plugin architecture** — pending your decision; biggest ceiling, biggest refactor.
11. **GPU moat** — only with real hardware.

The §7 items are ordered by evidence-per-day, not by ambition. Intervals cost hours and make every
other number defensible; FAR/MFAR is next because it is arithmetic over data we can already get; the
SynthID adapter is last because its value is a date, not a measurement.

## 10. How we would know it worked

Not stars. These:

- **zero drifted claims** — CI proves every published number still reproduces
- **`neural` default clears ≥ 50% of real HC3 text** at full tier, replicated at `--repeats ≥ 3`
- **a `.tex` file round-trips** and still compiles, with every citation key intact
- **one non-English catalogue contributed by a native speaker** — the platform test
- **every published rate carries an interval**, and none of them is a bare point estimate at n = 30
- **`untell` emits a calibrated threshold**, not just a verdict — an auditor can bound their own FPR
  at a chosen α and see how far the vendor's shipped threshold sits from it
- **the loop's evasion numbers are reproduced on Beemo's expert-edited split**, or they are restated
  as a property of our rewriter rather than of meaning-preserving editing
- **a watermark survives, or does not, with a number attached** — the Article 50 marking obligation
  audited the same way every detector here is
- **untell reports FAR and MFAR per subgroup**, on a corpus the user supplied, at both the vendor
  threshold and a calibrated one — the composite-null result in §7 says that is the only false-positive
  number that means anything, and no other tool produces it
