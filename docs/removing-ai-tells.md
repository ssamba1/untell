# Removing AI tells: everything known, and what it is actually worth

One page for the question the rest of this repository circles: **given a piece of machine-written
text, what can be done to stop it reading as machine-written, and how far does each thing get?**

Every number here is measured in this repository and traceable to a committed artefact. Where a
technique could not be run, the row says *not tested* rather than reporting a zero — an untested
technique and an ineffective one produce identical cells, and telling them apart is most of what
makes a table like this worth reading.

## The field, as surveyed

`docs/humanizer-census.json` reads **435 repositories** and sorts them into twelve categories:

| category | repos | what it is |
|---|---|---|
| prompt-guide | 184 | instructions to an LLM; no code, no detector |
| api-wrapper | 75 | a paid humanizer behind a client |
| other | 46 | — |
| adversarial-perturbation | 39 | word-importance ranking, synonym swaps (PWWS/TextFooler class) |
| rule-based-rewriter | 38 | sentence-level transforms, deterministic |
| research-code | 19 | papers' released implementations |
| fine-tuned-model | 11 | a trained rewriting policy |
| paraphrase-model | 7 | T5/DIPPER-class paraphrasers |
| unicode-trickery | 7 | homoglyphs, zero-width characters |
| detector-with-evasion | 5 | a detector shipping its own bypass |
| back-translation | 3 | pivot through another language |
| dataset | 1 | — |

**Only 49 of 435 put a detector inside the loop.** That is the single largest structural difference
between the field and what this tool does, and it is why most of the field cannot tell you whether
its output works.

## What each class is worth, measured

25 machine-written abstracts, lite tier, one corpus, four axes
(MEASURED, `eval/data/technique_matrix.json`, reproduce with `python -m eval.technique_matrix`):

| technique | category | changed | P(AI) | tells/100w | Δstyle | hidden | foreign |
|---|---|---|---|---|---|---|---|
| none (control) | — | 0 | 0.3084 → 0.3084 | 0.32 → 0.32 | +0.0000 | 0 | 0 |
| homoglyph_substitute | unicode-trickery | 25 | 0.3084 → **0.3084** | 0.32 → 0.32 | −0.1220 | **641** | **641** |
| synonym_swap | adversarial-perturbation | **0** | 0.3084 → 0.3084 | 0.32 → 0.32 | +0.0000 | 0 | 0 |
| back_translation | back-translation | *not tested* — models absent | | | | | |
| structural | rule-based-rewriter | 22 | 0.3084 → 0.2823 | 0.32 → 0.23 | −0.0111 | 0 | 0 |
| targeted | rule-based-rewriter | 16 | 0.3084 → 0.2729 | 0.32 → 0.23 | −0.0052 | 0 | 0 |
| mt_pivot | back-translation | *not tested* — models absent | | | | | |
| t5_paraphrase | paraphrase-model | *not tested* — models absent | | | | | |
| ensemble | research-code | 18 | 0.3084 → 0.2655 | 0.32 → **0.09** | −0.0094 | 0 | 0 |
| composite (default) | rule-based-rewriter | 17 | 0.3084 → 0.2705 | 0.32 → **0.09** | −0.0080 | 0 | 0 |
| **our closed loop** | detector-in-loop | 15 | 0.3084 → **0.2652** | 0.32 → **0.09** | −0.0125 | 0 | 0 |

**Δstyle** is Burrows's Delta to a centroid built from machine-written text: positive would mean the
technique moved the document *away* from how machines write. Nobody in the census reports this axis.

### Three things this table shows that a single-axis table cannot

**1. Unicode trickery is sabotage with no measured benefit.** It changes every document, plants
**641 invisible or counterfeit characters**, and moves the detector score by **nothing at all**
(0.3084 → 0.3084). The output breaks search, spellcheck, screen readers and copy-paste, and a single
`unicodedata.normalize("NFKC", …)` undoes it. Seven repositories in the census are built on this.

**2. Word substitution is inert on prose that carries no catalogued tell.** `synonym_swap` changes
0 of 25 documents. The mechanism is in `untell/attacks/word_importance.py`: it ranks words by whether
swapping one removes a tell, and 36 of 40 machine-written abstracts carry no catalogued tell at all,
so the ranking is empty and the loop never runs an iteration. The 39 adversarial-perturbation repos
in the census inherit this limit whenever the detector cannot see a synonym swap — which, measured,
this one cannot.

**3. Nothing moves the document's style.** Every technique that works has **negative** Δstyle: they
all move the document *toward* the machine centroid while lowering its score. The gains are
detector-specific, not stylometric. That is the in-loop-versus-held-out gap the free-ceiling report
calls the central unknown, made concrete on one corpus.

## So what actually works, and how well

**The closed loop is the best available here** — lowest P(AI) (0.2652) and lowest tells (0.09/100w),
without touching a single character a reader cannot see. That is a real answer, and it is a modest
one: a drop of **0.043** in P(AI) on this corpus, not a document that stops looking machine-written.

The honest ceiling statement, from `docs/free-ceiling-measured.md` and unchanged by this page: high
against the open detectors you can put in the loop, **unprovable against the commercial detectors
you cannot**, and no verified training-free method reaches the published 92–97.6% attack success,
which requires GPU fine-tuning.

## Why "remove all AI tells" is the wrong target, measured

The phrase assumes AI tells are a property of the text that can be deleted. Two measurements in this
repository say otherwise.

**The tell catalogue detects register, not authorship.** Holding the author constant and varying only
register, `references/ai-tells.md` separates the two at **AUROC 1.0000**; holding register constant
and varying authorship at matched length, it separates them at **0.2697** — worse than chance
(rounds 81–82 of the verification ledger). Removing catalogued tells makes text less *chatbot-register*,
which is not the same as less *machine-written*.

**And distance from a norm does not predict false positives the way the field assumes — it predicts
them the other way round.** Two instruments, two different centres, both on the 6,810 pre-ChatGPT
abstracts where every flag is a false accusation by construction:

| instrument | centre | statistic | result |
|---|---|---|---|
| `eval/homogenization.py` | the machine centroid | trend across 5 quintiles, function-word space | **z=+3.91, p=0.0001** |
| `eval/outlier_fairness.py --trend` | the corpus norm | trend across 5 quintiles, stylometric features | **z=+6.55, p≈0** |

Both rise. **Being stylistically unusual makes a human document *more* likely to be falsely flagged,
not less** — so "move away from how machines write" is not a strategy the data supports, and the
writers who already sit furthest from the norm are the ones absorbing the false accusations.

⚠️ Outlier status is not a protected characteristic. This establishes that a detector's false
accusations concentrate on the margins; it does not establish which margin.

## Who gets falsely accused, and whether a verdict is supportable at all

Removal and false accusation are the same question from two ends, and the tools for the second half
live here too. All three run on the pre-ChatGPT corpus, where **every flag is a false positive by
construction** because the text predates the model.

**Being unusual costs you.** Two instruments, two different centres, agreeing:

| instrument | centre | result |
|---|---|---|
| `python -m eval.homogenization --all --sweep` | machine centroid, function words | **z=+3.91, p=0.0001** |
| `python -m eval.outlier_fairness --trend` | corpus norm, stylometric features | **z=+6.55, p≈0** |

False-positive rate **rises** with distance from a norm. Detectors do not flag a writer for
resembling the model; they flag a writer for departing from the reference human distribution.

**Whether that explains the L2 finding is measured and unsettled.** `python -m eval.native_distance`
uses the one reachable corpus with self-declared author status (36 Native, 36 Non-Native): non-native
authors sit **+0.0394** further from the function-word centre, p=0.098, and **+0.0441**
length-matched, p=0.066. The right direction in both arms, neither significant, and the effect size
implies **~79–104 per group** to settle it. Reported alongside: in that corpus the *native* writers
were flagged more often (13.9% vs 5.6%), on 7 flags total.

**And on the free tier, no threshold supports a verdict.** `python -m eval.calibrated_thresholds`
fixes the bar per length band by split conformal prediction. It works — 60–100 word documents go from
**29.1% to 3.6%** false positives — and the sensitivity column is why that is not a win:

| band | FPR at 0.45 | FPR calibrated | TPR at 0.45 | TPR calibrated |
|---|---|---|---|---|
| 50–100 | 29.1% | **3.6%** | 9.3% | 2.3% |
| 100–200 | 15.8% | **4.8%** | 9.1% | 0.0% |

Sensitivity is 9% before calibration and 0–2% after. **This tier cannot support a verdict at any
threshold** — a stronger conclusion than "better thresholds", and visible only because both columns
are reported.

## What would actually raise the ceiling

Ranked by measured or published magnitude, not by appeal:

1. **A trained policy.** StealthRL reports 97.6% attack success with GRPO + LoRA on Qwen3-4B rewarded
   by a free open-detector ensemble — a setup that fits a free Colab T4. This repo's items 15–17 are
   blocked on exactly this and on nothing else.
2. **A real detector in the loop.** 49 of 435 repos manage it; the free web UIs are the only
   commercial-adjacent signal available at $0, and they are slow and bot-gated.
3. **A paraphrase model.** DIPPER-class rewriting is the strongest published training-free lever, and
   three rows above are *not tested* here. ⚠️ **Not because torch is missing.** MEASURED:
   `pip download torch` fetches a 554.6 MB wheel without trouble — PyPI is reachable — while
   `https://huggingface.co/` returns **403, CONNECT tunnel failed**, and there is no weight cache
   anywhere on the machine. The blocker is an organization egress policy on the model host, so
   installing 554 MB of torch would not make one of those rows measurable. Saying "torch is absent"
   invites a reader to install it and find that out for themselves; `eval/technique_matrix.py`
   probes and reports which of the two walls it hit.
4. **Not unicode trickery, and not word substitution alone** — measured above at zero and zero.

## Reproducing every number on this page

```
python -m eval.technique_matrix --n 25          # the table
python -m eval.homogenization --all --sweep     # distance vs false positives, machine centroid
python -m eval.outlier_fairness --trend         # the same, against the corpus norm
python -m eval.native_distance                  # do non-native authors sit further out?
python -m eval.calibrated_thresholds --all      # per-length thresholds, and what they cost
python -m eval.compare_humanizers               # the head-to-head, full tier
python -m untell.scripts.audit                  # every figure here has a stated source
```
