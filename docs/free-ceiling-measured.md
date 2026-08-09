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
> **The corpus is not the only thing scoped here — so is the rewriter, and this one turned out to
> matter just as much.** Every number in this document, Result 11 included, was measured with
> `--rewriter composite`: the CLI default, but the *middle* rung of the ladder the README documents
> (`surgical` → `structural` → `composite` → `neural` → `ensemble`/`max`). Running the rung above
> it on the same six texts ([Result 13](#result-13--the-wall-is-the-rewriter-not-the-free-tier))
> moves the headline from **0.805, flagged 1.00** to **0.502, flagged 0.50**, and takes
> `hc3_roberta` — called "the wall", "barely moves", "immovable by meaning-preserving rewriting"
> throughout Results 11 and 12 — from 0.998 to **0.407**.
>
> Those were single runs each. Replicated at `--repeats 3`
> ([Result 14](#result-14--result-13-replicated-with-repeats-and-the-variance-it-could-not-see)),
> the gap survives — 0.398 against a worst within-rewriter spread of 0.191 — and the figures settle
> at **composite 0.778 ± 0.020, flagged 0.94** against **neural 0.380 ± 0.079, flagged 0.28**, with
> `hc3_roberta` at **0.710** and **0.248**. So **72% of real AI paragraphs clear** with `neural`,
> and Result 11's "0 of 20 cleared in any configuration measured" is composite's result, not the
> free tier's. `neural` is also **4x as variable** as composite, so quote it with repeats or not at
> all.
>
> So the wall those results describe is a property of **composite**, not of the free tier. Read
> every "ceiling" claim below with that scope attached. The cost is real and is stated in Result
> 13: meaning similarity 0.986 → 0.941, and `neural` needs the `.[full]` extra.
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
- **A later change to the loop does not move these numbers.** The loop now re-scores the RESTORED
  text rather than reporting the masked one, because on fact-bearing prose those differ by up to
  0.1535 and can flip a verdict. Every corpus used here is essentially unaffected: `_SAMPLE` and
  `eval.datasets._BUILTIN` lock **0 spans** in every paragraph, so the two strings are identical;
  the HC3 slice behind Results 11 and 14 locks spans in 5 of 8 texts but shifts by **mean +0.0006,
  max +0.0015** — the fourth decimal. Stated so a reader reproducing these figures after that
  change knows the difference is not a regression.

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

Measured at scale rather than left as a pointer: 80 runs over 40 real HC3 paragraphs with
citations, URLs, quoted dates, currency, emails, phone numbers and ratios spliced in, two seeds
each — **0 sentinels lost, 0 duplicated, 0 facts altered.** The check is now in the suite over the
packaged corpora, and it is mutation-verified: making the rewriter drop a locked span, or duplicate
one, each fails it.

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

---

## Result 13 — the wall is the *rewriter*, not the free tier

Every result above, Results 11 and 12 included, was measured with `--rewriter composite`. Composite
is the CLI default and the right thing to characterise, but it is the **middle** rung of the ladder
the README documents (`surgical` → `structural` → `composite` → `neural` → `ensemble`/`max`), and
nobody had run the rungs above it against the real-text corpus. The result dict recorded
`rewriter_available: true` and never *which* — so "0.999 → 0.860, hc3_roberta barely moves, this is
a wall not variance" was written down with no record of the one variable it turns out to depend on.

Same six HC3 answers through both, same command, same settings. `pre_mean_max` is identical to four
decimals (0.9994), so this is a controlled comparison and not a corpus difference:

```bash
UNTELL_DISABLE_MAGE=1 untell-ceiling --dataset hc3 --n 6 --tier full --best-of 3 --max-iters 5 \
  --rewriter composite   # and again with --rewriter neural
```

| | `composite` | `neural` |
|---|---|---|
| mean max P(AI) | 0.9994 → **0.8052** | 0.9994 → **0.5017** |
| flagged rate | 1.00 → **1.00** | 1.00 → **0.50** |
| **`hc3_roberta`** | 0.998 → **0.7559** | 0.998 → **0.4072** |
| `roberta_openai` | → **0.1237** | → 0.3003 |
| `fast_detectgpt` | → 0.3168 | → **0.2007** |
| `perplexity_burstiness` | → 0.4188 | → **0.3265** |
| meaning similarity | **0.986** mean / **0.965** worst | 0.941 mean / 0.884 worst |

**`hc3_roberta` is not immovable.** Results 11 and 12 called it the wall — "barely moves",
"the loop is being asked to move the one signal a meaning-preserving rewrite may not change". On the
same texts a different *free* rewriter takes it from 0.998 to 0.407, and half the samples clear the
threshold where composite cleared none in any configuration previously measured.

Three things this does **not** say, stated because the earlier results were over-read in exactly
these ways:

1. **It is not free.** Meaning similarity drops from 0.986 to 0.941 mean and 0.965 to 0.884 worst —
   still clear of the 0.76 bar, but a real cost, and `neural` needs the `.[full]` extra (~850MB T5)
   and several times the wall-clock. The CLI now prints the trade when a run ends flagged rather
   than changing the default silently.
2. **It is not uniformly better.** `neural` *loses* on `roberta_openai` (0.300 against composite's
   0.124) and wins on the other three. It wins the `max`, which is what decides the verdict, but a
   per-detector reading shows a trade rather than a dominance.
3. **It does not rank the strong rewriters against each other.** An earlier n=3 run gave
   `neural` 0.322, `ensemble` 0.485 and `max` 0.748 — but `max` **is** `ensemble` (the same
   `EnsembleRewriter` object; there is no `MaxRewriter`), so that 0.263 spread is one method's
   run-to-run variance, and it is *wider* than the gap it appeared to establish. Ranking `neural`
   against `ensemble` needs `--repeats ≥ 3` at n ≥ 8, which has not been run.

The general lesson is the one this document keeps relearning, now applied to a second axis: a
ceiling is a property of the corpus **and of the rewriter**, and a number recorded without both is
a number that will be read as more general than it is. `untell-ceiling` now records `rewriter` in
its result and prints it in the banner, next to the corpus.

---

## Result 14 — Result 13 replicated with repeats, and the variance it could not see

Result 13 compared `composite` against `neural` on six HC3 answers in a **single run each**, and its
own point 3 records run-to-run variance of 0.263 on this corpus. A 0.303 gap measured against 0.263
of noise is a direction, not yet a finding — and this document has twice learned that lesson the
hard way (Result 6/7: two 3-repeat runs of the identical command gave 0.247 and 0.330). So the same
comparison, `--repeats 3` on both sides, 36 loop runs total:

| n=6, `--repeats 3`, full tier, best-of-3, max-iters 5 | `composite` | `neural` |
|---|---|---|
| mean max P(AI) | 0.9994 → **0.7779 ± 0.0204** | 0.9994 → **0.3795 ± 0.0794** |
| flagged rate | 1.00 → **0.944** | 1.00 → **0.278** |
| per-run means | 0.795, 0.749, 0.790 | 0.359, 0.485, 0.294 |
| **`hc3_roberta`** | 0.998 → **0.710** | 0.998 → **0.248** |
| `roberta_openai` | → 0.199 | → 0.220 |
| `fast_detectgpt` | → 0.300 | → 0.140 |
| `perplexity_burstiness` | → 0.429 | → 0.239 |
| meaning similarity | 0.978 mean / 0.921 worst | 0.932 mean / 0.831 worst |

**The gap survives.** 0.398 between the rewriters against a worst within-rewriter spread of 0.191.
Result 13's conclusion holds: `hc3_roberta` is not immovable, and the wall Results 11 and 12
describe belongs to `composite`.

Two things one run could not show:

1. **`neural` is four times as variable as `composite`** — spread 0.191 against 0.045, stdev 0.0794
   against 0.0204. The stronger rewriter is also the less predictable one, and a single `neural` run
   can land at 0.485, most of the way back to composite's band. That is exactly why Result 13's
   single-run numbers (composite 0.805, neural 0.502) differ from these; both are draws from those
   distributions. Quote `neural` with repeats or not at all.
2. **Most real AI text clears with `neural`** — flagged 0.278, so **72% of samples fall below the
   0.30 threshold**. Result 11 stated "0 of 20 real AI paragraphs cleared in any configuration
   measured", which was true of every configuration measured *at the time* and is composite's
   result, not the free tier's.

### What this does to Result 11

Result 11's headline — "the honest free ceiling against real AI text is 0.86, flagged 1.00" — is
**composite's** ceiling. The free tier's, measured the same way with the rung above it, is
**0.38, flagged 0.28**. The reasoning in Result 11 was sound and its control (`roberta_openai`
0.993 → 0.088) still holds; what was wrong was the scope, in exactly the way Result 10 warned about
one axis earlier and Result 13 caught on this one.

The cost is real and unchanged from Result 13: similarity 0.978 → 0.932 mean and 0.921 → 0.831
worst, still clear of the 0.76 bar, plus the `.[full]` extra and several times the wall-clock.

Reproduce:

```bash
UNTELL_DISABLE_MAGE=1 untell-ceiling --dataset hc3 --n 6 --tier full --best-of 3 --max-iters 5 \
  --repeats 3 --rewriter neural    # and again with --rewriter composite
```

---

## Result 15 — `ensemble` vs `neural`: the point estimate favours `ensemble`, the noise swallows it

`--rewriter ensemble` runs composite + mt_pivot + neural and keeps the per-input detector-lowest,
so on the score it selects on it is **>= any single member by construction**. The CLI help says so.
What the help does not say is how big the margin is, which is the number that decides whether it is
worth several times the wall-clock.

Same corpus and protocol as Results 13 and 14 — 6 HC3 AI answers, full tier, `--best-of 3`,
`--max-iters 5`, `--repeats 3`:

| rewriter   | post          | flagged | per-run                  | similarity (mean / worst) |
|------------|---------------|---------|--------------------------|---------------------------|
| `neural`   | 0.4364 ± 0.066 | 0.333   | 0.346 / 0.460 / 0.503    | 0.918 / 0.746             |
| `ensemble` | 0.3352 ± 0.084 | 0.278   | 0.228 / 0.344 / 0.434    | 0.935 / 0.840             |

The gap is **+0.1012 in ensemble's favour, and the worst within-method spread is 0.2052** — twice
the gap. Three runs of `ensemble` span 0.228 to 0.434; three of `neural` span 0.346 to 0.503. The
bands overlap heavily, so at this sample size the honest statement is:

> `ensemble` selects the best of its members per input, and measured that way it is never worse.
> Its *advantage over `neural` alone* is smaller than the run-to-run variation of either, so a
> single comparison run cannot establish it and neither can this one.

This is the same lesson as Result 14, applied to the rung above: `neural`'s variance was what made
Result 13's single run misleading, and it is what makes this comparison inconclusive rather than
favourable. The direction is what the construction guarantees; the *size* is not measured here.

Similarity is the one place the difference is clean: `ensemble` holds 0.840 worst-case against
`neural`'s 0.746, both above the 0.76 bar — meaning `neural` alone came within 0.014 of tripping
the meaning gate on its worst input, and the ensemble's per-input selection did not.

Reproduce:

```bash
UNTELL_DISABLE_MAGE=1 untell-ceiling --dataset hc3 --n 6 --tier full --best-of 3 --max-iters 5 \
  --repeats 3 --rewriter ensemble   # and again with --rewriter neural
```

---

## Result 16 — the meaning gates were not the throttle; one synonym entry was

Every previous result treats the loop's output as given. This one asks what stops it: of the
candidates the rewriter draws, which gate rejects them, and how often?

Protocol: 25 RAID + 25 HC3 AI texts, 3 structural draws each, every gate evaluated
**independently** against the original (the shipped loop short-circuits, so a serial reading
attributes every rejection to whichever check runs first).

| gate       | veto rate | veto rate |
|------------|-----------|-----------|
|            | **before** | **after** |
| similarity | 0%        | 0%        |
| numerals   | 0%        | 0%        |
| roles      | 2%        | 3%        |
| **hedges** | **20%**   | **0.7%**  |

The hedge gate was doing essentially all of the rejecting, and **every one of those 30 vetoes was
the same class** — `intention`. The cause was not the gate. Three entries had been added to the
synonym map (`propose`, `proposes`, `proposed`) as academic boilerplate, and those words are
intention hedges. A hedge class counts as dropped when the candidate contains no member of it, so
substituting an intention verb for anything outside the class vetoes *by construction*. The gate
was correct; the substitution was wrong.

The obvious fix — widen the class to admit the substitutes — was tried and reverted. `suggest` is
an **evidential** hedge in "the results suggest a link" and an **intention** verb in "we suggest a
method". Forcing it into one class breaks the other, and it broke two pre-existing tests that were
right to fail. There is no member list that makes an intention → non-intention swap safe.

### What this changes, and what it doesn't

With the gates no longer throttling, the next question is whether admitted candidates are actually
*good*. Over 40 texts × 4 draws, lite tier:

- **96%** of admitted candidates lower the detector score
- mean delta **−0.210**, median **−0.217**
- **0 of 40** texts had no helpful draw

So admission is not the constraint and neither is candidate quality. Depth is not the constraint
either — repeated passes are sharply diminishing:

| pass | score | flagged | similarity | step |
|------|-------|---------|------------|------|
| 0 | 0.3964 | 85% | 1.0000 | — |
| 1 | 0.1175 | 0% | 0.9910 | −0.2789 |
| 2 | 0.0904 | 0% | 0.9885 | −0.0271 |
| 3 | 0.0859 | 0% | 0.9872 | −0.0045 |
| 4 | 0.0825 | 0% | 0.9856 | −0.0034 |

Pass 1 is **88%** of the total gain; passes 3 and 4 together are under 2%. Raising `max_iters`
buys nothing, and the loop already exits early on pass, so the existing default of 5 costs nothing
either. Both are non-findings worth recording, because both looked like levers.

The gap this does *not* close is the tier gap: the same pipeline reaches 0% flagged at lite and
leaves 39 of 40 flagged at full. That is a per-detector fact, not a loop fact, and `max` is the
reported score — one stubborn detector pins the result regardless of the other four.

Reproduce: `scratchpad/veto.py`, `accept.py`, `compound.py` in the session scratchpad; each is a
standalone script against `eval.datasets.load_pairs`.

---

## Result 17 — no single detector is the wall, and plainening does not feed the curvature detector

Result 16 ended on the one gap it could not close: the same pipeline clears lite entirely and
leaves most texts flagged at full tier. `max` is the reported score, so the natural hypothesis was
that **one** stubborn detector pins the result while the other four move. Measured, 12 RAID AI
texts, full tier, `composite`:

| detector | before | after | delta | still flagged |
|----------|--------|-------|-------|---------------|
| `fast_detectgpt` | 0.792 | 0.249 | −0.544 | **33%** |
| `perplexity_burstiness` | 0.529 | 0.254 | −0.275 | 17% |
| `hc3_roberta` | 0.766 | 0.206 | −0.559 | 8% |
| `roberta_openai` | 0.588 | 0.068 | −0.520 | 8% |
| **MAX (reported)** | 0.904 | **0.340** | −0.564 | — |

The hypothesis is wrong. Every detector moves, and moves a lot — the two RoBERTa detectors end at
8% flagged. But **the reported max (0.340) is higher than the worst individual mean (0.254)**,
which means different texts are caught by different detectors. The max is an *envelope*, not a
single adversary, and there is no one thing to fix.

`fast_detectgpt` is nonetheless the weakest link: 33% still flagged, two to four times the others,
and the highest post-rewrite mean.

### The tension that isn't there

`fast_detectgpt` scores probability *curvature* — text sitting at high-probability positions reads
as generated. `_plain_register` swaps formal, rare words for plain common ones ("utilize" → "use"),
and common words are **higher** probability. So the move that kills `ai_vocab` tells looked like it
might be feeding the curvature detector, with nothing in the loop able to reveal it because only
`max` is reported.

Isolating the register pass (same texts, that pass only, full tier):

| detector | before | after | delta |
|----------|--------|-------|-------|
| `fast_detectgpt` | 0.792 | 0.598 | −0.195 |
| `roberta_openai` | 0.588 | 0.333 | −0.254 |
| `perplexity_burstiness` | 0.529 | 0.393 | −0.136 |
| `hc3_roberta` | 0.766 | 0.718 | −0.048 |

**Refuted.** Every detector goes down, `fast_detectgpt` among them. Plainening is not a trade
against curvature — presumably because the formal AI vocabulary it removes is itself
high-probability *in the generator's distribution*, which is what the curvature score reads.

Reproduce: `perdet.py` and `tension.py` in the session scratchpad.

---

## Result 18 — a diversity gate that provided no diversity, and the collision it was hiding

The plain-register pass scaled its per-word swap probability by `intensity * profile["register"]`.
The `profile` factor is deliberate — "utilize" → "use" is right for casual prose and wrong for a
paper, so `academic` holds the map back at 0.15. The `intensity` factor was there for best-of-N
diversity. It provided none.

12 RAID AI texts, 4 draws each, full tier, register pass isolated:

| | best-of-4 score | ai_vocab left | sim to source | **draw-to-draw sim** |
|---|---|---|---|---|
| gated (×0.5) | 0.8130 | 6 | 0.9941 | **0.9949** |
| ungated (×1.0) | 0.7613 | **0** | 0.9903 | **0.9948** |

Draw-to-draw similarity is identical to four decimals. `random.choice` already picks among 2–4
synonyms per word, so two draws differ even when both swap everything — the gate contributed
nothing to diversity and 6 surviving `ai_vocab` hits plus 0.05 of detector score to the cost. Draw
*level* diversity was never at stake: `CompositeRewriter._intensity_sweep` varies intensity ACROSS
draws, which still scales every structural transform.

End-to-end through the real pipeline, 14 RAID texts, best-of-4, full tier:

| | score | flagged | similarity |
|---|---|---|---|
| coupled to intensity (old) | 0.5324 | 71% | 0.9901 |
| profile only (new) | **0.4151** | **50%** | 0.9879 |

### What ungating exposed

Applying the map wholesale surfaced a second bug that the gate had been masking. The map is
many-to-one: six source words offer `key` (`pivotal`, `crucial`, `vital`, `paramount`,
`essential`, `salient`), six offer `boost`, five offer `so`. AI prose reaches for several of a
cluster in one passage, so independent choices collapse them onto the same word — three of six land
on `key` about 4% of the time, at least two about 26%. On the 60-text corpus:

| category | before | after (gate removed) | after (collision fix) |
|---|---|---|---|
| `ai_vocab` | 55 | **0** | **0** |
| `formulaic_transition` | 33 | **0** | **0** |
| `repeated_sentence_openers` | 146 | 52 | **19** |
| `repeated_phrasing` | 1148 | 985 | 984 |

`_swap` now prefers an option the text has not spent yet, falling back to the full list when all
are used — repeating a plain word beats leaving the AI one in place.

`repeated_phrasing` does **not** fully recover (984 against 960 before ungating). That residue is
real and is the honest cost: applying the map wholesale draws on a smaller, plainer vocabulary, and
plainer vocabularies repeat. It is 2.5% against `ai_vocab` −21, `formulaic_transition` −5 and
openers −25, and the detector score — the only arbiter that matters — moved decisively the right
way.

The openers column is a separate fix in the same commit: the participial flattener always emitted
"This <verb>", so five trailers became five identically-opening sentences. `score_tells` never
flagged it, because `_duplicate_sentence_starts` needs 40% of sentences plus a word floor. The
catalogue is a proxy for what detectors read, not a definition of it — "our checker is quiet" is
not evidence the output is good.

Reproduce: `gate.py`, `netgate.py`, `catmove.py` in the session scratchpad.

---

## Result 19 — the rewriter's own choices, measured against what humans actually write

Results 16–18 fixed things that were wrong on their own terms: a gate that vetoed too much, a
substitution that changed nothing, a gate that bought no diversity. This one asks a different
question — every hard-coded choice in the rewriter is a number or a word list somebody picked, and
the human halves of the paired corpora say what they should have been.

All figures below: 400 paired texts from HC3 and RAID, 3347 human sentences against 4094 AI.

### Merge connectors — uniform was a fingerprint

`_merge_sentences` chose from five clause connectors with `random.choice`, i.e. 20% each.

| connector | human | ai | **uniform (emitted)** |
|---|---|---|---|
| and | 65.9% | 79.5% | 20.0% |
| but | 21.6% | 6.7% | 20.0% |
| so | 7.9% | 3.1% | 20.0% |
| while | 3.9% | 10.6% | 20.0% |
| though | **0.7%** | 0.0% | **20.0%** |

"though" was emitted **29× more often than a human writes it**, "while" 5×. An unnatural
connective distribution is exactly what a perplexity detector reads, so the transform whose job is
humanising rhythm was signing its work. Now weighted to the human column; emitted over 4000 seeds:
66.7 / 21.1 / 8.0 / 3.4 / 0.8.

Worth noting the AI column: humans use "but" **3.2×** as often as AI does. Under-using contrast is
itself an AI trait, so the weights lean the right way on that axis too.

### Openers — half of them are written by nobody

`_vary_openers` fires at ~30% per sentence. Humans open a sentence with one of its eight phrases
**0.2%** of the time. Per phrase:

| | human | ai | |
|---|---|---|---|
| broadly | 0.000% | 0.000% | **dropped** |
| looking at this | 0.000% | 0.000% | **dropped** — also the top source of created repetition |
| as it turns out | 0.000% | 0.000% | **dropped** |
| realistically | 0.000% | 0.000% | **dropped** |
| in short | 0.090% | 0.073% | kept |
| in practice | 0.060% | 0.000% | kept |
| also | 0.568% | 0.000% | **added** |
| now | 0.329% | 0.073% | **added** |
| basically | 0.209% | 0.000% | **added** |

Four of the eight are written by nobody — not humans, not the generators. Inserting one is not
humanising, it is a fingerprint.

Selection needs **two** criteria, not one. Several human-leaning markers were declined because they
*assert* something about the sentence they precede, and the meaning gates check entailment and
semantic roles, not discourse relations — nothing downstream would catch the error. "so" is the
single most common human opener in the corpus (1.285%) and is declined on exactly that ground;
likewise "then" (sequence), "recently" (recency), "meanwhile" (simultaneity), "here" (deictic).

### The same marker points opposite ways in different registers

`_TRANSITIONS_RE` strips sentence-opening Moreover / Furthermore / Therefore as AI tells. Per
corpus:

| marker | HC3 human | HC3 ai | RAID human | RAID ai |
|---|---|---|---|---|
| moreover | (<5 occ) | | **0.888%** | 0.041% |
| furthermore | (<5 occ) | | **0.947%** | 0.332% |
| therefore | (<5 occ) | | **0.592%** | 0.000% |
| additionally | 0.000% | 1.544% | 0.178% | 0.913% |
| overall | 0.000% | 2.613% | 0.000% | 2.407% |

Real paper abstracts use "Moreover"; the generators largely do not. Stripping it from academic
prose makes the text read **less** human. Tied to the `academic` style profile rather than applied
globally, because this is corpus scope — the same word is an AI tell in forum prose. Not extended
to `professional`/`technical`, where the direction is plausible but unmeasured.

### Two passes that each deferred to the other

Fixing the above exposed a structural bug worth recording separately. `_plain_register` began
declining to substitute sentence-initial transitions, on the correct reasoning that
`_strip_transitions` deletes them outright. But the strip was rate-gated at 0.65, so a third of
them were neither stripped nor substituted, and `formulaic_transition` went 0 → 12.

And every sentence-level transform sat behind `if len(sents) >= 2`, correct only for the ones
needing a *pair*. Blocks are per-paragraph, so a lone "Overall, the paper provides ..." paragraph
was never looked at: **9 of the 10** surviving hits were that, while the strip rate was 100%.

Finally, `_vary_openers` skipped any sentence opening with The/This/It/That/There — precisely the
sentences that duplicate an opener, which is the entire reason `repeated_sentence_openers` exists.
A four-sentence passage all beginning "The ..." came back unvaried at rate 1.0.

### Where the categories ended up

60 RAID+HC3 AI texts, two structural passes, across Results 16–19:

| category | before | after |
|---|---|---|
| `ai_vocab` | 55 | **0** |
| `formulaic_transition` | 33 | **0** |
| `cliche` | 11 | **0** |
| `hedge_stacking` | 4 | **0** |
| `participial_trailer` | 2 | **0** |
| `repeated_sentence_openers` | 146 | **27** |
| `repeated_phrasing` | 1148 | **1014** |

`repeated_phrasing` is the one that stays large, and Result 18's split explains why: **93%** of it
is inherited from the source — domain terms the meaning gates would veto varying. The reachable
share was 7%, and most of that is now gone.

**This row moved the wrong way after Result 19 was first written, and the figure here is the
current one.** It reached 969 mid-session and then rose to 1014 when the fragment guards landed
(Result 22): refusing a split leaves a longer sentence, and a longer sentence repeats more
trigrams. `formulaic_transition` went the other way, 1 to 0, over the same changes. Both are
re-measured with `catmove.py` rather than carried forward, because a table of numbers nobody
re-runs is how this document would start lying.

Reproduce: `conn.py`, `openers.py`, `strip.py`, `rates.py`, `repsplit.py`, `catmove.py`.

---

## Result 20 — the free composite, replicated at n=40, and the `neural` question closed

Results 16–19 were each verified in isolation. This is the end-to-end number, on the largest real-
text sample this repo has run, replicated.

```bash
UNTELL_DISABLE_MAGE=1 untell-ceiling --dataset raid --n 40 --tier full \
  --rewriter composite --workers 3 --repeats 3
```

| | pre | post | flagged pre → post | mean sim | worst sim |
|---|---|---|---|---|---|
| `composite`, 3 repeats, 120 rewrites | 0.7737 | **0.3206 ± 0.0121** | 0.95 → **0.342** | 0.9825 | 0.9406 |

For comparison, the same corpus and settings before this session's work: **0.951 post, 39 of 40
still flagged**. The spread across the three runs is 0.0121, so this is not a lucky draw.

### `neural` vs `composite`, like for like

The pending question was whether the full tier's default rewriter should become `neural`. Both at
n=40, same corpus, same `best_of=1`:

| rewriter | post | flagged | mean sim | **worst sim** | cost |
|---|---|---|---|---|---|
| `composite` | **0.3234** | **35.0%** | **0.9831** | **0.9603** | CPU only |
| `neural` | 0.3691 | 37.5% | 0.9621 | 0.8716 | T5, hours |

`composite` is ahead on every column. But the honest reading of the score gap is narrower than it
looks: 0.0485 is **smaller than `neural`'s own run-to-run standard deviation**, measured elsewhere
in this document at ±0.079, and the `neural` figure here is a single run. The two cannot be
separated on score at this sample size.

What *is* clean is everything else. `composite` holds 0.9406 worst-case similarity across 120
rewrites against `neural`'s 0.8716 on 40; its own spread is 0.0121 against `neural`'s ±0.079, so it
is roughly six times more reproducible; and it needs no model download and no GPU.

**Decision: the default stays `composite`.** Not because it beats `neural` on evasion — that is not
established — but because it matches it there while being more faithful, far more stable, and free.
The earlier reading that "the wall is the default rewriter, not the tier" is now obsolete: the wall
was a set of fixable defects in the default rewriter, and Results 16–19 removed them.

### Burstiness — the right target depends on the register too

`_target_burstiness` drove sentence-length variance at a fixed CV of 0.45. Coefficient of variation
of sentence length, 200 pairs per corpus:

| corpus | human mean | human median | ai mean | our target |
|---|---|---|---|---|
| HC3 (forum Q&A) | 0.480 | 0.465 | 0.301 | 0.45 |
| RAID (paper abstracts) | **0.352** | 0.330 | 0.263 | 0.45 |

0.45 tracks conversational human prose closely and overshoots academic human prose by 0.10. Real
abstracts are more uniform in sentence length than forum answers, and driving them past that is a
deviation in its own right — the same failure as emitting "though" at 29× the human rate, one level
up. Note the AI column sits below human in **both** registers, so the transform's direction was
never wrong; only its destination was register-blind.

Only `academic` moves, to 0.35. The evidence is RAID abstracts, so it is not extended to
`professional`/`technical` (formal but unmeasured) and explicitly not to `journalistic`, whose
register is short punchy sentences against long ones — the opposite direction. The neutral default
stays 0.45, which every earlier result in this document was measured against.

### What is left, per detector

Where the remaining 34% comes from. 20 RAID AI texts, full tier, `composite`, single draw:

| detector | before | after | delta | still flagged |
|---|---|---|---|---|
| `fast_detectgpt` | 0.771 | 0.328 | −0.444 | **45%** |
| `perplexity_burstiness` | 0.514 | 0.282 | −0.232 | 35% |
| `hc3_roberta` | 0.764 | 0.269 | −0.496 | 20% |
| `roberta_openai` | 0.535 | 0.070 | −0.464 | **5%** |

`roberta_openai` is close to solved. `fast_detectgpt` is the wall — nine times the flagged rate,
and the highest post score — which is the same ranking Result 17 found before any of this session's
work, so it is a stable property of the pipeline rather than a sampling artefact.

It is worth being clear about what it is *not*: `fast_detectgpt` also takes the second-largest
absolute drop of the four (−0.444), so it is responding to the rewriter, not immune to it. It
simply starts higher and stays higher.

> **Superseded — see [Result 33](#result-33--the-wall-moved-and-it-is-now-our-own-zero-dependency-detector).**
> This ranking held for as long as it was measured, and then stopped. `fast_detectgpt` fell from
> 45% flagged to 19% without ever being targeted, and now ties with `perplexity_burstiness`. The
> "stable property of the pipeline" wording above was true of every measurement taken up to that
> point and was still wrong — stability across four runs of one pipeline says nothing about a
> pipeline that then changes.

**Do not compare the MAX row here against Result 17's.** That table was 12 texts and this one is
20 different ones; the per-detector *ranking* is what replicates, not the absolute level. The
like-for-like end-to-end figure is Result 20's, on a fixed n = 40 with repeats.

---

## Result 21 — reordering, and two structural moves measured then declined

Every transform in `rewriter/structural.py` was a **local** edit: a word swap, a split, a merge, a
deletion. None changed the order in which information arrives, which is what a curvature detector
reads over a long span — and `fast_detectgpt` was the wall at the time this was written
(Result 33 later found it no longer is).

### Fronting a trailing subordinate clause

`"X because Y."` → `"Because Y, X."` Safe without a parser: the subordinator travels with its
clause, so the relation it marks survives exactly. Isolated over 14 RAID texts, fronting everything
eligible:

| detector | before | after | delta |
|---|---|---|---|
| `fast_detectgpt` | 0.7858 | 0.7560 | −0.0298 |
| `perplexity_burstiness` | 0.5247 | 0.4983 | −0.0263 |
| `roberta_openai` | 0.5501 | 0.5280 | −0.0221 |

No detector worse, at **0.9993** similarity — it adds no words, it moves them.

The rate is a target rather than a maximum, for the same reason as contractions. Share of sentences
carrying a frontable subordinator that are actually fronted:

| corpus | human | ai |
|---|---|---|
| HC3 (forum) | 22.0% | **25.2%** — AI already fronts *more* |
| RAID (paper) | **17.6%** | 2.8% — humans front 6.3× as often |

### Declined: passive → active

Passive voice is register-inverted, like everything else measured this way — per 100 words, HC3
human 0.671 vs AI **1.194** (1.78×), but RAID human **1.113** vs AI 0.795 (the other way). The
forum gap is real.

It is still not worth building. Only the **agentive** passive is convertible without inventing an
agent, and that is **14.0%** of HC3 passives and **5.6%** of RAID's — the rest are "the results were
analysed" with no agent present. Converting the remainder would reach ~0.17 occurrences per 100
words, against a transform that must get subject/object order, number agreement and tense right
with no parser. Cost and risk both exceed the reachable signal.

### Declined: first-person injection

The largest single distributional gap found all session: HC3 human **1.200** first-person tokens per
100 words against AI **0.309** — humans use them **3.9×** as often.

Declined on meaning grounds, not measurement. "The system works" → "I think the system works" adds a
speaker stance the source does not have. It would very likely lower the score; it would also make
the tool assert something its input never said, which is the one thing the meaning gates exist to
prevent. Recorded here so the gap is known rather than rediscovered.

---

## Result 22 — the rewriter was emitting broken English, and every metric was blind to it

Reading roughly eight rewritten paragraphs by hand found six defects that 1900+ passing tests, the
tell catalogue, the detector ensemble and the meaning gates had all missed. A sentence fragment is
**perfect English to a tell catalogue** — `score_tells` counts AI tells and has no grammaticality
check, no quote-balance check, no contraction check.

| defect | example |
|---|---|
| exemplifier comma split | `"...options for melting ice on roads. Such as using chemicals..."` |
| appositive comma split | `"we show EdgeFlow. A new way to interactive segmentation..."` |
| stranded coordinator | `"...in combination with other techniques, but. Salt is often..."` |
| split inside a quotation | `He said "the result is robust.` / `It replicates", which...` |
| serial list split | `"The authors, Smith, Jones, and Patel."` / `"Reported that..."` |
| fronting stranded a coordinator | `"...it runs fast, the model works well and."` |

Counted end to end: **12 fragments in output against 0 in the sources**, over 60 texts. Now **3**,
and the full mechanical battery — 13 checks, scored on output *and* source so corpus artefacts are
not blamed on the rewriter — shows one residual (`stub_sentence` +1) against zero on everything
else.

Four of the six lived in `_split_one`, the copy of the split that the burstiness pass uses. It has
now diverged from `_split_long_sentences` four separate times: the comma clause-check, the minimum
side length, the stranded coordinator, and the list/quotation guards. They are still not unified —
they genuinely differ on a stranded coordinator, where one rehomes it and the other deletes it, so
merging is a measurement and not a refactor — but both are pinned to a shared invariant set.

### The cost, stated plainly

Refusing bad split points costs evasion. Like-for-like, `best_of=1`, n = 40, 3 repeats:

| | post | flagged | spread |
|---|---|---|---|
| before the fragment guards | 0.3206 | 34.2% | ±0.0121 |
| after | **0.3382** | **38.3%** | ±0.0072 |

+0.018 and +4.1pp, both larger than either run's spread. `repeated_phrasing` moved with it,
969 → 1014: a sentence that is not split stays long, and a long sentence repeats more trigrams.

**The trade was tried and refused first.** Making both splitters keep scanning past an unusable
comma instead of abandoning the split would recover the score — and measured, it recovered it by
finding a *different* bad split: stub sentences went 4 → 5 and a dangling coordinator reappeared,
because the next candidate is usually inside a list. Separating a list continuation from a clause
needs verb detection, which is not available on a parser-free tier. Reverted.

Broken English is a worse failure than four percentage points of flagged rate. A reader notices a
fragment instantly; the detector score is a number in a report. The regression is accepted, and it
is recorded here rather than left to be discovered in the next measurement.

### Three ways to recover the lost evasion, all tried

1. **Rescan past an unusable comma** instead of abandoning the split. Recovered score by finding a
   *different* bad split — stubs 4 → 5, a dangling coordinator reappeared. Reverted.
2. **Raise the burstiness move cap.** `_target_burstiness` is a hill-climb with `max_moves=12`, and
   output CV sits at 0.423 against a 0.45 target with only 23 of 60 texts reaching it. Measured at
   12 / 24 / 48 moves: mean CV **0.3044 in all three**, identical to four decimals. The cap is not
   the constraint — the climb runs out of moves that raise CV, because its split candidates are the
   ones now being refused. A second full burstiness pass over already-rewritten text gains
   **+0.0000**.
3. **Add a reordering transform** (Result 21's clause fronting). This one worked, and is shipped:
   every detector down, none worse, 0.9993 similarity.

So the burstiness ceiling is set by how many *valid* split points the text contains, not by how
hard the pass tries. That is a property of the corpus, and the honest conclusion is that the
fragment guards cost what they cost.

---

## Result 23 — the closing figure, on frozen code

Every number above was measured against whatever the code was at the time, and several runs were
invalidated mid-flight by the next fix. These two were taken on frozen final code, sequentially,
with nothing else competing:

| configuration | pre | post | flagged pre → post | mean sim | worst sim |
|---|---|---|---|---|---|
| `best_of=1`, ×3 repeats | 0.7737 | **0.3469 ± 0.0193** | 0.95 → **0.408** | 0.9816 | 0.9212 |
| `best_of=3` (**shipped**), **×3 repeats** | 0.7737 | **0.3271 ± 0.0132** | 0.95 → **0.375** | 0.9824 | 0.9394 |
| *(the same, single run — see below)* | 0.7737 | *0.3017* | 0.95 → *0.325* | 0.9823 | 0.9595 |

Against the same corpus and settings at the start of the day — **0.951 post, 39 of 40 flagged** —
that is the whole session's movement: **0.951 → 0.302** and **97.5% → 32.5%** in the configuration
users actually run.

### The `best_of=1` series, including where it went backwards

| stage | post | flagged | spread |
|---|---|---|---|
| before Results 16–19 | 0.951 | 97.5% | — |
| after Results 16–19 | 0.3206 | 34.2% | ±0.0121 |
| after the fragment guards (Result 22) | 0.3382 | 38.3% | ±0.0072 |
| after the list/quotation guards | **0.3469** | **40.8%** | ±0.0193 |

The last two rows are the grammar work being paid for: about **0.026 of score and 6.6 points of
flagged rate**, spent deliberately, after three separate attempts to recover it failed or made the
output worse. The final spread (±0.0193) is wide enough that the last two rows are not cleanly
separable from each other; the movement from 0.3206 is.

### The ≥3-repeats rule earning its keep, again

The shipped configuration was first measured as a **single run: 0.3017 post, 32.5% flagged**. That
was written down and explicitly *not* promoted to the headline, on this document's rule since
Results 13/14. Replicated, the same configuration on the same code is **0.3271 ± 0.0132 and 37.5%
flagged** — the single run sat about **two standard deviations low**. Quoting it would have
overstated the product by 0.025 of score and 5 points of flagged rate.

That is the third time in this file a single run of a randomised rewriter has produced a number the
replication did not support. The rule is cheap and it keeps paying.

### Which number to quote

The **`best_of=3 ×3`** row is the headline: it is the configuration users actually run, and it now
has its spread. The `best_of=1 ×3` row is kept because every earlier entry in this series used
`best_of=1`, and the session-long comparison has to be like for like.

---

## Result 24 — the lite tier's threshold is calibrated for the wrong job

The defect table in ROADMAP §2 has carried "lite tier flags 65% of human text at the shipped
threshold" as *found, not fixed*. Re-measured across both corpora, 120 human and 120 AI texts,
`tier=lite`, sweeping the threshold:

| threshold | false positive on HUMAN | true positive on AI | Youden J | balanced acc |
|---|---|---|---|---|
| 0.30 (**shipped**) | **60%** | 93% | 0.333 | 66.7% |
| 0.35 | 41% | 91% | 0.500 | 75.0% |
| **0.40** | 27% | 78% | **0.517** | **75.8%** |
| **0.45** | 17% | 68% | **0.517** | **75.8%** |
| 0.50 | 10% | 42% | 0.325 | 66.2% |
| 0.60 | 2% | 23% | 0.208 | 60.4% |

60%, not 65%, and identical in HC3 and RAID separately — so it is a property of the lite detector,
not of one corpus. **At the shipped threshold, a user checking their own writing on the free tier is
told it reads as AI three times in five.**

The optimum is a plateau at **0.40–0.45**, where balanced accuracy is 75.8% against the shipped
66.7%. A 5% false-positive rate would need 0.60, and AI recall there collapses to 23%.

### Fixed — by separating the two jobs the constant was doing

`score_text` now reports **`verdict_threshold`** alongside `threshold` and computes `flagged` from
it. The raise applies only when the stdlib heuristic is the *whole* verdict; with any model-backed
detector in the set the max is driven by a well-calibrated member. Measured on the same corpus
after the change: **false positives on human text 60% → 15%**, AI recall 93% → 70%, balanced
accuracy 66.5% → **77.5%**.

The loop is untouched. `flagged` is a report field; `_passed` reads `max < threshold - margin`, and
`threshold` still holds the low value the loop needs.

And the swept optimum for the **gpt2** path is **0.30 exactly** (J 0.970, FP 3%, TP 100%) — so the
shipped default was never wrong for the tier, only for the sub-path. Raising it globally would have
broken the well-calibrated path to fix the other one.

### Why it was not a one-line fix

`threshold` does two different jobs and they want opposite values:

- **The verdict.** "Is this text flagged?" — wants ~0.45, or it slanders human writing.
- **The loop's stopping condition.** "Rewrite until the score is below this" — wants a LOW value,
  because stopping early is under-rewriting. Raising it to 0.45 would make the loop quit sooner and
  weaken every humanisation run on the lite tier.

They were the same number, and the full tier — whose score distribution is different again —
shared it. The fix separates the reporting threshold from the loop target and calibrates the
reporting one per *scoring path* rather than per tier, which is the level the measurement actually
points at.

### Which "lite" this is

Measured with `UNTELL_LITE_NO_TORCH=1`, i.e. the **stdlib** path. That matters more than the
threshold does: the README records the same tier flagging **6% of human text when `torch` is
present** (GPT-2 perplexity, AUROC 0.997) against **69% on the stdlib path** (AUROC 0.754) — an
11.5× difference in false positives under one tier name. So the table above describes the
zero-dependency path specifically, and the threshold question is a stdlib-path question.

The README's 65% and the 60% here are the same finding on different samples (100 HC3 pairs there,
60 HC3 + 60 RAID pooled here); the ROADMAP row said 65% and now says 60% with this pooled
measurement behind it. The sweep points differ for the same reason — the README's 0.55/0.60 rows
are HC3-only.

Reproduce: sweep `score_text(t, tier="lite")["max"]` over `load_pairs("hc3", 60)` and
`load_pairs("raid", 60)` with `UNTELL_LITE_NO_TORCH=1` set.

---

## Result 25 — what the field actually has that we do not, and what that is worth

The census's own fields are prose, not booleans — `detector_in_loop` reads
`"no — there is no AI-text detector anywhere in the codebase"` — so a naive truthiness read gives
435/435 and a keyword heuristic gives 78 where the document, written by reading them, says 49.
Neither is usable. What follows is a technique sweep over the mechanism prose, checked against what
this repository implements.

| technique | mentions across 435 repos | here |
|---|---|---|
| watermark removal | 70 | `scripts/scrub.py` |
| synonym / token substitution | 30 | `attacks/word_importance.py` |
| **per-token logit steering** | **20** | **absent — architectural** |
| homoglyph / zero-width | 19 | `scripts/scrub.py` (we *remove* these) |
| style transfer / persona | 7 | `rewriter/prompts.py` |
| surrogate distillation | 6 | `training/surrogate.py` (GPU) |
| sentence reordering | 6 | `rewriter/structural.py` |
| **typo / noise injection** | **6** | **absent — declined** |
| **readability targeting** | **6** | **absent — now measured, see below** |
| RL / GRPO / DPO | 4 | `training/` (GPU) |
| back-translation | 3 | `attacks/back_translation.py` |
| **genetic / evolutionary search** | **2** | **absent — rare** |

Three of the four gaps are closed by a decision rather than by work. **Logit steering** needs
token-level access the black-box design does not have; the roadmap already names it as the reason
we lose on raw evasion. **Typo injection** is declined: it lowers the detector score by damaging
the text for the reader, which is the opposite of what this tool is for. **Genetic search** is two
mentions in 435.

**Readability targeting was the real one**, and measuring it found a defect rather than a missing
feature — see Result 26.

### Star count measures distribution, not capability

The eight highest-starred repos in the census are a 298k-star Chinese rewrite prompt,
`gpt_academic`, three more prompt files, an archive of leaked GPT system prompts, HuggingFace's
inference server, and a red-teaming scanner. **Not one is a competing humanizer.** 60% of the field
either instructs a humanizer or resells one. Engineering cannot buy adoption against that, which is
why the argument this repository makes is correctness — the axis where the field is empty.

---

## Result 26 — the rewriter was making text *harder* to read, and fixing it improved evasion

Readability was the one technique class in Result 25's sweep that was both absent and achievable.
Measuring it found a defect rather than a missing feature.

AI text is consistently harder to read than human text answering the same prompt, in both corpora
(150 pairs each):

| | Flesch reading ease | FK grade level |
|---|---|---|
| HC3 human | 61.81 | 9.69 |
| HC3 ai | 54.14 | **11.49** |
| RAID human | 19.85 | 16.53 |
| RAID ai | 16.54 | **17.13** |

The rewriter was moving it **the wrong way**. Over 40 HC3 pairs, FK grade: human 10.53, AI 11.84,
**ours 13.56** — harder to read than the AI it started from, and further from human than the input.
RAID the same: 16.55 / 17.39 / **18.23**.

### Which half was wrong

| | words/sentence | syllables/word |
|---|---|---|
| human | 21.62 | 1.499 |
| ai | 23.08 | 1.562 |
| ours | **27.95** | 1.546 |

The syllable half was already right — the plain-register pass moves it toward human. **Length was
the entire regression**: sentences 21% longer than the AI input and 29% longer than a human, and it
had worsened when Result 22's fragment guards began refusing splits while merges carried on.

### The fix, and the trade that was not a trade

A merge is declined when it would leave a sentence past `1.5 ×` the **input's** mean — relative, not
a constant, because a paper's sentences are legitimately longer than a forum answer's and a fixed
cap would flatten register. Plus an absolute floor of 25 words, just above the measured human mean:
merging two *average* sentences always yields 2× the mean, so a purely relative cap refuses it by
construction, which is right for long prose and stops the transform dead on short prose. The
burstiness pass has the same budget — it runs later and was unconstrained, so a pair the main merge
had just declined could be fused there anyway.

Readability lands in the human band:

| | FK grade | words/sentence |
|---|---|---|
| HC3 ours, before | 13.56 | 27.95 |
| HC3 ours, after | **11.65** | **22.9** |
| RAID ours, after | **15.91** | 22.2 |

Burstiness CV fell from 0.423 to 0.294, so this looked like trading one distribution match for
another. It is not. n = 40 RAID, 3 repeats, shipped configuration:

| | post | flagged | spread | mean sim |
|---|---|---|---|---|
| before | 0.3271 | 37.5% | ±0.0132 | 0.9824 |
| **after** | **0.3003** | **35.8%** | **±0.0073** | 0.9808 |

Better on score by more than either run's spread, better on flagged rate, and **half the
run-to-run variance**. Sentence-length inflation was costing more than the CV was buying, which is
not what the burstiness literature would predict and is the reason to measure rather than reason.

---

## Result 27 — a punctuation sweep, and a stylometric one that came back negative

Two dimensions nobody had measured here. One produced a shipped transform; the other produced a
reason not to build anything, which took the same effort and is worth the same.

### Punctuation: humans bracket, AI does not

Share of words that are each mark, 120 pairs per corpus:

| mark | HC3 human | HC3 ai | RAID human | RAID ai |
|---|---|---|---|---|
| **parenthesis** | **0.679** | 0.177 | **0.924** | 0.421 |
| question mark | 0.246 | 0.016 | — | — |
| quote mark | 1.046 | 0.437 | — | — |
| exclamation | 0.074 | 0.025 | — | — |
| comma | 4.953 | 5.018 | 4.442 | 5.134 |

Only the bracket gap is **safe** to close. A question mark at human frequency would invent
rhetoric the source never had, an exclamation a tone, and a quotation mark would fabricate a
quotation — each is a meaning change no gate here would catch, because the gates check entailment
and semantic roles, not speech acts.

Parenthesising an aside that is *already comma-bounded* is punctuation and nothing else: `the iris,
which is the coloured part of your eye, controls…` → `the iris (which is the coloured part of your
eye) controls…`. No word added, removed or reordered. 7.1% of AI sentences carry one. Rate-targeted
like the other distribution fixes; measured after, HC3 0.195 → **0.308** and RAID 0.348 → **0.554**,
about 40% of the gap in both.

Restrictive clauses are excluded and the distinction matters: *the method that is fast works* says
**which** method, so bracketing it changes the claim — and nothing downstream would notice.

### Lexical diversity: a gap that is not a lever

| | human | ai | ours |
|---|---|---|---|
| type-token ratio (HC3) | 0.6508 | 0.5066 | 0.5169 |
| hapax rate (HC3) | 0.4862 | 0.3226 | 0.3351 |

A large gap, and the rewriter barely moves it — which looks like an obvious next target. It is not.
Correlating type-token ratio against detector max over 100 real AI texts:

    corr(TTR, detector max)  = +0.229     more diverse vocabulary -> HIGHER P(AI)
    corr(length, TTR)        = -0.558     TTR falls with length by construction

The sign is the **opposite** of the intuition, and the second row says why the first is not to be
trusted either: TTR is mechanically a function of length, so a correlation with anything
length-sensitive is confounded before it is interpreted. Building a diversity-raising transform on
that would be optimising an artefact.

Mean word length and long-word rate both already move toward human, so the lexical axis needs
nothing. Recorded so the gap is known to have been examined rather than missed.

---

## Result 28 — a per-transform ablation, and why half of it cannot be trusted

Every transform run in isolation against each detector, 14 RAID AI texts, full tier. Delta from
the unmodified source, so more negative is better. The right-hand column is how often the stage
changes anything at all, over 120 real texts — without it, half this table is noise.

| stage | fast_detectgpt | ppl_burst | hc3_roberta | roberta_openai | fires |
|---|---|---|---|---|---|
| **plain register** | **−0.2198** | **−0.1444** | −0.0203 | **−0.3475** | most texts |
| merge | −0.0633 | −0.0185 | −0.0017 | −0.0743 | most |
| strip transitions | −0.0506 | −0.0188 | **−0.0744** | −0.0701 | most |
| **parenthesise asides** | −0.0416 | −0.0188 | −0.0240 | −0.0795 | 7% of sentences |
| burstiness | −0.0256 | −0.0183 | −0.0064 | −0.0074 | most |
| split long | −0.0245 | −0.0215 | −0.0116 | −0.0074 | most |
| clause fronting | −0.0177 | −0.0211 | −0.0196 | −0.0224 | 20% of eligible |
| participial | −0.0088 | −0.0008 | −0.0061 | **+0.0212** | **4 / 120** |
| cliché flattening | −0.0005 | −0.0004 | −0.0006 | 0.0000 | 14 / 120 |
| filler openers | 0.0000 | 0.0000 | 0.0000 | 0.0000 | **1 / 120** |

**The plain-register pass is worth three to five times any other transform**, on every detector.
That is the single most useful number here: the cheapest, oldest, least glamorous stage in the
pipeline — swapping formal vocabulary for plain words — does most of the work.

### The bottom three rows are not results

`filler openers` reads as dead code. It is not: its pattern (`it is worth noting that…`) fires
correctly on its own example and appears in **1 of 120** real texts. A stage that cannot fire and a
stage whose trigger is rare produce the same zero, and only the firing rate tells them apart.

Likewise `participial` appears to make `roberta_openai` *worse* by +0.0212. It changes 4 texts in
120, so across 14 texts it fired at most once or twice: that number is one text, not an effect.
Reporting it as a regression would be the same error as quoting a single run of a randomised
rewriter, which this document has had to correct three times.

**An ablation without a firing rate is a list of numbers with no denominators.** Measured this way,
seven of the eleven rows support a conclusion and four do not.

---

## Result 29 — the nominalisation substitutions, reported in both directions

Result 25 found AI text carrying 36% more nominalisations than human text on the same prompt, and
the rewriter moving that by zero. Four register substitutions were added (`utilization`,
`implementation`, `improvement`, `combination`), deliberately excluding the words that carry meaning
in a paper — a *contribution* is the novel claim, *robustness* is a measured property.

The distribution moved: HC3 2.584 → **2.487** per 100 words against a human 1.896, RAID → **7.346**.
That closes 13% and 34% of the gap, consistent with only 18.5% of the excess being register at all.

The detector result is **mixed, and both halves are reported**:

| | post | flagged | spread | mean sim |
|---|---|---|---|---|
| before | 0.3003 | 35.8% | ±0.0073 | 0.9808 |
| after | 0.3118 | **31.7%** | ±0.0162 | 0.9808 |

The flagged rate — the number a user actually sees — improved by 4.1 points. The mean score went
*up* by 0.0115, and the spread more than doubled to ±0.0162, which makes that difference **smaller
than one standard deviation**: it is noise, not a regression, and it is also not a win.

Kept, on the flagged rate and the distribution match, with the score movement recorded rather than
omitted. The headline row in the ROADMAP now carries these numbers, because quoting 0.300 would
mean quoting a figure the current code does not produce — which is the defect `untell-audit` was
built to catch, and it would be a poor look to commit it in the same session.

---

## Result 30 — paragraph structure is a real difference that nothing measures

AI text is broken into paragraphs where humans write flowing prose. Over 80 pairs per corpus:

| | paragraphs / text | newlines / text |
|---|---|---|
| HC3 human | 1.00 | **0.00** |
| HC3 ai | 1.00 | **2.70** |
| RAID human | 1.00 | 17.25 *(hard-wrapped)* |
| RAID ai | **5.25** | 9.31 |

A clean signal in HC3 — the AI answer carries line breaks the human answer never does — and the
rewriter changes it by nothing (3.14 paragraphs in, 3.14 out).

It is still not a lever. Flattening every newline in the 25 HC3 texts that have them:

    detector max   0.5669 -> 0.5669
    tells/100w     6.0052 -> 6.0052

Identical to four decimal places on both. Neither the detector ensemble nor the tell catalogue
sees whitespace, so a flattener would destroy document structure — the pipeline deliberately
processes per block to preserve it — in exchange for nothing measurable.

Recorded because it looks like an obvious win and is not, and because the *reason* is worth
knowing: this is a tell a human reader would notice that no automated detector here does.

### Two things that came back clean in the same sweep

`formulaic_transition` now survives in **zero** of 80 rewritten texts, down from 33 at the start of
this work. And the distinct-sentence-opener ratio — how varied the first words of sentences are —
reads human 0.839, AI 0.688, **ours 0.790**: most of the gap already closed by the opener and
merge work, with no further transform needed.

---

## Result 31 — ten missing inflections, and the best figure of the session

The Result 28 ablation showed `_plain_register` worth three to five times any other transform. That
made its coverage worth auditing, and the map turned out to be keyed on exact tokens with ten
inflected forms of existing keys missing:

| missing form | occurrences in 300 real AI texts | stem already in the map |
|---|---|---|
| **leverages** | **107** (15.2× the human rate) | `leverage` |
| demonstrating | 28 | `demonstrate` |
| achieving | 27 | `achieve` |
| required | 19 | `require` |
| requiring | 18 | `require` |
| evaluated | 17 | `evaluate` |
| introducing | 15 | `introduce` |
| utilizes | 14 | `utilize` |
| leveraging | 12 | `leverage` |
| outperforming | 11 | `outperform` |

Both consumers look up `_WORD` matches verbatim, so a stem does nothing for its inflections. A
half-connected entry looks complete in the table.

Shipped configuration, n = 40 RAID, 3 repeats:

| | post | flagged | spread | mean sim |
|---|---|---|---|---|
| before | 0.3118 | 31.7% | ±0.0162 | 0.9808 |
| **after** | **0.2889** | **24.2%** | **±0.0081** | 0.9808 |

−0.023 on score, **−7.5 points on flagged rate**, the spread halved, similarity unchanged. Ten
dictionary entries, and the largest single improvement measured in this session — because they were
missing from the one transform that does most of the work.

### The invariant found a bug the additions did not introduce

Every substitute must carry its key's inflection, or the swap yields "the system use robust
methods". Enforcing that surfaced `empowering → helpful`, which turns *the tool is empowering
users* into *the tool is helpful users*.

Scoping the rule took two attempts and the failure is worth recording. A blanket "-ing keys need
-ing substitutes" check reported **seven false positives**: `compelling`, `unwavering`,
`groundbreaking` and `overarching` are adjectives, and `compelling → powerful` is correct. It now
applies only to keys that are an inflection of *another* key — verbs by construction — with a
companion test asserting that scoping is not vacuous.

### Session trajectory, same corpus and settings throughout

    start of this work   0.951   97.5% flagged
    Results 16-19        0.321   34.2%
    Result 22 (grammar)  0.347   40.8%   <- paid deliberately for correct English
    Result 26 (length)   0.300   35.8%
    Result 29 (nominal)  0.312   31.7%
    Result 31 (this)     0.289   24.2%

---

## Result 32 — twelve more over-used words, and the grammar bug they exposed

The same sweep that produced Result 31's inflection fix also listed words AI over-uses with **no**
map entry at all. Twelve were added; several were deliberately not:

| excluded | why |
|---|---|
| `united` (99×) | it is "United States" — a proper noun, not register |
| `treatment`, `efficiency` | subject matter in these corpora |
| `contributions` | in a paper it names the novel claim |
| `helps`, `follows` | ordinary words with no formal register to remove |

Shipped configuration, n = 40, 3 repeats:

| | post | flagged | spread | mean sim |
|---|---|---|---|---|
| before | 0.2889 | 24.2% | ±0.0081 | 0.9808 |
| **after** | **0.2850** | **21.7%** | **±0.0051** | 0.9799 |

The score movement is *inside* the spread and is not claimed as a result. The flagged rate is
−2.5 points and the variance tightened again, which is.

### The bug the additions exposed

`applying → putting to work` produced **"putting to work it accurately"**. A separable phrasal verb
takes its object inside: *putting it to work*.

The particle is not the fault — `spell out the details` is correct English — it is a particle
followed by a **pronoun**. 35 keys in the map carry a particle-tailed substitute, and
`harnessing → putting to work` had the same latent bug before any of this session's work.

The swap now declines a particle substitute when a pronoun object follows, taking a single-word
alternative instead. Reordering the object was rejected: it requires knowing where the object ends,
which needs a parser this tier does not have. A test asserts `spell out the details` still happens,
because a rule banning every particle substitute would delete a third of the map's alternatives to
fix a case that only arises before a pronoun.

---

## Result 33 — the wall moved, and it is now our own zero-dependency detector

Result 17 measured each detector separately and found one obstacle: `fast_detectgpt` still flagged
**45%** of outputs where `roberta_openai` flagged almost none. Everything since — the corpus-matched
rates, the vocabulary work, the grammar repairs — was aimed at general naturalness, not at that
detector. Re-running the same breakdown asks whether any of it moved the thing that was actually
holding the score up.

Shipped configuration, `--tier full --rewriter composite`, n = 16, verdict threshold 0.30:

| detector | before | after | delta | still flagged |
|---|---|---|---|---|
| `perplexity_burstiness` | 0.521 | 0.263 | −0.258 | **19%** |
| `fast_detectgpt` | 0.783 | 0.260 | −0.523 | **19%** |
| `hc3_roberta` | 0.769 | 0.122 | −0.646 | 6% |
| `roberta_openai` | 0.544 | 0.042 | −0.502 | 0% |
| MAX (reported) | 0.925 | 0.319 | −0.606 | — |

`fast_detectgpt` went from 45% to 19% without being targeted once. The single wall is gone; what
is left is two detectors tied at the top, and 19% of 16 texts is **three documents** — small enough
that the tie should not be read as a ranking.

### The part worth noticing

`perplexity_burstiness` is *ours*: the pure-Python lite detector that ships with no model download,
no `torch`, no network. It is now as hard to beat as Fast-DetectGPT, which needs a GPT-Neo forward
pass. That is not because it got better — it is the same calibrated scorer from the earlier fix —
but because the neural detectors were reachable by the work that has been done and it was not.

Two readings, and they have opposite consequences:

1. **The lite detector is a good proxy for what remains.** If so, the cheap loop can keep making
   progress with no heavy stack, which is the whole free-tier premise.
2. **It is measuring something the rewriter structurally cannot change** — sentence-length variance
   and token-level surprise are properties of the generator's phrasing, and the rewriter edits
   words and clause joins, not the underlying rhythm.

The before column argues for the second: `perplexity_burstiness` started at 0.521, the *lowest* of
the four, and fell the least in absolute terms (−0.258 against −0.502 to −0.646). It was never the
detector with the most to give, and it still gave the least. A detector that starts near the
threshold and moves slowly will end up looking like the wall regardless of how good the rewriter is.

So the honest statement is not "burstiness is the next target." It is that **the ensemble max is no
longer set by one beatable detector**, and the remaining 0.319 is spread across two mechanisms with
different causes. Anything claiming to move it should report the per-detector table, not the max —
the max hid this for the whole of Result 17.

n = 16 on one corpus. The flagged rates are three-document resolution and the deltas are the
reliable part of this table.

---

## Result 34 — matching the human sentence-length distribution makes the score worse

Result 33 left `perplexity_burstiness` tied for the wall. It reads sentence-length variance, the
rewriter has a budget on *mean* length and nothing on spread, and both of its structural moves —
split and merge — pull toward the mean by construction. That is a mechanism, so it was worth
measuring. RAID, n = 40, `composite`:

| | mean | cv | 10th pct | 90th pct |
|---|---|---|---|---|
| AI original | 23.78 | 0.2625 | 15 | 32 |
| our output | 21.13 | 0.3818 | 10 | 30 |
| **HUMAN** | **23.49** | **0.3513** | **12** | **35** |

**The hypothesis was wrong.** Variance is already human — `cv` 0.382 against 0.351, if anything an
overshoot. The AI original sits at 0.2625 and the rewriter fixes that outright.

What the table does show is a different mismatch: our mean is 2.4 words *below* human, the short
tail runs below the human one (10 against 12), and the long tail is missing entirely (30 against
35). Splitting overshoots downward.

### Two levers, swept

`_MIN_SPLIT_SIDE` is a grammar floor — below it a half is a stranded discourse marker — so a
separate distribution floor was swept rather than moving it:

| floor | mean | cv | p10 | p90 | post | flagged |
|---|---|---|---|---|---|---|
| 4 (shipped) | 21.61 | 0.3454 | 11 | 31 | 0.4934 | 0.675 |
| 8 | 22.61 | 0.3013 | 13 | 32 | 0.5002 | 0.675 |
| 12 | 23.45 | 0.2772 | 15 | 32 | 0.4720 | 0.700 |

Raising the floor buys mean and *sells* variance — 12 lands the mean on the human value and drags
`cv` from 0.345 down to 0.277, away from it. No setting matches both moments. And no floor lifts
the long tail: splitting cannot create a long sentence. Merging can, so `_MEAN_LENGTH_BUDGET`:

| budget | mean | cv | p10 | p90 | post | flagged |
|---|---|---|---|---|---|---|
| **1.10 (shipped)** | 20.99 | 0.3553 | 10 | 30 | **0.4802** | **0.600** |
| 1.35 | 25.16 | 0.4458 | 12 | 40 | 0.5724 | 0.725 |
| 1.60 | 27.70 | 0.4630 | 12 | 47 | 0.5158 | 0.750 |

At 1.35 the output distribution is **closer to human on every moment measured** — mean 25.16 near
23.49, p10 exactly the human 12, a long tail that finally exists. The score gets **worse**:
+0.092 and +12.5 points flagged.

### Why this is trustworthy, and it usually would not be

The two sweeps re-ran one identical configuration by accident — shipped settings, same corpus, same
n. It came out **0.4934 / 0.675** in the first and **0.4802 / 0.600** in the second. That is a free
noise estimate on this harness: about ±0.013 on the score and ±0.075 on the flagged rate, from a
single unrepeated run.

Which retroactively decides the first table. Its whole range, 0.472 to 0.500, fits inside that
noise band — the split-floor sweep measured nothing, and reading a winner out of it would have been
reading noise. The budget result is +0.092, seven times the noise, and survives.

### What it means

The working method for most of this document has been: measure a rate against the human half of a
paired corpus and move ours toward it. Here that method points the **wrong way**. A rewrite can be
more human on the statistic a detector is named after and score worse, because the detector is not
actually reading that statistic in isolation — merging two sentences with a connector produces a
long sentence with a *predictable* join, and predictability is what the perplexity term measures.
The length histogram improved and the thing generating it got more machine-like.

Nothing shipped. `_MEAN_LENGTH_BUDGET` stays at 1.10 and `_MIN_SPLIT_SIDE` at 4. The distribution
gap is real and documented; the obvious ways to close it are measured and rejected.

Single run per cell, one corpus, one rewriter. The noise estimate above is the reason the budget
row is stated as a result and the floor rows are not.

---

## Result 35 — both model-backed meaning gates stopped reading part-way through the document

The gates are what this project claims over the rest of the field, so "does the entailment gate
catch X" deserved a systematic answer rather than the accident that produced Result 32's epistemic
finding. Nine classes of minimal meaning change, each scored against the full stack.

| class | caught by |
|---|---|
| negation | similarity, entailment |
| quantifier (`all` → `some`) | entailment |
| number | entailment, numerals |
| temporal (`before` → `after`) | entailment, roles |
| causal direction | roles |
| role swap | roles |
| evaluation flip (`improved` → `worsened`) | entailment |
| scope (`only X` → `X`) | similarity |
| **epistemic strength** (`demonstrates` → `proves`) | **nothing** |

Eight of nine, which reads well. Then the same table at realistic document length, and it collapses.

### The finding

Both model-backed gates truncate their input, and neither said so. The same edit, in the same
document, with only its **position** changed:

| | 7 w | 75 w | 143 w | 279 w |
|---|---|---|---|---|
| entailment, edit at the start | 0.9976 | 0.9769 | 0.9833 | 0.9833 |
| entailment, edit at the end | 0.9971 | 0.9748 | **0.0179** | **0.0179** |

0.0179 is the contradiction score for two *identical* strings. Past the tokeniser's cut the model
was comparing the same truncated prefix with itself.

Similarity was worse. Replacing a whole sentence with unrelated text — "The intervention halved
mortality among the treated cohort." for "Cats are pleasant animals and many people enjoy their
company." — at 280 words and beyond scored **1.0000**. Not "similar enough": the model reporting
the two documents as the same string.

Neither is a badly-set threshold. The changed text was **never fed to the model**, so no value of
the 0.76 bar or the 0.5 contradiction bar could have caught either. A rewriter could invert any
claim after roughly the first 130 words and nothing in this project would have noticed.

The detectors had this exact bug and it was fixed for them with windowed scoring. The meaning
gates never got the fix — and they are the more important half, because a missed detection costs a
point of score while a missed inversion ships a false statement.

### The fix, and the version of it that was wrong

Both gates now cut the pair into aligned chunks and take the worst: `max` contradiction, `min`
similarity. Averaging was never an option — meaning destroyed in one paragraph is destroyed, and
averaging against four untouched paragraphs is precisely what hid this.

**How the chunks are aligned decides whether the fix works.** Cutting each side into k equal pieces
drifts: the rewriter merges and splits sentences, so by the third chunk the two sides are a
sentence apart and the gate compares text that never corresponded —

```
SRC chunk: "Our results demonstrate that the attention mechanism improves ..."
OUT chunk: "We also perform a series of ablation studies ... Our results show that ..."
```

That produced 3 false vetoes in 30 real rewrites. Cut points now come from `difflib` matching
blocks, which drops it to 1 — and that last one turned out to be a **true** catch: `applied to
various tasks` → `applied to all sorts of tasks`, 0.29 whole-text against 0.61 aligned. An
overclaim I had personally read in the Result 32 scan and waved through as a register shift.

`entailment_score` is deliberately **not** chunked. Chunking it took vetoes from 0 to 2 and
printing the chunks showed misalignment rather than damage. Contradiction survives drift because it
is a `max` and unrelated text reads as neutral; entailment is a `min` over eight directional scores
and every imperfect pair drags it down.

### Cost and false-rejection rate

| | before | after |
|---|---|---|
| entailment, 298-word input | 0.17 s | 0.57 s |
| similarity, 30 real rewrites rejected | 0/30 | **0/30** (min 0.9005 vs the 0.76 bar) |
| entailment, 30 real rewrites vetoed | 1/30 | 2/30 (the extra one is real) |

At 60-word chunks similarity starts rejecting real rewrites (1/30), so 90 is the setting. Short
input takes a single chunk and reproduces the old call exactly, so nothing previously measured on
short text moved.

### What was not broken

`roles`, `hedges` and `numerals` were probed identically and are position-independent to 552 words.
The defect was confined to the two transformer-backed gates, which is the expected shape — the
other three do not have a context window to run out of.

`tests/test_gates_read_the_whole_document.py` pins the invariant for all five rather than
regression-testing the two: a gate added later that reads a fixed-size prefix fails on its first
run. Verified non-vacuous by disabling chunking, which fails 6 of its 31 assertions.

---

## Result 36 — the zero-dependency meaning gate cannot see a destroyed sentence, at any setting

Result 35's chunking fix applies to `similarity()` before it chooses a backend, so the
zero-dependency Dice path inherits it. Worth checking whether that is enough, because on a
`pip install untell` with no extras, `token_overlap` is the **only** meaning gate there is.

It is not enough. Replacing an entire sentence with unrelated text in a 280-word document, against
the 0.50 token bar:

| chunk size | score | caught? | faithful rewrites rejected (n=25) |
|---|---|---|---|
| whole text | 0.9680 | no | 0/25 |
| 90 words (shipped) | 0.8732 | no | 0/25 |
| 40 words | 0.7500 | no | 0/25 |
| 20 words | **0.1000** | **yes** | **3/25** |

Chunking did help — 0.9680 → 0.8732 — and it removed the truncation artefact. It did not make the
gate able to catch this, and going finer does not either: the only granularity that catches the
destroyed sentence also rejects 12% of genuine rewrites.

**There is no setting that separates them, and the reason is structural.** Dice measures word
overlap. A faithful paraphrase of a 20-word window rewords most of it; a destroyed one replaces all
of it. Both have low overlap. The metric does not contain the information needed to tell them
apart, so no threshold can.

The honest statement of what the free tier guarantees is therefore narrower than "meaning
preserved": it detects **drift across a document** and does not detect **destruction of a single
sentence**. `.[full]` adds the entailment and role gates, which do separate the two — the same
280-word case scores 0.98 contradiction there.

This is recorded rather than fixed because the alternative is choosing 20-word chunks and quietly
accepting a 12% false-rejection rate on the tier that exists to work everywhere. Stating the limit
costs nothing; a gate that rejects one rewrite in eight would cost the free path its usefulness,
and users would not know why.

---

## Result 37 — repairing the meaning gates cost nothing on the headline

Result 35 found both model-backed gates truncating at roughly 130 words. The documented headline —
post 0.285, flagged 21.7% — was measured under those gates, on a corpus whose median document is
284 words. Any candidate that damaged meaning in the back two thirds was accepted unopposed, so the
number could have been resting on damage nobody could see. Repaired gates are strictly stricter:
the loop can only lose candidates, never gain them.

Rather than reproduce the n=40 × 3 protocol — hours, now that each gate call costs 3.4× more — this
measures the **delta**, which is the actual question. Same 16 RAID documents, same seeds, run twice:
once with chunking disabled (exactly the old truncating behaviour) and once as shipped.

| | post mean max | flagged |
|---|---|---|
| pre-rewrite | 0.9250 | 100% |
| gates truncating (as the headline was measured) | 0.3118 | 31.2% |
| **gates repaired (as shipped)** | **0.3078** | **31.2%** |

**−0.0040 and an identical flagged rate.** Result 34 measured this harness's single-run noise at
±0.013 score and ±0.075 flagged; the difference is a third of the score noise and exactly zero on
the flagged rate. Nothing moved.

### What that does and does not mean

It means the documented headline was **not** built on unnoticed late-document meaning damage. That
was the worry, it was a reasonable worry, and it is answered: the rewriter was not exploiting the
hole, so closing it took nothing away.

It does not mean the repair was unnecessary, and the distinction matters because the cheap reading
here is "the fix changed nothing, so the bug did not matter". The bug was that a rewriter *could*
invert any claim after the first ~130 words with no gate objecting. That this particular rewriter
happened not to is a fact about the rewriter, not a property of the system — and it is exactly the
kind of fact that stops being true the moment someone adds a transform, or plugs in a hosted LLM
backend, or raises the intensity. A safety check is worth having when it costs nothing, which is
what this table shows it costs.

It also earned its keep immediately in a way the table does not capture: the repaired gate caught
`"an original way to medical image segmentation"` and `"An unsupervised segmentation way"` in real
output, which is broken English no metric in this repo scores as broken, and which led to the
preposition-collocation fix.

n = 16, one run per arm. The two arms share texts and seeds, so the comparison is paired even though
neither absolute figure is a replacement for the n = 40 × 3 headline.

---

## Result 38 — on RAID, one ensemble member wins everything and one never wins at all

`rewriter/ensemble.py` opens with a claim about why the ensemble exists:

> Measured, different free rewriters win on different inputs: the rule-based composite crushes some
> paragraphs while a neural T5 paraphrase crushes others (and backfires on the first). No single
> free method dominates.

That is the whole argument for running three rewriters instead of one. It has not been re-measured
since it was written, so here it is on 8 RAID texts, each member run standalone on the same input,
scored at the full tier:

| member | wins | worse than its input | mean post | total time |
|---|---|---|---|---|
| composite | 0 | 0 | 0.5600 | 111.6 s |
| mt_pivot | **0** | **1** | 0.8884 | 257.8 s |
| neural | **8** | 0 | **0.1434** | 990.7 s |

**Neural won every text.** Not most — all eight. On this corpus the premise above does not hold:
one method dominates, and it is not close (0.1434 against 0.5600 and 0.8884).

**`mt_pivot` never won, had the worst mean, and made one text more detectable than the input it was
given** — 0.9992 from a 0.9604 source, consistent with `untell-compare` putting back-translation at
0.995. It cost 258 seconds to contribute nothing.

### What follows, and what does not

The ensemble is unharmed by this: it takes the per-input minimum, so a member that never wins costs
time and cannot cost quality. The guarantee was checked separately and holds — on two texts the
ensemble beat every member individually, because the members are stochastic and it runs its own
internal contest.

What is affected is the *reason* stated for having three members. On RAID it is one member plus two
that are paying rent, and 258 of those seconds buy nothing measurable.

**`mt_pivot` is not being removed on this evidence.** n = 8, one corpus, one run per member. The
claim it would contradict was itself made on a corpus that is not named, and replacing an unnamed-
corpus claim with an n=8 claim is not an improvement in rigour — it is the same mistake with fresher
numbers. What would justify removal is the same measurement on HC3 and on the demo corpus, at n ≥ 30,
with repeats; if mt_pivot wins nothing anywhere, it is dead weight in the strongest free path.

The docstring has been corrected to say what is measured rather than what was assumed.

Also worth recording for anyone choosing a backend: neural is **8.9x** the wall-clock of composite
(991 s against 112 s for the same eight texts) for that 0.56 → 0.14. That is the actual trade, and
neither number appears anywhere a user picking `--rewriter` would see it.

---

## Result 39 — spot-checking four documented constants, and the one that is register-blind

`untell-audit` enforces that a measured number states its provenance. It cannot re-derive the
*value*, so nothing has ever checked whether these constants still describe the corpus they claim
to. Four re-derived over 400 human documents (200 HC3 + 200 RAID):

| constant | claimed | re-measured |
|---|---|---|
| merge connector `, and ` | 0.659 | 0.652 |
| merge connector `, but ` | 0.216 | 0.224 |
| merge connector `, so ` | 0.079 | 0.084 |
| merge connector `, while ` | 0.039 | 0.032 |
| merge connector `, though ` | 0.007 | 0.007 |
| parentheses / 100 w | 0.80 | 0.82 |
| `This …` openers / 100 sentences (RAID) | 4.59 | **4.59** |
| contractions / 100 w | 0.67 | **0.32** |

Six of seven reproduce. The last one looked like a factor-of-two error and was not: I had pooled
HC3 with RAID. Split, **HC3 human is 0.66** — the constant is right, and my pooled figure was the
misleading number. The lesson this repo keeps relearning, this time applied to my own measurement
before it became a claim.

### The real finding

The constant is correct for HC3 and **applied to everything**. Measured on 25 texts per corpus,
contractions per 100 words in our own output:

| corpus | human | our output | ratio |
|---|---|---|---|
| HC3 | 0.666 | 0.687 | **1.0×** |
| RAID | 0.045 | 0.200 | **4.4×** |

The pass hits the human rate exactly on forum answers and overshoots academic abstracts by 4.4×.
That is the third constant in this project to behave differently by register, after
`formulaic_transition` (0.88 on HC3, 0.60 on RAID) and `hedge_stacking` (0.53 against 0.88).

### The obvious fix, measured and not shipped

The comment above the constant already records that AI input contracts *at or above* the human rate
in both corpora — so the input's own rate is a register-aware target needing no register detection.
Capping the budget at `min(constant, input_rate)`:

| corpus | shipped | capped by input rate |
|---|---|---|
| HC3 | 1.0× | **0.6×** |
| RAID | 4.4× | **1.2×** |

Total distributional error falls from 3.4 to 0.6, and it is still not obviously right: it trades an
overshoot on the corpus the constant was tuned for into an undershoot there. Those are not
symmetric — overshooting a human distribution manufactures a signature, undershooting merely leaves
formal text formal — which argues for the cap. Neither version moves the detector: this pass was
measured at ±0.0003 when it was written, so the whole question is distributional.

**Not shipped on one run of n=25 per corpus.** Result 38 criticised replacing an unnamed-corpus
claim with a thin one; doing it here would be the same error. What would settle it: both corpora at
n ≥ 30 with repeats, the detector delta confirmed at zero for the capped version, and a decision
recorded about whether undershoot on HC3 is an acceptable price for matching RAID.

---

## Result 40 — where the loop's time actually goes

Nothing in this repository has ever profiled the loop, so every performance statement in it —
including mine, earlier in this document — has been a guess about a part rather than a measurement
of the whole. `cProfile` over 3 RAID texts at `--tier full --rewriter composite --best-of 3`,
409.6 s total:

| | cumulative | share |
|---|---|---|
| `_score_with_detectors` | 385.8 s | **94%** |
| — of which `windowed_max` | 270.8 s | 66% |
| — of which `roberta_openai` | 151.1 s | 37% |
| — of which `fast_detectgpt` | 130.0 s | 32% |
| — of which `perplexity_burstiness` | 113.1 s | 28% |
| `surgical_substitute` → detector batches | 144.7 s | **35%** |
| everything else (rewriting, gates, I/O) | ~24 s | 6% |

**94% of the loop is detector scoring.** Not rewriting, not the meaning gates, not preserve-lock.

### This corrects something I wrote earlier in this document

Result 35 reported the chunked meaning gates costing 0.17 s → 0.57 s per pair and described it as
"3.4× dearer". That number is right and the framing was misleading: the gates do not appear in the
top thirty entries of this profile at all. Against 385 s of detector passes, tripling a component
that costs single-digit seconds is not a performance decision worth the sentence I gave it. The
honest version is that the gate fix was free in practice, and I said "3.4×" without knowing what it
was 3.4× *of*.

### The surgical stage

`surgical_substitute` accounts for 144.7 s — 35% of the run — in detector batches, one per ranked
word. So: does the stage earn a third of the wall clock? Measured directly, 10 RAID texts, same
seeds:

| | post mean max | tells/100w | time |
|---|---|---|---|
| `structural` alone | 0.4924 | 7.07 | ~0 s |
| `composite` (structural + surgical) | **0.4018** | 6.97 | 88.2 s |

**Yes.** −0.091 on the score, about seven times the ±0.013 noise floor from Result 34, for 8.8 s
per text. The tells barely move (7.07 → 6.97), so essentially all of the gain is the detector-guided
substitution doing the thing it is named for.

I wrote the opposite here first and the measurement corrected it. Having read that `prefer_tells=True`
makes the *ranking* detector-independent, I concluded the batches must be a mere guard against
tell-swaps raising the score, and wrote that a third of the runtime buys "the tell swaps did not
make things worse". That is wrong: the acceptance test takes a strict score win first and only falls
back to the tells objective within a noise band, so the batches optimise and guard. The 0.0002
figure quoted for this pass elsewhere is from the *standalone* surgical rewriter on the stdlib path,
not from the composite chain at full tier — a different configuration answering a different
question, which I had folded into one number.

### The obvious optimisation, measured and rejected

`windowed_max` scores its windows one at a time through a per-window callback, so batching them
into a single forward pass is the first thing anyone will reach for — 66% of the run, and the repo
already has `batch_score_texts` elsewhere. Measured on `roberta_openai`, four ~320-word windows:

| | median of 3 |
|---|---|
| one at a time | 0.686 s |
| batched into one forward pass | **0.632 s** |

**8%.** And that is the best case: the four windows in this test were identical, so they padded to
the same length. Real windows differ, and the padding waste makes batching worse than this.

The profile says why. `torch._C._nn.linear` alone is 223 s of the 409 s — the time is matrix
multiplication, not Python or framework overhead, and batching amortises only the latter. On a GPU
this trade looks completely different; on the CPU this project targets, it does not.

Not implemented. An 8% win is not worth a change to every detector adapter and the scoring core,
and writing that down is the point: the next person to profile this will see 66% in one function
and reach for the same lever.

The levers that would actually work are fewer windows (a wider window, at the cost of more
truncation inside each), a smaller model, or not scoring every candidate at full tier — all of
which trade accuracy for speed, which is a different decision from an optimisation.

### For anyone choosing a tier

`windowed_max` is 66% of the run on its own: long documents are scored in overlapping windows, and
that is what makes the full tier expensive. It is also what fixed the detectors reading only the
first ~380 words. The cost is the fix, not an accident of it.

---

## Result 41 — the "higher-fidelity" meaning gate rejected 95% of good rewrites

Six tests skip on every run. Four are honest opt-in gates (a 600 MB model, a tier flag). Two said
`bert-score not installed` — and **no CI job installed it either**, so they had never run anywhere.
`bert-score` is declared in the `quality` extra, and `quality.py` treated it as the highest-fidelity
backend with its own threshold, so `pip install untell[quality]` silently switched the meaning gate
onto a code path nothing had ever exercised.

Installing it, the two tests fail immediately: a faithful paraphrase is **rejected**.

### It is not a mis-tuned threshold

The first reading is that 0.88 is too tight. Measured on 20 real composite rewrites: median 0.8293,
and **19 of 20 below the bar**. So `untell[quality]` made the loop discard 95% of its own good
candidates. But recalibrating cannot fix it, because the two populations are *inverted*:

| | BERTScore range |
|---|---|
| faithful paraphrases | 0.7995 – 0.8409 |
| meaning-CHANGED rewrites (negation, quantifier, role swap, number, evaluation flip) | **0.8526 – 0.9577** |

Every meaning-changed pair scores **above** every faithful one. No threshold separates them.

The cause is structural. BERTScore rewards token-level overlap. A negation flip changes one word
and keeps the rest; an honest paraphrase changes many. So the metric systematically prefers the
rewrites the gate exists to reject.

This is the same failure the module already documents for cosine similarity — "it passed rewrites
that INVERT the source while rejecting 6 of 8 faithful formal→casual rewrites" — which is *why* the
NLI gate was built. BERTScore has it too. Being a stronger metric does not help when the thing it
measures is the wrong thing.

### What changed

`similarity()` no longer routes the gate through BERTScore, and `method()` no longer reports
`"bertscore"` — reporting a backend the gate does not use left `recommended_bar()` selecting a bar
for a path never taken, which produced a token-overlap bar of 0.5 against a cosine score.

`_bert_score_similarity` is kept and still reported by `untell-quality --json`. Recall against a
reference is a useful number; it is just not a meaning gate.

The `quality` extra is now installed in the full-tier CI job. An optional extra that no environment
exercises is an untested code path a user can enable with one pip flag — which is exactly how a
gate that rejects 95% of good rewrites shipped and stayed.

---

## Result 42 — re-deriving the `targeted` rewriter's fix: direction holds, magnitude does not

Result 39 established re-deriving documented constants. This does the same for a documented
*behavioural* claim. The roadmap's Priority-1 defect table says:

> `targeted` rewriter did **literally nothing** on the zero-dep path (0/15 texts changed) —
> **fixed**: re-measured 2026-08-08 it changes **14/15** and moves the score **−0.186**, via a
> whole-text fallback that says so on stderr

Re-measured, n = 15 per cell:

| corpus | tier | changed | mean score delta |
|---|---|---|---|
| HC3 | full | 10/15 | −0.0007 |
| HC3 | zero-dep (stdlib) | 11/15 | −0.0591 |
| RAID | zero-dep (stdlib) | 12/15 | −0.0639 |
| **claimed** | *unstated* | **14/15** | **−0.186** |

**The fix is real.** The rewriter was doing nothing (0/15) and now changes 10–12 of 15 on every
configuration tried, with the fallback warning firing on all fifteen — so per-sentence targeting
still never engages on the stdlib path and the whole-text fallback is what does the work, exactly
as the note says.

**The numbers do not reproduce.** 14/15 against 10–12/15, and −0.186 against −0.06 at best — three
times the movement I can measure anywhere. The claim names no corpus, no tier and no n, so there is
no configuration to check it against; three plausible readings all come out lower.

I am not calling it wrong. It may have been measured on a corpus I have not tried, or before a
later change moved it. What is certain is that it **cannot be verified as written**, which for a
number sitting in a defect table as evidence that a defect was fixed is the same problem as being
wrong — a reader cannot act on it either way.

This is precisely the gap `untell-audit` is honest about: it enforces that a measured claim states
its provenance, and this one states a date and nothing else. A date is not provenance. The entry
should carry its corpus, tier and n like every figure in this document does, and the fix is to
re-measure it deliberately rather than to quietly swap in my numbers — mine are n=15, single-run,
and would be exactly the thin replacement Result 38 argued against.

### Result 42b — the `surgical` claim, re-derived: understated, and identifiably so

The same table's `surgical` row states its conditions properly — "over 30 HC3+RAID texts", with a
before and an after — so unlike Result 42 it can be checked. Reproduced with 15 HC3 + 15 RAID:

| | claimed | re-measured |
|---|---|---|
| texts changed | 19/30 | **23/30** |
| tells/100w before | 8.02 | **8.02** |
| tells/100w after | 7.22 | **6.88** |
| detector delta | −0.004 | **−0.0212** |

**The before value reproduces to the digit**, which is what makes the rest trustworthy: it confirms
the corpus construction is the same one, so the differences are about the code and not about a
different sample.

Every outcome is *better* than documented, and the cause is plausibly in this document. Results 31
and 32 added inflections and twelve vocabulary entries to the substitution map — `leverages` and
`leveraging` where only `leverage` was covered — so a pass that depends on map coverage doing more
work is the expected consequence.

Worth flagging the direction. A discrepancy that flatters the project is where bias gets in, and
"the numbers improved" is the easiest thing in the world to accept without checking. It survives
here for one specific reason: the *baseline* matches exactly. A run that had drifted to an easier
sample would have moved 8.02 too.

Single run, n = 30. The row now cites this re-derivation rather than silently carrying either set
of numbers as fact.

---

## Result 43 — the lite tier's fixed false-positive rate is corpus-dependent, and the single number hides it

Result 24 fixed the lite tier flagging 60% of human text, reporting **60% → 15%** over 120 human
texts across both corpora. It also established something about the *pre*-fix number that matters
here: 60% was "identical in HC3 and RAID separately — so it is a property of the lite detector, not
of one corpus."

Re-measured post-fix at n = 100 per corpus, `tier=lite`, pure-stdlib path, reading the `flagged`
field the fix introduced:

| corpus | human texts flagged |
|---|---|
| HC3 (forum answers) | **30/100 = 30%** |
| RAID (paper abstracts) | **10/100 = 10%** |
| pooled | 20% |
| Result 24's figure | 15% |

The fix is real — 60% to 20% pooled is most of the problem gone. But the property that made the
original defect easy to reason about **did not survive it**. The pre-fix rate was corpus-independent;
the post-fix rate differs by 3× between corpora, and the single headline number sits between them
describing neither.

What that means for a user is concrete: someone pasting conversational prose into the free tier is
told it reads as AI **three times in ten**, not fifteen in a hundred. Someone pasting an academic
abstract is told so one time in ten. The documented figure understates the first case by 2× — and
the first case is the likelier one for a tool whose landing page invites you to paste your own
writing.

This is the fifth constant in this document to behave differently by register, after
`formulaic_transition`, `hedge_stacking`, contractions and the tell catalogue as a whole. The
pattern is consistent enough now to be the default expectation rather than a recurring surprise:
**a threshold calibrated on pooled corpora is calibrated for neither.**

Not re-tuning it here. The threshold trades false positives against AI recall along a curve Result
24 already swept, and picking a new point needs that whole sweep re-run per corpus — plus a decision
about whether the free tier should be tuned for conversational or formal input, which is a product
question. What is fixed is the claim: the row now gives both numbers instead of their average.
