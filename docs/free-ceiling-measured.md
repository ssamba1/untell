# Measured: untell's inference-only evasion ceiling (the number the literature is missing)

The companion [`free-ceiling-report.md`](free-ceiling-report.md) names, as the #1 free move,
*"measure untell's inference-only evasion against the local open detectors — the literature has no
data point in this regime."* Every prior attempt to produce it was blocked by a broken local torch
stack. With a working CPU torch build (`torch 2.12.1+cpu`, `transformers 5.12.1`) the full local
ensemble runs, so this is that measurement.

It is deliberately small and honest. It is **not** a benchmark against GPTZero / Originality /
Turnitin — those cannot be queried for free and are out of scope by construction (see the report).
It measures exactly one thing: **how far a free, training-free rewrite moves the local open-detector
ensemble that untell can actually put in its loop.**

> **Read [Result 6](#result-6--re-measured-on-a-working-perplexity_burstiness-supersedes-result-5s-table)
> for the current numbers.** Every earlier result was measured while `perplexity_burstiness` — the
> one detector present at every tier — was anti-correlated and saturating.
>
> The corrected figure, measured at `--repeats 9` (27 loop runs) after two 3-repeat runs disagreed:
> **Superseded by Result 9 — the current figure is 0.859 → 0.154 ± 0.042, flagged 1.00 → 0.000.**
> Everything below Result 7 was measured through two miscalibrated detectors, and Result 8 was
> measured before the loop was found to be discarding passing candidates.
>
> **0.859 → 0.261 ± 0.027, flagged rate 1.00 → 0.148.** Use `--repeats ≥ 9`; three repeats gave
> 0.247 ± 0.015 and 0.330 ± 0.118 on the same command.

> ## ⚠️ Read the corpus before reading any number here
>
> **Results 1–9 are all measured on the same three hand-written paragraphs** (mean 36 words), and
> that corpus is measurably *easier* than real AI output. On real HC3 ChatGPT answers the same loop,
> same settings, gives **0.999 → 0.860 ± 0.001, flagged 1.00 → 1.00** — not one sample cleared.
>
> | corpus | words | before | after | still flagged |
> |---|---|---|---|---|
> | built-in sample (Results 1–9) | 37 | 0.859 | **0.154** | **0%** |
> | real HC3 answers ([Result 11](#result-11--the-ceiling-against-real-ai-text-and-the-content-wall-coming-back)) | 195 | 0.999 | **0.860** | **100%** |
>
> Every figure below reproduces exactly as written, and each isolates the defect it was measuring.
> What none of them is, is a claim about real AI documents. Read
> [Result 10](#result-10--the-corpus-was-doing-more-work-than-anything-measured-above) and
> [Result 11](#result-11--the-ceiling-against-real-ai-text-and-the-content-wall-coming-back) first.

> **Read [Result 3](#result-3--superseding-update-the-content-wall-was-largely-a-selection-limit)
> next.** Results 1–2 were measured with the then-default `best_of=1`. Re-measuring with best-of-3
> selection cut mean max P(AI) roughly in half again (0.683 → **0.290**) and falsified this
> document's original claim that the content/genre detector cannot be moved (`hc3_roberta`
> 0.725 → **0.036–0.064**, replicated). Earlier sections are kept for the record with corrections
> marked inline.
>
> That falsification is itself scoped by Result 11: it holds on the built-in sample, and on real
> HC3 answers `hc3_roberta` only reaches **0.810**, which is what Results 1–2 originally described.
> Selection remains a large real lever — it takes `roberta_openai` to 0.088 on that same real text.

## Setup

- **Detector ensemble (full tier, `max` aggregation):** `roberta_openai`
  (`openai-community/roberta-base-openai-detector`), `hc3_roberta`
  (`Hello-SimpleAI/chatgpt-detector-roberta`), `fast_detectgpt` (EleutherAI/gpt-neo-125m), and the
  lite `perplexity_burstiness` heuristic. `mage` (`yaful/MAGE`) is excluded via
  `UNTELL_DISABLE_MAGE=1` — for **speed**, not because it is broken. That exclusion note used to
  read "a known, documented dead detector, its `id2label` config is rejected by current
  `huggingface_hub`"; the adapter has since normalised that config on load and MAGE runs (measured
  gap +0.666 on the audit probes). It is a Longformer and is roughly 50–100× slower on CPU than the
  base-size detectors, which is why the reproduce command still leaves it out.
- **Threshold:** `0.30` (untell's default — aggressive; most formulaic text flags).
- **Metric:** `max` P(AI) across the live detectors (the proxy untell drives down), reported as the
  per-corpus mean (`mean_max`) and the fraction still at/above threshold (`flagged_rate`).
- **Corpus:** formulaic AI-style paragraphs (the genre detectors are trained to catch). No locked
  facts needed — this measures detector *movement*, not meaning preservation (which the loop's
  similarity gate and sentinel lock handle separately and are tested elsewhere).
- **Reproduce:** `untell-ceiling --rewriter surgical --tier full` (the deterministic, no-key path).

## Result 1 — three free rewriters, head to head (n=3, full tier)

> ⚠️ **SUPERSEDED — historical, kept for the record.** Everything in this section was measured with
> `best_of=1` (the then-shipped default) and with `fast_detectgpt` emitting a constant. Its central
> conclusion — that no free rewriter reliably beats the proxies and that content-locked detectors
> cannot be moved — **did not survive re-measurement.** Current figures: [Result 5](#result-5--the-meaning-gate-was-the-binding-constraint-final-free-path-figure).

| Rewriter | Key needed? | flagged before → after | mean max P(AI) before → after |
|---|---|---|---|
| **surgical** (PWWS-style word substitution) | No | 1.00 → 0.67 | 0.859 → 0.759 |
| **back-translation** (EN→FR→EN, marian) | No | 1.00 → **1.00** | 0.859 → **0.995 (worse)** |
| **Claude-in-loop** (the skill's actual rewriter) | No¹ | 1.00 → 0.67 | 0.859 → 0.738 |

¹ Free inside Claude Code, where Claude *is* the rewriter (no API key).

### Per-paragraph, the real story is in the variance

| Paragraph | baseline | surgical | Claude-in-loop |
|---|---|---|---|
| 1 — "AI has transformed industries…" | 0.578 | **0.280** (pass) | **0.918 (worse)** |
| 2 — "cybersecurity has become paramount…" | 0.999 | 0.999 (stuck) | **0.296** (pass) |
| 3 — "climate change… pressing challenge…" | 0.999 | 0.999 (stuck) | 0.999 (stuck) |

Two findings fall straight out of this table, and both confirm the report's thesis rather than the
marketing of any humanizer:

1. **Surface edits cannot move a content/genre detector.** `roberta_openai` and `hc3_roberta` lock
   onto *what the paragraph is about and how it is structured*, not its surface words. Paragraphs 2
   and 3 sit at 0.999 and word-substitution (surgical) cannot move them at all. This is the
   *"the content is the tell, and you promised not to change the content"* result, measured.

2. **The local ensemble anti-correlates with human-ness on some text.** The Claude rewrite of
   paragraph 1 reads obviously more human ("AI has changed how a lot of industries work over the past
   few years…") yet scores **0.918 vs the robotic original's 0.578.** A meaning-preserving, genuinely
   more human rewrite made the *proxy* score go **up**. Optimizing hard against these proxies would
   therefore push the text *away* from human, not toward it — which is exactly why untell's rubric
   now treats the local score as a weak hint, not the objective.

Neither free rewriter is reliably better than the other on the proxies (both land ~0.74–0.76 mean
max, both clear 1 of 3). That is the honest inference-only picture: **a modest, unreliable drop —
nowhere near the 88–98% ASR the *trained* literature reports, and against the wrong target anyway.**

**Reproduced via the shipped CLI** (`untell-ceiling --rewriter surgical --tier full`, ~90 s on CPU),
the per-detector mean P(AI) before → after pins down *which* signal moves and which doesn't:

> ⚠️ **SUPERSEDED — see [Result 4](#result-4--re-measured-with-a-live-fast_detectgpt-supersedes-the-per-detector-table-above).**
> This table was measured with `best_of=1` AND with `fast_detectgpt` emitting a constant. Both of its
> conclusions were later falsified: `hc3_roberta` reaches **0.038** with best-of-N selection, and
> `fast_detectgpt` was not "flat" — it was broken, and moves 0.630 → 0.252 once calibrated.

| detector | before → after | what it keys on |
|---|---|---|
| `perplexity_burstiness` | 0.319 → **0.197** | surface predictability — moves most |
| `roberta_openai` | 0.523 → **0.361** | lexical/stylistic — moves |
| `hc3_roberta` | 0.725 → **0.670** | content/genre — ~~**barely budges**~~ *(falsified: 0.038)* |
| `fast_detectgpt` | 0.312 → 0.306 | curvature — ~~flat~~ *(falsified: detector was dead)* |

~~The content/genre detector (`hc3_roberta`) is the one a meaning-preserving rewrite cannot move — the
measured face of *"the content is the tell."*~~ **This conclusion did not survive re-measurement:**
with best-of-N selection `hc3_roberta` drops to 0.038. See Results 3 and 4.

## Result 2 — surgical floor on a larger sample (n=10, full tier)

> ⚠️ **SUPERSEDED — historical.** Measured with `best_of=1` (the then-default) and a broken
> `fast_detectgpt`. Kept for the record; the current figures are in Results 3 and 4.

The deterministic, reproducible, no-key path (`untell-ceiling --rewriter surgical --tier full`) on 10
formulaic AI paragraphs:

| Metric | before | after |
|---|---|---|
| flagged rate (max P(AI) ≥ 0.30) | 0.90 | **0.60** |
| mean max P(AI) | 0.870 | **0.683** |

Per-sample, the same split as the n=3 set: surgical substitution moves the perplexity/lexical-driven
paragraphs hard (0.578 → 0.280, 0.887 → 0.287, 0.948 → 0.281, 0.996 → 0.736) and is **near-powerless
against the content-locked ones** (0.999 → 0.999 on three of them). 3 of 10 cross the threshold; one
was already under it. The surgical lever is real but bounded: **it strips the lexical tell and stops
at the content tell** — a ~0.19 absolute drop in mean max P(AI), nowhere near the trained 97.6% ASR.

## Result 3 — SUPERSEDING UPDATE: the content wall was largely a *selection* limit

**The conclusions in Results 1–2 below are now known to understate the free ceiling substantially.**
They were measured with `best_of=1` — a single rewrite draw per iteration — which was the shipped
default at the time. It is not any more, and the difference is not small.

Re-measured with **best-of-3 selection against the same tier the loop scores on**, 3 repeats
(9 loop runs total, full tier minus `mage`, `--max-iters 2`), run twice independently:

| Metric | Results 1–2 (`best_of=1`) | Re-measured (`best_of=3`), run A | run B |
|---|---|---|---|
| flagged rate (max P(AI) ≥ 0.30) | 0.90 → 0.60 | 1.00 → **0.111** | 1.00 → **0.222** |
| mean max P(AI) | 0.870 → 0.683 | 0.859 → **0.290 ± 0.018** | 0.859 → **0.297 ± 0.018** |

Per-detector mean P(AI), before → after (both runs):

| detector | before | run A after | run B after | earlier claim |
|---|---|---|---|---|
| `perplexity_burstiness` | 0.319 | 0.068 | 0.104 | moves most ✓ |
| `roberta_openai` | 0.523 | 0.097 | 0.104 | moves ✓ |
| **`hc3_roberta`** | 0.725 | **0.064** | **0.036** | *"barely budges"* ✗ **falsified** |
| `fast_detectgpt` | 0.312 | 0.282 | 0.284 | flat ✓ |

**The headline correction:** Results 1–2 concluded that `hc3_roberta` — the content/genre detector —
*"is the one a meaning-preserving rewrite cannot move,"* the measured face of *"the content is the
tell."* With best-of-N selection it drops to **0.036–0.064**. That wall was mostly a **selection**
limitation, not a structural one: a single draw rarely finds a phrasing that clears a content
detector, but three draws scored against that detector usually do. The lever was never a better
rewriter — it was *choosing among rewrites against the signal you actually care about*, and that was
shipped disabled.

> **SCOPE CORRECTION (Result 11).** This falsification holds *on the built-in sample*, and the
> built-in sample turns out to be the easy case. Re-run against real HC3 ChatGPT answers with the
> same selection, `hc3_roberta` goes **0.998 → 0.810** — barely moved, exactly as Results 1–2
> described. Best-of-N selection is still a real and large lever, and everything measured below
> stands for the corpus it was measured on; what does not stand is reading "the content wall was a
> selection limit" as a general claim. See Result 11.

### How far does selection scale? (best-of-3 vs best-of-8)

Same corpus, same 3 repeats, only `--best-of` changed:

| Metric | `best_of=1` | `best_of=3` (A / B) | `best_of=8` |
|---|---|---|---|
| flagged rate | 0.60 | 0.111 / 0.222 | **0.000** |
| mean max P(AI) | 0.683 | 0.290 / 0.297 | **0.281** |
| stdev across runs | — | 0.018 | **0.009** |
| mean similarity | — | — | **0.959** (worst 0.927) |

**Selection buys reliability, not a lower average.** Going 3 → 8 barely moved the mean (0.29 → 0.28)
but *halved the run-to-run spread* and took the flagged rate to **zero** — every sample cleared the
threshold in all three runs. The mean is near its floor; what more draws fix is the tail, i.e. the
occasional paragraph that a small sample of drafts fails to find a good rewrite for.

Meaning held throughout: **0.959 mean similarity, 0.927 worst case** — this is not evasion bought by
mangling the text.

The cost is linear: `best_of=8` runs 8 rewrites and 8 full-tier detector passes per iteration. The
shipped default is **3** as the reliability/cost knee; use `--best-of 8` when it matters and you can
spend the CPU. (Deterministic rewriters short-circuit to a single draw — extra draws would be
byte-identical.)

### Result 4 — re-measured with a LIVE fast_detectgpt (supersedes the per-detector table above)

Every number above was computed while `fast_detectgpt` was emitting a near-constant ~0.30 for any
input (the calibration bug fixed in `925beaf`). Re-measured on the repaired detector, same config
(best-of-3, 3 repeats, 9 loop runs):

| detector | before | after | delta |
|---|---|---|---|
| `perplexity_burstiness` | 0.319 | **0.045** | −0.274 |
| `roberta_openai` | 0.523 | **0.069** | −0.454 |
| `hc3_roberta` | 0.725 | **0.038** | −0.687 |
| **`fast_detectgpt`** | **0.630** | **0.252** | **−0.378** |

| Metric | value |
|---|---|
| flagged rate | 1.00 → **0.222** |
| mean max P(AI) | 0.859 → **0.255 ± 0.030** |
| meaning similarity | **0.959 mean, 0.935 worst** |

**This falsifies the "one wall did not fall" caveat stated throughout the earlier sections.** With a
working calibration, `fast_detectgpt` turns out to have been the *strongest* baseline AI signal
(0.630, not 0.312) — and it moves, by −0.378. It never appeared to move before because it never
responded to anything.

So the honest picture is now: **all four local detectors move substantially, and meaning holds at
0.96 similarity.** The remaining caveat is the one that actually matters and is unchanged — this is
the local proxy ensemble, and clearing it says nothing about GPTZero / Originality / Turnitin. The
documented anti-correlation (a rewrite that reads *more* human can score *worse* locally) also
stands.

### Result 5 — the meaning gate WAS the binding constraint (final free-path figure)

Results 3–4 optimised selection. This one tests the hypothesis that fell out of them: that the
*meaning gate*, not the rewriter or the detectors, was capping the free ceiling. Cosine similarity
penalises register change — it rejected 6/8 faithful formal→casual rewrites — so the loop was
structurally unable to adopt the most natural humanizing move. Replacing it with the NLI gate
(contradiction veto + bidirectional entailment) and adding the plain-register vocabulary pass:

| Metric | selection only (Result 4) | **+ NLI gate + register shift** |
|---|---|---|
| flagged rate | 0.222 | **0.111** |
| mean max P(AI) | 0.255 ± 0.030 | **0.214 ± 0.012** |
| `perplexity_burstiness` | 0.045 | **0.028** |
| `roberta_openai` | 0.069 | **0.051** |
| `hc3_roberta` | 0.038 | **0.020** |
| `fast_detectgpt` | 0.252 | **0.214** |
| embedding similarity | 0.959 / 0.935 worst | 0.944 / 0.900 worst |

**The hypothesis holds.** Every detector dropped further, the flagged rate halved, and the run-to-run
spread more than halved (0.030 → 0.012). Overall: **0.859 → 0.214**, a 75% reduction in mean max
P(AI) from the untouched AI baseline.

**On the similarity figure**, which fell 0.959 → 0.944: that is the expected and intended
consequence, not a quality regression. The entire point of the change is to permit rewrites that
*cosine similarity scores low but that preserve meaning* — the register shifts it was measured to
penalise. Fidelity is now enforced by the NLI gate instead (contradiction < 0.5 AND bidirectional
entailment ≥ 0.005), which on a fixed probe set admitted 7/8 faithful rewrites and **0/11**
meaning-lost or inverted ones, versus 2/8 and 4/11 for the similarity bar it replaced. A lower score
on a metric proven unreliable for this transformation is not evidence of lost meaning.

### What this measurement does NOT cover

The built-in corpus is formulaic AI prose with **no citations, numbers, quotes or named entities** —
measured, `preserve.lock` finds **0 locked spans in all three paragraphs**. So every ceiling figure
here exercises the rewriters and the meaning gate, and never once exercises the fact-preservation
machinery that is the product's other half.

That is not a flaw in the numbers — detector movement is what they claim to measure — but it does
mean **a regression that corrupted citations or numbers would not show up anywhere in this
document.** Those guarantees are covered separately by `tests/test_end_to_end_guarantees.py`, which
runs the real loop over fact-bearing text and asserts every locked span survives byte-exact. Read
the two together; neither alone describes the system.

Two honest caveats that keep this from being a "solved" claim:

1. ~~**`fast_detectgpt` did not move** (0.312 → ~0.283 in both runs). The curvature signal is
   untouched by everything measured here. One wall fell; another did not.~~
   **RETRACTED — it was a broken detector, not a wall.** Investigating why this one number never
   budged in *any* configuration turned up the cause: its logistic calibration constants
   (`_CAL_MID = 1.0`) assumed a curvature range the model never produces. Measured, the discrepancy
   lands in ~[-0.20, 0.38], so the midpoint sat outside the entire observed range and **squashed
   every input to ~0.30 regardless of content**. It never moved because it never responded to
   anything. Recalibrated in `925beaf` (`_CAL_MID = -0.03`, `_CAL_SCALE = 0.12`); the output now
   spans 0.20–0.97.
   **Consequence for the numbers above:** every per-detector and ensemble figure in this document
   was computed with that detector contributing a constant ~0.30 to a `max`/`mean` aggregation. The
   `hc3_roberta` and `roberta_openai` movements are unaffected (they were measured directly), but
   the *ensemble* means are stale and are being re-measured.
   Its own honest limitation remains: even recalibrated, the curvature distributions overlap so
   heavily at paragraph length with a 125m scoring model that the human/AI direction flips on small
   samples. It is a weak signal, now at least a *live* one.
2. **This is still the local proxy ensemble.** Nothing here says anything about GPTZero / Originality
   / Turnitin, and the separately established anti-correlation result (a rewrite that reads *more*
   human can score *worse* locally) is unchanged. A low local score still does not mean "passes a
   commercial detector."

### Result 6 — re-measured on a *working* `perplexity_burstiness` (supersedes Result 5's table)

Result 5's numbers were taken while the lite detector — the one detector present at every tier —
was itself broken. It scored each sentence **in isolation** and averaged, discarding the context
that makes generated text predictable, and its linear clamps floored a large class of ordinary
input to exactly `0.0`. Measured on paragraph-length text it was *anti-correlated*: AI text scored
**below** human text (gap −0.198). Rewritten as a single in-context pass with logistic calibration
fitted to labelled HC3 pairs (AUROC **0.999** on 200 held-out pairs, nothing saturated), the same
config re-run — `best-of 3`, `max-iters 2`, 3 repeats, 9 loop runs:

| detector | before (Result 5) | **before (live detector)** | after (Result 5) | **after (9 repeats)** |
|---|---|---|---|---|
| `perplexity_burstiness` | 0.319 | **0.604** | 0.028 | **0.194** |
| `roberta_openai` | 0.523 | 0.523 | 0.051 | **0.113** |
| `hc3_roberta` | 0.725 | 0.725 | 0.020 | **0.022** |
| `fast_detectgpt` | 0.630 | 0.630 | 0.214 | **0.225** |

| Metric | Result 5 | **re-measured (9 repeats)** |
|---|---|---|
| flagged rate | 1.00 → 0.111 | 1.00 → **0.148** |
| mean max P(AI) | 0.859 → 0.214 ± 0.012 | 0.859 → **0.261 ± 0.027** |
| meaning similarity (cosine) | 0.944 / 0.900 worst | 0.930 / 0.825 worst |

**The headline moved in both directions and both matter.** The *baseline* for
`perplexity_burstiness` was understated by nearly half (0.319 → 0.604): a broken detector had been
reporting formulaic AI text as barely suspicious, so the "before" picture flattered the corpus. And
the *after* figure is worse than Result 5 claimed (0.214 → 0.261), because the 0.028 it recorded for
that detector was a number the loop never really had to earn — on a live detector it only reaches
0.194.

Result 5's flagged rate (0.111) and this one (0.148) are within noise of each other at these sample
sizes; the meaningful change is the mean and the per-detector baseline, not the flag count.

⚠️ **Neither 3-repeat run was trustworthy on its own.** Running the identical command a second time
gave a materially different answer, so it was re-run at `--repeats 9`:

| run | repeats | loop runs | mean max P(AI) | stdev | flagged | per-repeat means |
|---|---|---|---|---|---|---|
| first | 3 | 9 | 0.247 | 0.015 | 0.000 | 0.265 / 0.248 / 0.228 |
| second | 3 | 9 | 0.330 | 0.118 | 0.444 | 0.252 / **0.496** / 0.241 |
| **third** | **9** | **27** | **0.261** | **0.027** | **0.148** | 0.212 – 0.297, no outlier |

**The 9-repeat figure is the one to quote: 0.859 → 0.261 ± 0.027, flagged 1.00 → 0.148.**

| detector | before | after (27 runs) |
|---|---|---|
| `perplexity_burstiness` | 0.604 | **0.194** |
| `roberta_openai` | 0.523 | **0.113** |
| `hc3_roberta` | 0.725 | **0.022** |
| `fast_detectgpt` | 0.630 | **0.225** |

meaning similarity 0.930 mean / 0.825 worst.

Two lessons, and the second corrects an explanation this section briefly carried:

1. **Three repeats is not enough**, and a low stdev across three does not mean the estimate is
   stable — the first run's ±0.015 came from drawing three low values in a row, and the second run
   contained a single 0.496 that dragged its mean up by 0.08. Nine repeats produced a range of
   0.212–0.297 with no outlier at all.
2. An earlier draft blamed **corpus size** and said `--repeats` "cannot average away a paragraph
   that is simply harder than the others". That was wrong, and the 9-repeat run disproves it: the
   variance was in the **rewriter's randomness**, not the corpus, and repeats did average it out
   (stdev 0.118 → 0.027). `n=3` still limits how far the result generalises — it says nothing about
   other genres — but it was not what made the number jump.

The cosine similarity figure falls again (0.944 → 0.916 mean, 0.900 → 0.815 worst). The same caveat
as Result 5 applies and is now stronger: fidelity is enforced by the NLI gate plus a
**predicate-argument veto** (`scripts/roles.py`) that rejects rewrites permuting who did what to
whom — a class NLI scores at 0.99 entailment and lets straight through. On the fixed probe set the
gate now admits **0 of 13** meaning-changing rewrites (was 4 of 13) while still admitting 8 of 8
faithful ones. Cosine is a reporting metric here, not the guarantee.

*Reproduce:* `UNTELL_DISABLE_MAGE=1 untell-ceiling --rewriter composite --tier full --best-of 3
--max-iters 2 --repeats 3 --json`. Use `--repeats ≥ 3`: the free rewriters are randomized, and a
single pass is not evidence — the same config moved a mean from 0.080 to 0.144 across two runs before
repeats existed. The harness also reports `mean_similarity` / `min_similarity` so an evasion number
can never be read without the meaning fidelity it cost.

## What this establishes

> **Superseded in part — read Result 3 first.** The bullets below were written from the `best_of=1`
> measurements and their central claim about the content detector has since been **falsified by
> replicated measurement**. They are kept for the record, with the corrections marked.

- The free, training-free inference regime sits **far below** the published trained ceiling
  (StealthRL 97.6% ASR), exactly as the report predicted. ~~The gap is structural (content-locked
  detectors + a non-transferring proxy).~~ **Correction:** the *content-locked* half of that
  explanation did not survive. With best-of-N selection `hc3_roberta` falls 0.725 → 0.036–0.064. The
  non-transferring-proxy half stands, and `fast_detectgpt` remains unmoved.
- The single most reliable free lever measured here is ~~surgical word substitution~~ **selecting
  among several rewrite draws against the tier you actually score on** (best-of-N). That, not any
  individual rewriter, produced the entire difference between "the content tell is immovable" and
  hc3 at 0.036.
- ~~**No free rewrite reliably clears the local ensemble on content-heavy formulaic text.**~~
  **Correction:** best-of-3 clears it on 78–89% of samples (flagged rate 1.00 → 0.11–0.22). What
  remains true, and is the part that matters: **clearing the local ensemble does not imply clearing
  GPTZero** (separately established: RADAR 0.008 vs GPTZero 100% on the same text).

The ceiling, restated from the replicated numbers: **for free you can strip the lexical/perplexity
tells AND — with best-of-N selection — most of the content/genre signal too; the curvature signal
(`fast_detectgpt`) still does not move; and the local proxies remain a noisy, partly anti-correlated
stand-in for the commercial detectors you actually care about.** The honest product stance is
unchanged: a low local score is not a claim about GPTZero, Originality, or Turnitin.

*Numbers produced on **CPU** with the project's own detector ensemble and rewriters; reproduce the
current (Result 3) figures with `UNTELL_DISABLE_MAGE=1 untell-ceiling --rewriter composite --tier full
--best-of 3 --max-iters 2 --repeats 3`, and the historical Results 1–2 with
`untell-ceiling --rewriter surgical --tier full`. Run on CPU for reproducibility —
GPU float ops are not bit-exact, so the perplexity detector can drift run-to-run. The surgical rewriter
is deterministic, so the loop converges in one effective pass and stops early (`stopped: "stalled"`)
rather than burning all iterations. n is small and the corpus is formulaic by design; treat these as
the first data points in an unmeasured regime, not a benchmark.*

---

## Result 8 — the detectors were over-scoring everything, including the loop's own output

Every number above was measured with two miscalibrated detectors. Found by asking a question the
audit never asked: **what does this tool say about text a human wrote?**

Measured on 40 HC3 pairs at the default 0.30 threshold:

| detector | human mean | human flagged | AI caught |
|---|---|---|---|
| `fast_detectgpt` | 0.510 | **92%** | 100% |
| `perplexity_burstiness` | 0.244 | 32% | 100% |
| `hc3_roberta` | 0.000 | 0% | 100% |
| `roberta_openai` | 0.006 | 0% | 100% |
| **ensemble (max)** | **0.520** | **95%** | 100% |

The ensemble aggregates with `max`, so one badly-scaled detector sets the floor: the full tier
flagged 95% of human documents. A user running `untell-score` on their own writing would be told it
was machine-generated, and the loop would rewrite it — spending meaning-similarity to fix nothing.

**Both were calibration, not discrimination.** AUROC was 0.999+ for both throughout, and moved by at
most 0.001 when fixed. `fast_detectgpt` had its logistic midpoint at the *human mean*
(`_CAL_MID = -0.03` against human -0.023, AI +0.265); `perplexity_burstiness` had its midpoints at
the *class midpoint* (`_NLL_MID = 3.036` against human 3.85, AI 2.23). Both are intuitive places to
put a midpoint and both are wrong: what matters is where the THRESHOLD falls relative to the human
distribution, not where the classes divide.

Refit on 40 pairs, validated on 60 unseen:

| | fit FPR/TPR | held-out FPR/TPR | held-out AUROC |
|---|---|---|---|
| `fast_detectgpt` MID -0.03 SC 0.12 | 92% / 100% | 88% / 100% | 0.996 |
| `fast_detectgpt` MID +0.20 SC 0.08 | 8% / 100% | **2% / 97%** | 0.996 |
| `perplexity_burstiness` MID 3.036 / 0.625 | 32% / 100% | 37% / 100% | 1.000 |
| `perplexity_burstiness` MID 2.680 / 0.400 | 5% / 100% | **12% / 100%** | 0.999 |

End state, human text at the default threshold: full ensemble 95% → **12%**, lite 32% → **5%**, AI
still caught 100% in both.

### What this does to the ceiling

Re-measured with `--repeats 9` (27 loop runs), same command as Result 7:

| | Result 7 (before) | Result 8 (after) |
|---|---|---|
| mean max P(AI) | 0.859 → 0.261 ± 0.027 | 0.859 → **0.184 ± 0.035** |
| flagged rate | 1.00 → 0.148 | 1.00 → **0.074** |
| meaning similarity | — | 0.936 mean, 0.835 worst |

The *before* figure is unchanged at 0.859 — AI text is flagged just as confidently, which is the
point. The *after* figure improved because the detectors had been over-scoring the loop's output
the same way they over-scored human writing. The rewriter did not get better; the ruler got
accurate.

Per detector, before → after: `hc3_roberta` 0.73 → 0.05, `roberta_openai` 0.52 → 0.11,
`perplexity_burstiness` 0.41 → 0.14, `fast_detectgpt` 0.21 → 0.02.

### Method note

`untell-detector-audit` reported both detectors as healthy the entire time, because it reported
AUROC — a threshold-free measure that asks whether a detector *ranks* the classes correctly, which
both did perfectly. It cannot see a detector that ranks correctly and reports on a scale that puts
ordinary human prose over the line. The audit now reports FPR and TPR at the default threshold and
has a `MISCALIBRATED` verdict for exactly this shape.

**The general lesson: a discrimination metric cannot validate a decision rule.** Anything that
ships a threshold has to be measured at that threshold.

---

## Result 9 — the loop was discarding passing candidates

Result 8's numbers were measured before three control-flow defects in `run.py` were found by a
multi-agent probe sweep. Two of them made the loop throw away work it had already done.

**The best-of-N tie-break could discard a passing candidate.** Candidates within `_TELLS_EPS`
(0.02) of the best score are treated as tied and the fewest AI tells wins. That band is symmetric,
so when the best candidate sits just under the threshold it straddles it:

    candidate A   max 0.28  (passes)      2 tells
    candidate B   max 0.30  (does not)    0 tells
    -> B adopted, loop never stops on 'passed', burns every remaining iteration

**Polish could un-pass an already-passing result.** Same epsilon band, same straddle: incumbent
0.28, polished 0.30 with fewer tells, adopted — and the run returned `stopped='passed'` together
with `flagged=True`. One result asserting both.

A preference meant only to break ties was deciding losses. Both now refuse to trade a pass.

Re-measured, same command, `--repeats 9` (27 loop runs):

| | Result 8 | Result 9 |
|---|---|---|
| mean max P(AI) | 0.859 → 0.184 ± 0.035 | 0.859 → **0.154 ± 0.042** |
| flagged rate | 1.00 → 0.074 | 1.00 → **0.000** |
| meaning similarity | 0.936 mean, 0.835 worst | 0.931 mean, 0.868 worst |

Per detector, before → after: `hc3_roberta` 0.73 → 0.06, `roberta_openai` 0.52 → 0.08,
`perplexity_burstiness` 0.41 → 0.12, `fast_detectgpt` 0.21 → 0.03.

The *before* figure is unchanged at 0.859 for the third measurement running, which is the control
that makes the rest readable: nothing about how AI text is scored has moved.

**Every sample now clears the threshold.** That is a flagged rate of zero against the local open
ensemble at `--best-of 3`, not against a commercial checker — the local tier is the thing being
optimised against, so this number is a ceiling on THIS ensemble and says nothing about GPTZero.
`untell-verify` against a real commercial API remains the only honest test, and the meaning gate
is what stops the number being bought with a mangled rewrite: worst-case similarity 0.868.

---

## Result 10 — the corpus was doing more work than anything measured above

Every figure in this document, Results 1 through 9, was measured on the same three paragraphs:
`eval/ceiling.py::_SAMPLE`, **hand-written, mean 36 words**. They were composed to read as AI, and
they do. They are also **measurably easier than real AI output**, which nothing here had checked.

Length and corpus are separable, so they were separated: HC3 ChatGPT answers were truncated to the
built-in sample's own length and run through the identical loop (tier=full, `--best-of 3`,
`--max-iters 5`, n=6).

| corpus | words | before | after | still flagged |
|---|---|---|---|---|
| built-in sample (every result above) | 37 | 0.859 | **0.234** | **0%** |
| HC3 ChatGPT answers, truncated to 36w | 36 | 0.998 | **0.628** | **50%** |
| HC3 ChatGPT answers, full length | 186 | 0.999 | **0.762** | **83%** |

**The gap is the corpus, not the length.** At identical length the built-in sample ends three times
lower and clears every sample, because it *starts* at 0.859 where real ChatGPT answers start at
0.998. The "before" figure that Results 6-9 relied on as a stable control — unchanged at 0.859
across three re-measurements — is stable because the corpus never changed, not because 0.859 is
what AI text scores.

Length then adds on top of that, and for a structural reason. Detectors window long text and
aggregate with `max`, so a document is only as clean as its **worst** window and the loop has to
clear every one of them rather than one. A separate sweep over concatenated HC3 answers:

| paragraphs | words | before | after | still flagged |
|---|---|---|---|---|
| 1 | 203 | 1.000 | 0.757 | 100% |
| 2 | 348 | 1.000 | 0.999 | 100% |
| 3 | 556 | 1.000 | 0.999 | 100% |
| 5 | 994 | 1.000 | 0.999 | 100% |
| 8 | 1601 | 1.000 | 0.999 | 100% |

Windowing itself did not introduce false positives — human text measured 0.000 in every window at
every length — so this is the loop failing to clear a long document, not the detector misreading
one.

### What this changes

Not the numbers. Results 1-9 reproduce exactly as written, and each still isolates the defect it was
measuring: the calibration bugs, the discarded passing candidates and the selection limit were all
real, and fixing them all moved the same corpus from 0.261 to 0.154.

What changes is **what those numbers can be read as saying**. `0.859 → 0.154, flagged 0.000`
describes the loop's mechanics on short, easy, single-window text. It is not the ceiling against a
real AI-written document, which on this evidence is closer to **0.63 at snippet length and 0.76 at
paragraph length, with most documents still flagged**.

That was invisible for nine results because the corpus was never a variable. `measure_ceiling` now
records `corpus` and `corpus_mean_words` in its result, a built-in-sample run prints a note saying
so, and `untell-ceiling --dataset hc3|raid|mage` runs the same measurement on real generated text —
refusing to run at all if the dataset silently falls back to the built-in sample, which would put a
demo number under a real corpus's name.

**The next frontier is length, not phrasing.** Clearing one window is solved; clearing every window
of a 600-word document is not, and `max`-over-windows means the second does not follow from the
first.

> **CORRECTION (Result 12).** That last paragraph overstates the length effect. Measured per text,
> a *single* 199-word HC3 paragraph already ends at 0.999 on its own, while a 207-word one reaches
> 0.403 — the spread is between texts, not along length. What the sweep above actually shows is
> `max` over a corpus of uneven difficulty: adding paragraphs adds chances to include a hard one,
> and `max` reports the worst. Both descriptions predict the same table; only the second survives
> measuring a single paragraph. See Result 12.

---

## Result 11 — the ceiling against real AI text, and the content wall coming back

Result 10 showed the corpus mattered. This is the measurement it implies, run properly:
**8 real HC3 ChatGPT answers, mean 195 words, `--repeats 3` (24 loop runs), full tier,
`--best-of 3`, `--max-iters 5`.**

```bash
UNTELL_DISABLE_MAGE=1 untell-ceiling --dataset hc3 --n 8 --rewriter composite \
  --tier full --best-of 3 --max-iters 5 --repeats 3
```

| | built-in sample (Result 9) | real HC3 answers |
|---|---|---|
| mean max P(AI) | 0.859 → **0.154 ± 0.042** | 0.999 → **0.860 ± 0.001** |
| flagged rate | 1.00 → **0.000** | 1.00 → **1.000** |
| meaning similarity | 0.931 mean / 0.868 worst | 0.981 mean / 0.945 worst |

Per detector, before → after:

| detector | before | after | verdict |
|---|---|---|---|
| `roberta_openai` | 0.993 | **0.088** | crushed |
| `fast_detectgpt` | 0.640 | **0.260** | moves well |
| `perplexity_burstiness` | 0.619 | **0.429** | moves |
| **`hc3_roberta`** | 0.998 | **0.810** | **barely moves** |

**Not a single sample cleared the threshold**, and the standard deviation across three repeats is
**0.0012** — this is not a variance problem the way the built-in sample's was. The loop hits the
same wall every run.

### The wall is `hc3_roberta`, and it is not a lack of effort

The obvious explanation — that the meaning gate is holding the rewriter back on harder text — is
wrong, and worth stating because the similarity number invites it. Similarity sits at 0.98 here
against 0.93 on the built-in sample, which reads like the loop is making smaller changes. Measured,
it is not:

| corpus | words | tokens changed | similarity | final |
|---|---|---|---|---|
| built-in | 34–39 | 78–100% | 0.90–0.96 | 0.20–0.28, passed |
| HC3 | 146–207 | **89–93%** | 0.97–0.997 | 0.51–0.999, max_iters |

Nine tokens in ten are rewritten and the content detector does not care. Similarity stays high
*because* the rewrite is faithful — it is a content metric, and so is `hc3_roberta`. The loop is
doing the work; the signal it is being asked to move is the one thing a meaning-preserving rewrite
is not allowed to change.

`roberta_openai` at 0.993 → 0.088 on the same text is the control that makes this readable: the
rewriter is not weak, and the loop is not broken. One detector is measuring style and one is
measuring subject matter.

### Caveat: `hc3_roberta` has home-field advantage on this corpus

`hc3_roberta` is trained **on HC3**, and this measurement is on HC3. Auditing all four detectors at
threshold 0.30 over 100 held-out pairs makes that visible:

| detector | FPR | TPR | AUROC | human mean | AI mean |
|---|---|---|---|---|---|
| `perplexity_burstiness` | 6.0% | 98.0% | 0.9972 | 0.129 | 0.601 |
| `roberta_openai` | 2.0% | 98.0% | 0.9990 | 0.015 | 0.975 |
| **`hc3_roberta`** | **0.0%** | 98.0% | **1.0000** | **0.000** | 0.979 |
| `fast_detectgpt` | 2.0% | 100.0% | 0.9955 | 0.085 | 0.667 |
| ensemble (`max`) | 10.0% | 100.0% | — | — | — |

A perfect 1.0000 with a human mean of exactly 0.000 is the signature of **in-distribution
evaluation**, not of a generally perfect detector. So part of the 0.810 wall may be train/test
overlap rather than a property of AI text — the mirror image of the built-in sample's problem, with
the bias pointing the other way. Result 10's lesson applies to this result too: a number is a
property of its corpus until measured on another one.

The ensemble row is worth noting separately: individual false-positive rates of 0–6% combine into
**10%** under `max` aggregation, because the union of four detectors' mistakes is what `max`
reports. That is the documented cost of using `max` as a verdict rather than as a loop target.

### What this means for the claims in this document

- Result 3's falsification of the content wall **holds on the built-in sample and does not
  generalise.** Best-of-N selection remains a large, real lever — it is what takes
  `roberta_openai` to 0.088 here — but "the content wall was a selection limit" was a
  corpus-specific result stated as a general one. Results 1–2 called `hc3_roberta` the detector a
  meaning-preserving rewrite cannot move, and on real AI text that is what it is.
- Every figure in Results 1–9 remains reproducible and each still isolates the defect it measured.
  None of them was ever a claim about real AI documents; they now say so.
- **The honest free ceiling against real AI text is 0.86, flagged 1.00** — not 0.15, flagged 0.00.

The two frontiers this leaves are length (Result 10) and the content signal itself. Neither is a
phrasing problem, which is the only thing an inference-only loop can attack, and that — not a
better rewriter — is what bounds the free path.

---

## Result 12 — two fixes that looked obvious, both refuted by measuring them

Results 10 and 11 suggested two levers. Both were measured before being built, and neither survived.

### "The loop wastes iterations 2–N, so exit early when it stalls"

Result 11 hits `max_iters` on every sample, and the stall guard in `run.py` only fires for
rewriters flagged `deterministic` — a stochastic one always spends the full budget. That reads like
4× the CPU for nothing. Running the same text at budgets 1 through 4, same seed, only `--max-iters`
changed:

| text | words | before | max_iters=1 | 2 | 3 | 4 |
|---|---|---|---|---|---|---|
| A | 207 | 1.000 | 0.927 | 0.542 | 0.514 | **0.403** |
| B | 199 | 1.000 | 0.999 | 0.999 | 0.999 | 0.999 |

Text A more than halves after the first iteration and keeps improving to the budget. Text B never
moves at all. **A no-progress early exit would have cost A most of its improvement**, and nothing at
iteration 1 distinguishes A from B. The existing guard — deterministic rewriters only, where a
repeat is provably a no-op — is exactly as aggressive as it can safely be. No change made.

### "Clear each paragraph separately, then reassemble"

If `max`-over-windows is what pins a long document, clearing each block on its own and reassembling
should beat rewriting the whole thing. Measured:

| doc | words | before | whole-document loop | per-block then join |
|---|---|---|---|---|
| 0 | 406 | 1.000 | 0.999 | **0.999** |
| 1 | 291 | 1.000 | 0.999 | **0.999** |

No difference — because the individual paragraphs do not clear either. Text B above is a single
199-word paragraph that ends at 0.999 on its own.

### What this corrects in Result 10

Result 10 concluded "the next frontier is length". That overstates it. The per-text spread
(0.403 to 0.999 at essentially the same length) is larger than anything the length sweep attributed
to length. The sweep's real mechanism is `max` over a corpus of uneven difficulty: each added
paragraph is another chance to include a text the loop cannot clear, and `max` reports the worst
one. Length and worst-element predict the same table, and only measuring a single paragraph tells
them apart.

So the frontier is not document length. It is that **some AI text is unclearable by
meaning-preserving rewriting at all**, and `max` aggregation means one such passage is enough to
flag a whole document. That is a harder problem than windowing, and it is the same content wall
Result 11 names — not a separate one.

Both of these are recorded because they were plausible, cheap to build, and wrong. Measuring first
cost two probe runs; building first would have shipped a regression in the first case.

### And a third: "warn the user when the text won't clear"

If some texts are unclearable, the tool could say so up front instead of spending five iterations
finding out. That needs a cheap pre-signal that predicts the outcome. There isn't one. Ten real HC3
answers, scored before and run to `max_iters=3`:

| | hc3_roberta | roberta_openai | fast_detectgpt | perplexity_burstiness | tells/100w | post |
|---|---|---|---|---|---|---|
| range across the 10 | 0.997–0.999 | 0.971–1.000 | 0.502–0.859 | 0.459–0.769 | 0.0–1.0 | **0.371–0.999** |

The inputs are nearly indistinguishable — `hc3_roberta` spans 0.002 across every text — while the
outcomes spread across the whole range. Nothing measurable about the input separates the text that
reaches 0.371 from the one that stays at 0.999, so there is no honest warning to give.

**None of the ten cleared**, which is Result 11's figure reproduced at a third setting (n=8
`max_iters=5`, n=2 `max_iters=4`, n=10 `max_iters=3`): 0 out of 20 real AI paragraphs cleared the
0.30 threshold in any configuration measured.
