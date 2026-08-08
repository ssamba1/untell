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
| **untell**, best real-text figure | 0.774 → **0.327 ± 0.013**, flagged 0.95 → **0.375** | **n = 40, ×3 repeats** |

Not close, and the gap is architectural: token-level guidance needs logit access, which our
black-box rewriter design does not have. Closing it needs the GPU path in §4.

The untell row moved a long way on 2026-08-07 and is worth reading carefully, because it does not
change the conclusion. The old figure was the **`neural`** rewriter on **n = 6**, single run. The
new one is the free CPU-only **`composite`** on **n = 40 with 3 repeats** (120 rewrites), which is
both a stronger result and far better evidence: post 0.327 ± 0.013 against a pre of 0.774, with
37.5% of texts still flagged where 95% were before, at 0.9824 mean similarity. That is the SHIPPED
configuration (`best_of=3`), replicated over 3 runs and 120 rewrites.

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
rate.

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
| `tells/100w`, the headline naturalness metric, pointed **backwards** on real text | metric inverted |
| `targeted` rewriter did **literally nothing** on the zero-dep path (0/15 texts changed) | feature dead |
| `surgical` near-inert there too (16/30 texts, 0 substitutions) | feature dead |
| Chinese/Korean/Japanese AI text reported as **perfectly clean** | false verdict |
| LaTeX **entirely unprotected** — `lock()` held 0 spans of a paper paragraph | headline promise broken |
| the central competitive claim quoted a sentence **that exists in no commit** | fabricated citation |
| lite tier flagged **60% of human text** at the shipped threshold — **fixed**: the verdict threshold is now separate from the loop target and calibrated per scoring path, 60% -> 15% (Result 24) | calibration |
| `max` and `ensemble` are the same object, benchmarked as two | phantom data point |

No competitor publishes anything comparable, because no competitor looks. Turning that into a
durable advantage means making it **mechanical rather than heroic**.

- 🔜 **`untell-audit` — every documented claim re-measured on demand, and in CI.**
  `tests/test_docs_claims.py` already does this for ~16 claims (test count, census counts, the
  research-report quote, the lite false-positive rate). Generalise it: each claim in README /
  `why-best` / `free-ceiling-measured.md` carries a machine-checkable assertion, and CI fails when a
  number drifts. **This is the moat.** Effort: days.
- 🔜 **Every category must prove it fires.** Already shipped for `tells` after six patterns turned
  out to be dead (`\b` written into a non-raw string became U+0008). Extend the same
  reachability guard to detectors, rewriters and meaning gates: anything registered must
  demonstrate it can fire, or it is dead code pretending to be coverage.
- 🔜 **Publish the negative results as a first-class artifact.** `free-ceiling-measured.md` has 15
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
| **`composite`** (default, 3 repeats / 120 rewrites) | **0.327 ± 0.013** | **37.5%** | 0.9824 | **0.9394** | CPU only |
| `neural` (1 run) | 0.369 | 37.5% | 0.9621 | 0.8716 | T5, hours |

The default was not the problem. It had **fixable defects**, and Results 16–20 removed them: the
same corpus that measured 0.951 post with 39 of 40 flagged now measures **0.327 ± 0.013 with 37.5%
flagged in the shipped `best_of=3` configuration**, replicated over 3 runs (Result 23). At
`best_of=1` it is 0.347, up from 0.321 earlier in the day — Result 22's fragment guards cost that,
knowingly.

Be precise about what this does and does not establish. The 0.048 score gap is **smaller than
`neural`'s own ±0.079 run-to-run spread**, so the two are not separable on evasion at this sample
size. `composite` stays the default because it *matches* `neural` there while holding 0.9406
worst-case similarity against 0.8716, varying six times less run to run, and needing no GPU.

### 🔜 Retire or rehabilitate the dead weight

`ai_vocab` — the "delve / leverage / tapestry" cluster this entire product category is famous for —
measures **0.55 precision on 400 real HC3 pairs**. A coin flip. Five categories fire *more* on human
writing than AI; removing them raises separation +0.307 → +0.332 and AUROC 0.705 → 0.718.

They are currently reported via evidence tiers rather than dropped, because the ten categories that
never fire on HC3 are exactly the *modern* tells and HC3 is 2022-era. **The fix is a modern labelled
corpus**, not reweighting against a dated one. Until then the tiering is the honest interim.

### 🔜 Finish the surgical objective

`surgical_substitute` cannot move a detector score at *either* tier (stdlib 0.003, full 0.0002), so
its deletion-importance ranking buys nothing. `prefer_tells=True` ships for our rewriter
(tells/100w 0.571 → 0.233 vs 0.458, and 2.3× faster). Remaining: decide whether the competitor
baseline row in `eval/compare_humanizers.py` should stay faithful to PWWS (currently yes, correctly).

---

## 4. Priority 3 — the academic niche, where our strengths are the buying criteria

**41 of the 111 profiles that beat untell at something named the academic/LaTeX/citation domain** —
the most-cited gap in the census, and the one place where meaning integrity *is* the product rather
than a nicety.

- ✅ LaTeX preserve-locking (`\cite*`, `\ref`, `\label`, math, environments) — shipped 2026-08-05.
- 🔜 **BibTeX-aware verification** — confirm every `\cite` key in the output exists in the `.bib`.
- 🔜 **`.tex` round-trip CLI** — read a `.tex`, humanize prose only, write it back compiling.
- 🔜 **Structure-aware skipping** — never rewrite abstracts, captions, or theorem statements unless
  asked.

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
- 🔜 **Pluggable per-language catalogues** — `tells/en.py`, `tells/zh.py`, `tells/ko.py`, a registry,
  and the existing script detector routing to the right one.

I will not write the catalogues themselves: Korean 번역체 calques and Chinese academic-register tells
need people who speak those languages. But **the architecture is the contribution** — it turns our
largest blind spot into the reason others contribute, which is the only realistic adoption path that
does not depend on marketing.

**This changes a core module. It is a decision, not a task.**

---

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

## 7. Sequencing

1. **Default rewriter change** — measured, small, currently costs every full-tier user a result.
2. **`untell-audit` + CI claim checking** — converts tonight's one-off discipline into a standing property.
3. **Academic niche** (BibTeX verify, `.tex` round-trip) — where our strengths are the buying criteria.
4. **Language plugin architecture** — pending your decision; biggest ceiling, biggest refactor.
5. **GPU moat** — only with real hardware.

## 8. How we would know it worked

Not stars. These:

- **zero drifted claims** — CI proves every published number still reproduces
- **`neural` default clears ≥ 50% of real HC3 text** at full tier, replicated at `--repeats ≥ 3`
- **a `.tex` file round-trips** and still compiles, with every citation key intact
- **one non-English catalogue contributed by a native speaker** — the platform test
