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

> **Read [Result 3](#result-3--superseding-update-the-content-wall-was-largely-a-selection-limit)
> first.** Results 1–2 were measured with the then-default `best_of=1`. Re-measuring with best-of-3
> selection cut mean max P(AI) roughly in half again (0.683 → **0.290**) and falsified this
> document's original claim that the content/genre detector cannot be moved (`hc3_roberta`
> 0.725 → **0.036–0.064**, replicated). Earlier sections are kept for the record with corrections
> marked inline.

## Setup

- **Detector ensemble (full tier, `max` aggregation):** `roberta_openai`
  (`openai-community/roberta-base-openai-detector`), `hc3_roberta`
  (`Hello-SimpleAI/chatgpt-detector-roberta`), `fast_detectgpt` (EleutherAI/gpt-neo-125m), and the
  lite `perplexity_burstiness` heuristic. `mage` (`yaful/MAGE`) is excluded — its `id2label` config
  is rejected by current `huggingface_hub` (a known, documented dead detector).
- **Threshold:** `0.30` (untell's default — aggressive; most formulaic text flags).
- **Metric:** `max` P(AI) across the live detectors (the proxy untell drives down), reported as the
  per-corpus mean (`mean_max`) and the fraction still at/above threshold (`flagged_rate`).
- **Corpus:** formulaic AI-style paragraphs (the genre detectors are trained to catch). No locked
  facts needed — this measures detector *movement*, not meaning preservation (which the loop's
  similarity gate and sentinel lock handle separately and are tested elsewhere).
- **Reproduce:** `untell-ceiling --rewriter surgical --tier full` (the deterministic, no-key path).

## Result 1 — three free rewriters, head to head (n=3, full tier)

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
