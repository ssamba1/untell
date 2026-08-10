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

## Result 44

**A word boundary mangled into a backspace, and the 2526-test suite that did not notice.**

Found by a new `untell-audit` check, written for a different reason. A stray carriage return had
just been spliced into a ROADMAP row — `\ref` built in a non-raw Python string became CR + `ef`,
which rendered as `ef` and is invisible in a diff. Python warns about `\c` and says nothing about
`\r`, because `\r` is a valid escape; that silence is why it landed. The check that catches it
mechanically — no tracked text file may hold a control character other than tab and newline — found
the CR, and then found two more offenders that had nothing to do with it:

| file | byte | what it was meant to be |
|---|---|---|
| `untell/rewriter/structural.py:1212` | `U+0008` | `\b` in `_FRONTED_RE` |
| `untell/scripts/audit.py:113-114` | `U+0008` ×2 | `\b` in the local/commercial count patterns |

Both sat inside `r"..."` strings, where a real backslash-b would be correct and a literal backspace
looks exactly the same on screen. No text contains a backspace, so both patterns matched nothing,
ever.

`_FRONTED_RE` counts the sentences a block has **already** fronted, so the transform can stop at
the human rate: `budget = 0.20 * eligible - already`. With the regex dead, `already` was always 0
and the budget was always full. Measured on a six-sentence block that already fronts three of its
three eligible sentences — a text that should receive nothing:

| | already counted | budget | sentences newly fronted per run (200 draws) |
|---|---|---|---|
| before | 0 | +0.60 | **0.67** |
| after | 3 | −2.40 | **0.00** |

So the defect was not a dead transform but a broken calibration: untell added fronting to text that
was already at or above the human share of it — the match-the-human-distribution failure mode
arriving through a typo instead of through a mis-set constant.

The audit patterns were vacuous in the same way — `(\d+)\s+local\b` could never match, so a check
that reports PASS today was reporting PASS on nothing.

Three things worth keeping:

- **A regex that matches nothing is indistinguishable from a corpus that contains nothing.** Every
  one of these read as a legitimate zero. The counter said "this text fronts nothing", the audit
  said "no mismatch found", and both were true statements about an empty match set.
- **`r"..."` does not protect you from a byte that is already wrong.** Raw strings prevent Python
  from interpreting an escape; they do nothing about a file that already holds the interpreted
  character. Every review of these lines read `\b`, because that is what a backspace looks like.
- **The suite could not see it.** 2526 tests passed with the regex dead and passed with it live.
  Nothing asserted that `_FRONTED_RE` matches a fronted sentence, so nothing distinguished the two
  worlds. The test added with this result is that assertion, plus the below-rate case that would
  fail if the transform stopped firing entirely.

## Result 45

**`tells/100w` points the right way, and is mostly one category.**

Re-derivation of the defect row "the headline naturalness metric pointed **backwards** on real
text", at n=100 pairs per corpus.

| corpus | human tells/100w | AI tells/100w | direction |
|---|---|---|---|
| HC3 | 0.551 | 7.335 | correct, gap +6.78 |
| RAID | 1.215 | 12.884 | correct, gap +11.67 |

The row is fixed: the metric ranks AI text above human text on both corpora, by a wide margin. But
the original defect was a *component* pointing the wrong way while the aggregate looked fine, so the
aggregate agreeing is not the end of the check. Per category:

| | HC3 | RAID |
|---|---|---|
| `repeated_phrasing` share of every tell counted | **91.1%** | **82.7%** |
| all other categories combined, per AI text | 1.34 hits | 6.74 hits |
| categories firing on ≤5% of AI texts | 4 of 9 | 6 of 12 |
| categories that never fired on AI text at all | 7 of 16 | 4 of 16 |

So `tells/100w` is, to a first approximation, a repeated-phrasing meter wearing the name of a
sixteen-category catalogue. That is not a defect — the metric does the job the row asked about —
but it does mean a change to `repeated_phrasing` moves the headline number and a change to anything
else effectively does not.

**Nine categories appear to point backwards, and none of them do.** Read as rates, nine categories
show human above AI on at least one corpus, three of them on both (`em_dash`, `semicolon_crutch`,
`inflated_copula`). Read as counts, over 200 texts:

| category | HC3 human / AI | RAID human / AI |
|---|---|---|
| `em_dash` | 2 / 0 | 1 / 0 |
| `semicolon_crutch` | 4 / 0 | 4 / 3 |
| `inflated_copula` | 1 / 0 | 1 / 1 |

Single-digit hits. Every one of those "inversions" is one or two paragraphs, and a rate computed
from two hits and printed to three decimals looks exactly like a finding. The direction of a
near-inert pattern is not measurable at this n, and reporting one would have been the same error as
the original row in the opposite direction.

Two things worth keeping:

- **A correct aggregate can rest on one component.** Checking the headline number told us nothing
  about fifteen of the sixteen categories, and the original defect lived in exactly that gap.
- **Normalise, then look at the raw count before believing the normalised value.** Per-100-word
  rates made four categories look like real inversions. The counts behind them were 1, 1, 2 and 4.

The direction is now a test (`tests/test_tells_point_the_right_way.py`) with offline fixtures that
reproduce the corpus separation closely — 11.66 AI vs 0.52 human, against 7.3/0.6 on HC3 — so CI
catches an inversion without a corpus download.

## Result 46

**The central competitive claim holds; one number under it did not.**

Re-derivation of the last defect row, "the central competitive claim quoted a sentence **that exists
in no commit**". The fabricated quote is long gone and a check already prevents its wording
returning. What the row does not cover is whether the claim that *replaced* it is true, so this
checks that instead, against all 435 census records.

The claim: five meaning gates and byte-exact citation locking that **no profiled repo combines**.

| | count |
|---|---|
| repos profiled | 435 |
| any fact-preservation mechanism | 131 |
| any meaning-verification mechanism | 85 |
| both fields non-empty | 56 |
| both, after reading the prose | **0** |

Every repo with a real mechanical meaning gate says `none` for fact preservation, in those words —
`apt` (bidirectional RoBERTa-NLI), `StealthRL`, `Waterfall`, `CLARE`, `DeepfakeTextDetection`,
`conversantech/humanizer-ai`, `TSAPA`, `AuthorMist`, `ii5/Humanizer_transformers`. The claim holds.

Worth stating plainly, because the page could be read as claiming more: **citation locking on its
own is not unique.** `marmbiz/humanizer-de` (80★) extracts anchor spans — numbers, dates, URLs,
DOIs, legal references, quoted strings — into a versioned JSON ledger and lints against it. It has
no meaning-gate stack, so the *combination* claim survives, but "nobody locks citations" would be
false and is not what the page says.

**Keyword matching cannot tell presence from absence.** A first pass looked for meaning-gate and
citation vocabulary in the same record and returned one repo with both. Reading it, the sentence
was *"No automated cosine similarity, NLI e[ntailment]..."* — the words were there because the
entry denies them. A grep over 435 free-text verdicts had produced exactly one hit and it was
backwards. Related to Result 45's lesson, one level up: there, a rate hid a count of two; here, a
match hid a negation.

**The number that was wrong.** The pages say 49 of 435 put a detector in the loop, 43 at inference
time. Re-derived: 49 is exact. 44 is the inference-time count — 49 answer "yes", and five of them
state the loop is training-time or offline only (`StealthRL`, `AuthorMist`, `CAU-ISS-Lab`,
`iljung1106`, `OUTFOX`). Corrected in all three places it appeared.

One repo out of 435 is not much on its own. What makes it worth a result is that no written rule
reproduced it, so there was no way to tell a typo from a judgement call about a borderline repo.
`check_census_counts` now re-derives every published census count from the JSON, with the reading
rules stated in code:

- `detector_in_loop` is answered with a verdict word, so it reads by prefix. Applying the other
  fields' rule to it counts the 28 `unclear` entries as yes and returns 112.
- `meaning_verification` and `fact_preservation` are descriptive prose, so they read by whether
  they open with a denial.
- "139 of 435 target another language" is deliberately **not** checked. The census JSON has no
  language field; confirming that count would mean inventing a rule and calling the result a
  verification.

## Result 47

**Engineering raises the floor and does nothing to the ceiling.**

The competitive question this repo had never actually measured: what separates the repos with stars
from the repos without them? Re-derived from all 435 census records.

| group | repos | median ★ | mean ★ | best |
|---|---|---|---|---|
| detector in the loop | 49 | 10 | 320 | 8,720 |
| automated meaning verification | 85 | 3 | 3,697 | 298,793 |
| any fact preservation | 131 | 2 | 3,228 | 298,793 |
| **no mechanical verification at all** | 275 | 1 | 581 | 68,545 |

A detector loop is worth 10× the median of a repo with nothing mechanical in it — and the largest
repo with no mechanical anything has 68,545 stars, while the largest with a detector loop has
8,720 and is a red-teaming scanner rather than a humanizer.

By category, the concentration is worse:

| category | repos | median ★ | share of all stars |
|---|---|---|---|
| `prompt-guide` | 184 | 1 | **92%** |
| `rule-based-rewriter` (ours) | 38 | 2 | **0.3%**, best 413 |

584,528 stars over 435 repos; the top 20 hold **98%**. Six of the eight largest contain no
executable code.

**The technique nobody uses.** Mining the 49 detector-coupled repos for search strategy: 12 iterate
until it passes, 5 use RL, 4 ensemble detectors, 3 couple per token, 3 use gradients, and **0 use
beam or tree search**. Every detector-coupled repo in the census, this one included, is greedy —
`best_of=3` draws three candidates and discards two before either can be extended. A beam keeps *k*
candidates across iterations, needs no GPU, and costs linearly in width.

Three things worth keeping:

- **A category can be won and still be worth nothing in the currency being counted.** We are near
  the top of a category holding 0.3% of the field's attention. That is a real position and it is
  not a star position, and conflating the two would misdirect every future decision.
- **The measurement contradicts the intuition that quality compounds into adoption.** 275 repos have
  no mechanical verification of any kind and one of them has 68,545 stars. Tests, gates, CI and
  published negative results show no correlation worth acting on.
- **A zero in a technique table is the most interesting cell in it** — provided it is a zero for
  lack of trying rather than for a reason. Beam search is untried here; whether it pays is a
  measurement nobody has run, and the honest next step is to run it at matched scoring budget
  rather than to build it.

Written up as [what-would-make-this-the-top-repo.md](what-would-make-this-the-top-repo.md).

## Result 48

**Beam search is a coin flip. The zero in the census technique table is not a missed opportunity.**

[Result 47](free-ceiling-measured.md) found that none of the 435 profiled repos searches — every
detector-coupled one, this repo included, is greedy. That looked like an opening. It is not.

Greedy and beam were implemented against the same primitives in one harness, so the comparison is
between search strategies rather than between a harness and the product. Budget is matched exactly:
greedy draws B candidates from the single incumbent each iteration, a beam of width *k* draws B/k
from each of *k* incumbents. Both spend B rewriter draws and B detector passes per iteration —
12 draws per text, confirmed identical in the output.

Paired on the seed, so every arm sees the same text under the same RNG state. 15 AI texts per
corpus, 3 repeats, 45 paired outcomes per arm.

| corpus | arm | mean | wins | losses | ties | mean Δ |
|---|---|---|---|---|---|---|
| HC3 | greedy | 0.4596 | — | — | — | — |
| HC3 | beam 2 | 0.4537 | 18 | 18 | 9 | −0.0060 |
| HC3 | beam 4 | 0.4586 | 17 | **21** | 7 | −0.0010 |
| RAID | greedy | 0.2290 | — | — | — | — |
| RAID | beam 2 | 0.2245 | 13 | **18** | 14 | −0.0045 |
| RAID | beam 4 | 0.2251 | 15 | **22** | 8 | −0.0039 |

The mean deltas are all slightly negative, which read alone would look like a small win. The paired
record says otherwise: beam **loses more often than it wins on three of the four arm/corpus
combinations**, and the fourth is exactly 18–18. The negative means come from a handful of large
wins against a larger number of small losses, which is what a coin flip looks like when the payoff
is skewed.

**The harness is faithful.** Its greedy arm was checked against the shipped loop on 6 HC3 texts at
matched settings: **5 of 6 byte-identical**, and the shipped loop better overall by 0.0097 — its
tells and voice tie-breaks find something greedy-on-score alone does not. So this is not a
comparison between two toys.

Three things worth keeping:

- **A zero in a technique table can mean the technique does not pay.** Result 47 flagged beam
  search as the one strategy nobody uses and the honest next step as a measurement rather than an
  implementation. It was: shipping a beam would have cost k× the scoring for nothing.
- **A mean delta and a paired record can disagree, and the paired record is the one to believe.**
  Every arm here improved the mean and lost the head-to-head. Reporting only the means would have
  produced "beam search improves detector score on both corpora" — technically true of those
  numbers, and wrong.
- **Check the `error` key before you score the result.** Validating the harness, a call to
  `untell_text` without a rewriter returned `{"error": ..., "final": <the input>}`; scoring that
  showed the shipped loop losing to a scratch reimplementation by 0.138. It was the unrewritten
  input. `eval/compare_humanizers.py` had the same unguarded read and would have reported our own
  tool as changing nothing in the competitor comparison; it now raises.

## Result 49

**The API answered "a" with 99.87% AI, flagged. Below 40 words the flag is not evidence.**

Found by probing the REST surface with pathological input. `/score` returns a maximally confident
AI verdict on a single letter — and `humanness()` already refuses to answer below five words, so
the repo had agreed the quantity is unmeasurable there and simply had not applied it to the path
behind `/score`, `/tells` and the CLI.

MEASURED on 40 HC3 pairs at the 0.30 default, full tier, truncating both halves of each pair to
the first N words:

| first N words | human flagged | AI flagged | separation |
|---|---|---|---|
| 5 | **98%** | 100% | none |
| 10 | 62% | 95% | poor |
| 20 | 40% | 100% | weak |
| 40 | 28% | 100% | usable |
| 80 | 17% | 100% | good |

At five words a human paragraph and an AI paragraph are indistinguishable: 98% against 100%. The
detector is not detecting anything, it is flagging everything, and the score being 0.9987 rather
than 0.5 makes it read as certainty rather than as noise.

The fix is the one the lite-tier stdlib path already uses: keep the number and say, with the
measured rate, that this configuration is not one to trust. `score_text` now appends a warning
below 40 words carrying the rate for that band — "19 words: too short for a reliable verdict.
MEASURED on 40 HC3 pairs at this threshold, 40% of HUMAN text this length also flags."

Three decisions worth recording:

- **`max` is unchanged.** Zeroing or withholding it would break callers that store and compare it,
  for a reason invisible at the call site. The number is real; what was missing was its context.
- **Appended, not folded into the tier chain.** Tier warnings are chosen by if/elif, so a short
  text on a downgraded tier would have reported whichever was checked first and hidden the other.
  Length and tier are independent problems and a caller can have both.
- **The bar is 40 words because 40 is where separation starts**, not because it is a round number.
  20 leaves a 40% human false-positive rate; the repo's own `humanness` bar of 5 words is far too
  low for the ensemble, which at 5 words is at 98%.

This is the third defect this session in the same family — a confident answer where the honest
answer is "not measurable". The other two were CJK text reported as perfectly clean, and a Chinese
paragraph reported as "shorter than 5 words". In each case the code knew the limit somewhere and
did not apply it at the surface the user actually touches.

## Result 50

**Sweeping one defect family across every surface: two real, three already correct.**

Results 44, 49 and the CJK fix were the same defect three times — a confident number where the
honest answer is "not measurable", with the limit known somewhere in the code and not applied at
the surface the user touches. Rather than wait to trip over a fourth, every public surface was
checked deliberately.

| surface | verdict on unmeasurable input | outcome |
|---|---|---|
| `humanness` | already refuses below 5 words | correct; its *reason* was wrong and was fixed earlier |
| `score_text` | `"a"` -> P(AI) 0.9987, flagged | **fixed** — caveat below 40 words with the measured rate ([Result 49](free-ceiling-measured.md)) |
| `score_tells` | `Moreover.` -> 100.0 per 100w | **fixed** — caveat below 14 words, derived from 100/N vs the AI mean |
| `score_sentences` | already warns: per-sentence AUROC 0.493 on the stdlib path | correct |
| `verify` | prints guidance and returns early when nothing ran | correct |
| MCP `score` / `tells` | returns the scorer dicts unwrapped | inherits both new caveats |
| REST `/verify` | `passes_all: false` with `n_configured: 0` | **schema fixed** — the boolean now documents that false also means "nothing ran" |

Two things worth keeping:

- **Three of the six were already right, and finding that out cost as much as the fixes.** The
  `verify` case looked like the strongest candidate — `passes_all: false` on an empty checker set
  is a false verdict by any reading — and `_render` turned out to return early with a better
  message than the one being written to replace it. The replacement was unreachable code and was
  reverted. A sweep that only reports what it changed overstates what was wrong.
- **The same behaviour can be correct in one channel and wrong in another.** `passes_all: false`
  with nothing configured is conservative and right, and the CLI explains it in a sentence. The
  REST consumer gets the boolean with no sentence attached, and a machine client reading it acts
  on "failed". The fix was not to change the value, which a test pins for good reason, but to say
  in the schema what it means — the only place a machine client can read.

## Result 51

**A non-breaking space nearly doubled the false-accusation rate on human writing.**

The concurrent session had just found `hc3_roberta` reading punctuation spacing as authorship, so
the obvious question was whether that was one bug or one instance of a class. Six semantically
neutral rewrites, four full-tier detectors, mean absolute change in P(AI):

| neutral rewrite | perplexity | roberta_openai | hc3_roberta | fast_detectgpt |
|---|---|---|---|---|
| trailing spaces | 0.0039 | 0.0024 | 0.0001 | 0.0388 |
| double spaces | 0.0562 | 0.0000 | 0.0000 | 0.1059 |
| CRLF line ends | 0.0952 | 0.0063 | 0.0015 | 0.0586 |
| curly quotes | 0.0139 | 0.0000 | 0.0000 | 0.0770 |
| **space -> U+00A0** | 0.1122 | 0.3068 | **0.9990** | 0.3919 |

A sixth transform, hard-wrapping at 40 characters, moved everything by 0.38–0.99 and was discarded:
it splits words mid-token, so it is not a neutral rewrite and proves nothing.

The non-breaking space is neutral. It is visually identical to a space and it is what a paste out
of Word, a web page or a PDF contains. Measured on 10 HC3 pairs, full tier:

| | mean P(AI) plain | with U+00A0 | flagged plain | flagged nbsp |
|---|---|---|---|---|
| human | 0.4322 | **0.7801** | 5/10 | **9/10** |
| AI | 0.9996 | 0.8935 | 10/10 | 10/10 |

**The entire effect lands on human writers.** AI text is flagged either way; human text goes from
half flagged to nearly all flagged, for a change no reader can see.

`scrub_hidden` already normalises these characters, so the rewrite loop was never affected — the
damage was confined to the scoring path, which is what `untell score`, `/score` and the MCP `score`
tool call directly. `_normalise_ws` existed for exactly this class of problem, and its own docstring
records spacing swings of up to 0.13 as the reason it was written. Its pattern was `[ \t]{2,}`:
ASCII only, and runs of two or more, so a single U+00A0 between words passed straight through.
Folding Unicode category-Zs separators before collapsing runs takes the delta to 0.0000 on every
detector, with ordinary prose byte-identical.

Two things worth keeping:

- **A fix for a class is not a fix for the class unless you enumerate the class.** `_normalise_ws`
  was written to make scoring invariant to spacing and left the most common non-ASCII spacing in
  existence untouched. The docstring, the measurement and the intent were all right; the character
  set was too small.
- **Ask which side of the ledger an asymmetric error lands on.** A detector that mis-scores AI text
  costs the tool an evasion. A detector that mis-scores human text costs a person an accusation.
  This one only did the second, and nothing in the aggregate would have shown that — the mean over
  both halves moves by +0.12, which looks like noise.

## Result 52

**The same character defeated the tell catalogue, and the fix now lives in one place.**

[Result 51](free-ceiling-measured.md) fixed the scoring path against Unicode spaces. The obvious
next question — since the lesson recorded there was that a fix for a class is not a fix for the
class unless the class is enumerated — was whether anything else in the repo compares against a
literal space. It does: every multi-word pattern in the tell catalogue.

MEASURED on a 37-word AI paragraph, replacing every space:

| | words | tells | tells/100w | humanness |
|---|---|---|---|---|
| plain | 37 | 5 | 13.5 | 37.4 |
| U+00A0 | 37 | **3** | 8.1 | 43.9 |
| U+202F | 37 | 3 | 8.1 | 43.9 |
| U+3000 | 37 | 3 | 8.1 | 43.9 |

Two of five tells vanish, because `"in conclusion"` does not match `"in\u00a0conclusion"`. The word
count is unaffected, so nothing in the output hints that patterns stopped matching. This is an
under-report for anyone pasting out of Word, and a one-keystroke evasion of our own catalogue for
anyone who notices.

The fix is not a second copy of the character class. `fold_unicode_spaces` now lives in
`untell/text_split.py` — the module that already exists because sentence splitting was written out
three times and the three copies drifted — and both `score.py` and `tells.py` call it. A test
asserts they are literally the same function object, because two modules agreeing today is not the
same as two modules that cannot disagree.

Worth keeping: **the second instance of a bug is evidence about where to look, not just something
to fix.** Result 51 could have ended at `_normalise_ws` and looked complete; the tell catalogue was
broken by the identical input, in a different file, with a different symptom — fewer tells rather
than a higher score — and nothing connected them except asking the question a second time.

## Result 53

**Enumerating the rest of the class: 75 patterns, one residual, and it is not worth fixing.**

Results 51 and 52 fixed the scoring path and the tell catalogue against Unicode spaces. Rather than
wait for a third instance, every compiled regex in `untell/` was enumerated by AST walk: **75
contain a literal space**. Where they sit, and whether they are reachable with an unfolded space:

| where | patterns | exposed? |
|---|---|---|
| `scripts/tells.py` | 13 | no — folds at entry (Result 52) |
| `scripts/score.py` | 1 | no — folds at entry (Result 51) |
| `scripts/preserve.py`, `numerals.py`, `latex.py` | 5 | no — they use `\s`, which matches U+00A0 in Python |
| `rewriter/structural.py` | 42 | only when `scrub=False` |
| `layout.py`, `detectors/base.py` | 5 | reached after folding or scrubbing |

The rewriter's 42 are almost all the contraction table — `\bdo not\b`, `\bit is\b`. They are
protected by `scrub_hidden`, which normalises these characters and runs by default on every
surface. `untell_text(scrub=False)` is the one path that reaches them raw, and there the transform
genuinely dies: over 30 seeds on a fixture containing "does not", "they are" and "we will not",
plain input produced `doesn't` and U+00A0 input produced **nothing at all**.

**And it does not matter.** Measured end to end over 6 HC3 texts, composite, 2 iterations:

| input | scrub | mean final P(AI) |
|---|---|---|
| plain | True | 0.4954 |
| plain | False | 0.4954 |
| U+00A0 | True | 0.4954 |
| U+00A0 | False | **0.4965** |

A cost of **0.0011**, against a noise floor of ±0.013 for this harness. One transform dies and the
other transforms in the composite absorb it completely.

Not fixed, deliberately. Folding at the loop entry independent of `scrub` would mutate the caller's
text on the one path where they explicitly asked for their characters left alone, and a
fold-then-restore pass is real machinery. Paying either price for 0.0011 — a number this harness
cannot distinguish from zero — would be buying complexity with nothing.

Worth keeping: **enumerate the class, then measure each member before fixing it.** The enumeration
was cheap and worth doing: it turned "where else might this bite?" from a guess into five lines of
table, and it showed that `\s` had quietly protected a third of the candidates all along. The
measurement then said the single genuine survivor was not worth touching. Finding a real bug and
declining to fix it is a result, not an omission.

## Result 54

**Running untell twice: worth 27% of the first pass, and one text in ten crosses a cliff.**

Nobody had measured what happens when a user feeds untell its own output, which is ordinary
behaviour. 10 HC3 texts, composite, 3 iterations, scored on the tier the loop optimises against.

| | original | 1 pass | 2 passes |
|---|---|---|---|
| lite P(AI) — the loop's target | 0.5747 | 0.4741 | **0.4466** |
| similarity to source | 1.0000 | 0.9847 | 0.9812 |
| tells | 8.70 | 7.10 | 8.20 |

The second pass adds **+0.0275**, about 27% of the first pass's +0.1006, and it is not noise: better
on 6 of 10 texts, **worse on none**. Extra meaning drift is 0.0036. So a second pass is mildly
worth it, with diminishing returns exactly as expected.

**The tells row is one text.** 7.10 -> 8.20 looks like the second pass degrading naturalness by 15%.
*(Superseded in part: the 1-in-10 crossing rate implied here is a small-sample artefact. Measured
at n=105 in [Result 59](free-ceiling-measured.md) it is 1 in 105.)*
Per text: unchanged on 9, and **+11 on one**. Quoting the mean here would have produced "a second
pass makes text read measurably worse", which is false for 90% of inputs — the same means-versus-
per-item error already recorded in [Result 45](free-ceiling-measured.md) (a rate hiding a count of
two) and [Result 48](free-ceiling-measured.md) (arms that improved the mean and lost the head-to-
head). Third time this session that the aggregate and the per-item record disagreed, and the third
time the per-item record was the true one.

**What happened to that one text.** Pass 1 scored 0 tells; pass 2 scored 11, all
`repeated_phrasing`. That category reports nothing below a 5%-of-tokens repetition share and the
full count above it — a threshold chosen from a false-positive curve, documented in its docstring.
Pass 1 sat under the bar with 6 repeated trigrams; pass 2 added three more and crossed it. So the
jump is a cliff in the metric, not an 11-fold collapse in quality — but the underlying fact is
real: **the rewriter added repetition to text it had already rewritten.**

The loop cannot currently prevent this. Its tells tie-break only applies among candidates within
`_TELLS_EPS` of the best detector score, so a candidate that scores clearly better on the detector
wins even if it repeats more — which is precisely the trade the second pass is making. Whether to
subordinate detector score to the repetition threshold is a real design question with a real cost,
and it needs its own measurement rather than a guess; recorded here as the open question it is.

Worth keeping: **"diminishing returns" and "safe to repeat" are different claims.** The aggregate
supports the first. Only the per-text record shows that one input in ten hits a discontinuity, and
a user re-running on a whole corpus would meet it about that often.

## Result 55

**An inconclusive experiment, and why it is inconclusive.**

[Result 54](free-ceiling-measured.md) left one question: should the loop refuse a candidate that
pushes repetition past the 5% bar the tell category thresholds on? A guard was built and measured
against an unguarded arm, paired on the seed, on the only population it can act on — texts that
START under the bar, which is 40% of HC3 AI texts (mean share 7.33%, 24 of 60 under 5%; human text
is 92% under, mean 1.36%).

Over 12 such texts, 2 passes, 3 iterations, 4 draws — **288 candidate draws — the guard blocked
nothing and neither arm crossed the bar.** Both arms finished identical: P(AI) 0.4250, 0.08 tells,
3.05% repetition.

That is not evidence the guard is unnecessary. **The harness does not reproduce the phenomenon.**
Run on the exact text that crossed in Result 54, it finishes at 3.60% with 0 tells and never comes
near the bar. The shipped loop, same text, same seeds:

| stage | words | repeated trigrams | share |
|---|---|---|---|
| original | 210 | 8 | 3.81% |
| pass 1 | 214 | 8 | 3.74% |
| pass 2 | 220 | **11** | **5.00%** |

So the phenomenon is real, and it is genuinely new repetition rather than an artefact of the share
being a ratio: the text got *longer* (214 -> 220 words) while gaining three repeats, which is the
opposite of what a shortening-inflates-the-share explanation predicts. That alternative was checked
and refuted rather than assumed away. And it lands on **exactly 5.00%** — the sharpest possible
illustration of the cliff, 11 reported tells against 0 for a text a hair under.

**The methodological error is the result worth keeping.** This harness was validated in
[Result 48](free-ceiling-measured.md) — its greedy arm reproduced the shipped loop 5 of 6 texts
byte-identical — and that validation was for *detector score*. Reusing it to measure *repetition
behaviour* assumed the validation transfers between properties. It does not: the shipped loop's
selection has tells, voice and ensemble-mean tie-breaks that the harness omits, and those are
precisely the terms that decide between candidates the detector rates equally, which is where
repetition differences live.

So the guard question stays open, and a valid test needs the shipped selection instrumented rather
than reimplemented. Nothing is shipped on this evidence. Two rules earned the hard way:

- **A harness is validated for a property, not in general.** "5 of 6 byte-identical" was a true
  statement about one measurement and I read it as a licence for another.
- **When a harness reports a clean zero, check it can produce a non-zero.** 288 draws and no blocks
  looked like a decisive negative until the known-positive case also came back clean. That is the
  same shape as [Result 44](free-ceiling-measured.md) — a check that cannot fire reads exactly like
  a check that found nothing.

## Result 56

**The repetition guard, tested properly: characterised, and still not shipped.**

[Result 55](free-ceiling-measured.md) failed because it reimplemented the selection loop. The fix
was to stop reimplementing: wrap the **rewriter object**, which is the one thing `untell_text` calls
to produce candidates, and let every tie-break, adoption guard and stall check stay exactly as
shipped. A vetoed draw returns the incumbent unchanged — a no-op candidate the loop already knows
how to handle.

**First run, and the guard still never fired.** Tracing every draw on the known-positive text
explained why:

```
pass 2 draws (incumbent% -> candidate%)
   3.35 -> 4.69      <- the damage, entirely below the bar
   4.69 -> 4.67 / 4.69 / 4.65 ...
final masked 4.65%      final restored 5.00%
```

Two separate problems, neither visible without the trace:

1. **The rise happens below the bar.** One draw adds 1.34 points in a single step and never
   crosses 5%. A guard that blocks bar-*crossings* has nothing to block.
2. **The loop selects on masked text; the metric scores restored text.** 4.65% against 5.00% on the
   same document. Across 60 HC3 texts, 41 lock at least one span; the restored-minus-masked
   difference is a mean of −0.055 points but reaches **+4.26**, and on 1 of those 41 it flips which
   side of the 5% bar the text falls on. The loop cannot see the quantity that gets reported.

Re-tested with the guard the trace implies — veto a draw that *raises* the share by more than
`slack` points, 12 eligible texts, 2 passes:

| guard | P(AI) | tells | over the bar | draws blocked |
|---|---|---|---|---|
| none | 0.4272 | 1.08 | 1/12 | — |
| slack 1.0 | 0.4272 | 1.08 | 1/12 | 0/216 |
| **slack 0.5** | 0.4295 | **0.08** | **0/12** | 2/216 |
| slack 0.0 | 0.4295 | 0.08 | 0/12 | 15/216 |

That looked like a bargain: two draws in 216, the cliff gone, +0.0023 detector. Replicated at n=30:

| guard | P(AI) | tells | over the bar | blocked |
|---|---|---|---|---|
| none | 0.4429 | 0.53 | **1/30** | — |
| slack 0.5 | 0.4504 | 0.13 | 0/30 | 7/540 |

*(Superseded: the 1-in-30 rate below is also a small-sample artefact — 1 in 105 at n=105,
[Result 59](free-ceiling-measured.md), which closes this question.)*

**Not shipped.** The cost is +0.0075 — still inside the ±0.013 noise floor, but positive in both
runs, so "free" is not a claim the data supports. The benefit is a 1-in-30 event, and the entire
tells improvement is that one text. Changing a default for every user to prevent a 3% event at a
cost that is merely too small to measure is not a trade this evidence justifies.

What it did buy is a precise question in place of a vague one. The mechanism is understood, the
efficient slack is 0.5, the cost is bounded at under 0.01, and the frequency is ~3%. Anyone
revisiting it starts from there instead of from "the rewriter sometimes adds repetition".

Two things worth keeping:

- **n=12 said +0.0023 and n=30 said +0.0075.** Both are inside the noise floor and the first looked
  three times better than the second. A cost estimate from a single small sample is a direction, not
  a magnitude — and the direction was consistent, which is the part that decided this.
- **The trace was worth more than either arm.** Both guard runs returned "blocked 0" and looked like
  clean negatives. Nine lines of per-draw logging showed the guard was well-formed and aimed at the
  wrong event, which no amount of re-running would have revealed.

## Result 57

**The tie-break was ranking on masked text — the same defect the detector score already fixed.**

Found by the trace in [Result 56](free-ceiling-measured.md), which showed the loop working with a
4.65% repetition share while the metric reported 5.00%. Chasing that discrepancy to its source: the
candidate tuple was built as

```python
cscore = score(candidate)                                  # restores first
valid.append((candidate, cscore, score_tells(candidate)))  # does not
```

Two quantities about the same candidate, one measured on what a reader sees and one on a string
full of sentinels. `score()` restores because of a fix already made and documented in this file —
*"the size of the misreport is not the argument for this fix; that the loop was RANKING on a
quantity nobody is judged on is."* The tells term never got the same treatment.

MEASURED over 120 HC3+RAID texts, 91 of which lock at least one span:

| | |
|---|---|
| texts where masked and restored tell counts disagree | **40 of 91 (44%)** |
| mean difference (restored − masked) | **+3.33 tells** |
| largest | **+27** |
| smallest | **+0** |

That last row is the important one. The minimum delta is zero, so **masking never invents a tell;
it only ever hides them.** The bias is one-directional and systematic, and it lands hardest on
texts that lock spans — the ones carrying citations and numbers, which is the academic register
this repo targets.

**It changes no output.** Measured end to end on 14 RAID texts that lock a span: P(AI) 0.2413 and
30.14 tells, identical before and after, because the tells term only breaks ties among candidates
already within `_TELLS_EPS` (0.02) of the best detector score, and that band rarely holds two
candidates whose tell counts differ.

Kept anyway, on the precedent quoted above. A ranking key that is systematically wrong in one
direction is worth correcting whether or not today's inputs happen to expose it — and the cost is
one string substitution and one regex pass per candidate, against a detector pass that already
dominates the loop.

Worth keeping: **an inconsistency found while investigating something else is still a finding.**
This was not on any list. It surfaced because Result 56 needed to explain a 0.35-point gap between
two numbers that should have been the same, and the explanation was two lines of code disagreeing
about which string they were describing.

## Result 58

**Every masked read in the loop, enumerated — and the rule that separates the safe from the wrong.**

[Result 57](free-ceiling-measured.md) found the tells tie-break ranking on masked text. Rather than
wait for the next one, an AST walk listed every call in `run.py` that takes a masked string as its
first argument. There are **13**:

| call | verdict |
|---|---|
| `score(masked)`, `score(candidate)` | safe — the closure restores internally |
| `similarity(masked, candidate)` ×3 | safe **by symmetry** — both sides masked |
| `meaning_preserved(masked, candidate)` | safe by symmetry |
| `rewrite(best_masked)` | correct — masking is the whole point of locking |
| `findall(candidate)`, `findall(masked)` | correct — the sentinel-integrity check must see sentinels |
| `restore(...)` ×3 | correct — these are the restore |
| `_voice_key(candidate)` | **already correct** — strips sentinels first, and its docstring says why |
| `score_sentences(best_masked)` | measured — see below |
| `score_tells(candidate)` | **was wrong**, fixed in Result 57 |

**The rule is symmetry.** A call that compares two masked strings is safe because the distortion
appears on both sides and cancels. A call that produces an *absolute number a user is judged on* is
not, because there is nothing to cancel against. Every one of the 13 sorts cleanly under that test,
and it is a cheaper thing to check than re-deriving each call from scratch.

`score_sentences` needed measuring rather than reasoning, because its output is a list of sentence
*strings* that must stay masked to match what the rewriter is handed — so "just restore it" is not
available. Measured over texts that lock a span, comparing which sentence *indices* get flagged on
the masked and restored views:

| per-sentence path | texts | flagged sets differ | mean Jaccard |
|---|---|---|---|
| stdlib | 61 | **0** | 1.000 |
| GPT-2 | 12 | **3 (25%)** | 0.833 |

The first row was written up as "no change needed" before the second finished, and it was wrong.
The stdlib per-sentence path is **AUROC 0.493** — a coin flip, documented as such in
`score_sentences`' own docstring — and two coin flips agreeing is not evidence of anything. On the
model-backed path, which is the one the README markets, masking moves the target a quarter of the
time.

**Fixed**: the loop now scores the *restored* sentences and returns the *masked* strings at the
flagged indices, pairing the two lists by position. When locking changes the sentence split the two
cannot be paired, and it falls back to the old behaviour rather than guessing an alignment — a
wrong pairing would target sentences nobody asked about, which is worse than the imprecision it
replaces.

Two things worth keeping:

- **`_voice_key` had already solved this, and said so in its docstring.** The information needed to
  avoid the tells bug was sitting in the same file, in a function two screens away, written by
  someone who had hit the same wall. Enumerating found the fix as well as the defect.
- **A rule that sorts every case is worth more than a fix.** "Restore before you measure" would
  have been wrong for `rewrite`, `findall` and the similarity calls. "Symmetry cancels; absolutes
  do not" sorts all 13 correctly and generalises past this file.
- **A clean result from a near-chance configuration is not a clean result.** The stdlib run said
  61 of 61 identical and would have closed the question. The path it measured cannot tell AI text
  from human text at the sentence level, so it also cannot tell masked from restored — the
  agreement was a property of the instrument, not of the thing being measured. The only reason the
  model-backed check ran at all is that it had been queued alongside it.

## Result 59

**The repetition guard, closed: the event happens once in 105 texts, and the guard hurts more than it helps.**

[Result 56](free-ceiling-measured.md) left this open with the honest note that its cost estimate
came from small samples. Run properly on both corpora, 2 passes each, paired on the seed:

| corpus | arm | P(AI) | over the bar | paired better / worse / tied | draws blocked |
|---|---|---|---|---|---|
| HC3 (n=60) | none | 0.4396 | **0/60** | — | — |
| HC3 (n=60) | slack 0.5 | 0.4460 | 0/60 | 1 / **5** / 54 | 12/1050 |
| RAID (n=45) | none | 0.3152 | **1/45** | — | — |
| RAID (n=45) | slack 0.5 | 0.3178 | 0/45 | 2 / 1 / 42 | 33/501 |

**One crossing in 105 texts.** The earlier rates — 1 in 10 from Result 54, 1 in 30 from Result 56 —
were small-sample noise, and the direction of that error was to make the problem look ten times
more common than it is.

The guard does prevent that one crossing. It also costs +0.0063 on HC3 and +0.0026 on RAID, and on
HC3 the paired record is **worse on 5 texts against better on 1** — the first time the cost has been
visible per-text rather than only in the mean. Blocking a draw removes a candidate the loop would
have adopted, and most of the time that candidate was fine.

**Not shipping it, and the question is now closed rather than open.** A guard that fires on 45 of
1551 draws to prevent a 1% event, while making 5 texts worse for every 1 it improves, is not a
trade that needs a bigger sample to settle.

Worth keeping: **the honest thing about Result 56 was saying the sample was small; the useful thing
was going back and fixing it.** Three estimates of the same quantity — 1/10, 1/30, 1/105 — each
from a bigger sample than the last, each smaller than the last. When successive samples move a rate
monotonically toward zero, the earlier ones were not measuring the rate, they were measuring
whether the rare thing happened to be in the sample.


## Result 60

**Invisible characters: 209 words become 889, and the two surfaces need opposite fixes.**

An extended invariance battery — twelve transforms rather than the six in
[Result 51](free-ceiling-measured.md) — against the scoring path and the tell catalogue. Seven of
the twelve are zero-width or invisible characters inserted between every character of every word,
which is what a soft hyphen from a justified PDF, a web paste, or a steganographic watermark looks
like to a tokeniser.

All seven behave identically, and the effect is enormous. On one 209-word HC3 answer:

| | words | tells | tells/100w | top category |
|---|---|---|---|---|
| plain | 209 | 23 | 11.0 | `repeated_phrasing` 21 |
| zero-width injected | **889** | **436** | 49.0 | `repeated_phrasing` **433** |
| scrubbed first | 209 | 23 | 11.0 | `repeated_phrasing` 21 |

Words shatter into single-character fragments, and single characters repeat constantly, so trigram
repetition explodes. Across 6 texts the detector score moved by a mean of **0.2176** and the flagged
verdict flipped on **6 of 6**.

**The two surfaces take opposite fixes, and that is the point.**

- `score_tells` **strips them**. A tell count describes the *writing*, and "889 words" is not a
  surprising description of a 209-word text, it is a false one. Everything else in that result —
  the rate, the categories, humanness — is derived from the word count and inherits the error.
- `score_text` **warns instead**. That number describes what a *detector* would say about the exact
  string the user is about to submit, and a real detector sees those characters too. Scrubbing them
  would report a score for a document that does not exist. The warning carries the measured 0.2176
  and tells the reader to strip and re-score if the characters came from a PDF rather than from
  them.

`scrub_hidden` does the stripping, rather than a narrower local helper: it already distinguishes an
orphan zero-width joiner from one holding an emoji sequence together, and writing a second
nearly-identical stripper is the mistake Result 51 recorded.

Two things worth keeping:

- **A soft hyphen is not an attack.** Six of the seven characters here read as adversarial, and one
  is in every justified PDF in existence. Had the battery only contained the exotic ones, the fix
  would plausibly have been gated behind an opt-in flag for "hostile input" and would have missed
  the common case entirely.
- **"Which question does this number answer?" decided both fixes.** The same input, the same
  characters, two surfaces, opposite correct answers. Neither follows from a general principle
  about invisible characters; both follow immediately from asking what the number is *for*.

## Result 61

**Three failed attempts to measure one fix, and what each failure was.**

The sentence-targeting fix from [Result 58](free-ceiling-measured.md) has a verified *mechanism* —
masking moves the flagged sentence set on 25% of texts on the model-backed path — and no
demonstrated *benefit*. Three attempts, each broken in a different way, each caught:

1. **Benchmarked with the wrong rewriter.** Ran before/after with `composite`, got byte-identical
   output, and nearly wrote it up as "no effect". `flagged_sentences` is read only by
   `untell/rewriter/prompts.py` and `targeted.py` — the composite path never looks at it, so the
   benchmark was measuring a code path the fix cannot reach.
2. **A silent no-op edit.** The fix-up replaced `get_rewriter('composite')` with single quotes
   against a file containing double quotes. No assertion, so the substitution did nothing, the
   harness ran unchanged, and it reported the *same ten numbers to three decimals* as the previous
   run. Two different rewriters cannot agree on ten floats — that implausibility is the only reason
   it was caught.
3. **An arm killed at 1 of 10.** The corrected run's "after" arm died to a timeout while the
   "before" arm completed, leaving a single-arm comparison that looks like a result.

The fix is kept anyway, on the same grounds as [Result 57](free-ceiling-measured.md): the loop
should rank on the text a reader sees. But the code comment now says the benefit is unmeasured
rather than implying it was measured at zero, because those are very different claims.

Three things worth keeping:

- **Every string replacement in a throwaway script needs an assertion.** The no-op edit is the
  fourth time this session a silent substitution produced a confident wrong number. A one-line
  `assert old in text` converts it from a wrong result into a crash.
- **Implausible agreement is a bug report.** Identical means could be a real null result; identical
  *per-text values to three decimals across two different implementations* cannot. The habit of
  printing per-item values rather than only aggregates is what made it visible — the same habit
  that caught Results 45, 48 and 54.
- **Know which code path consumes the thing you changed** before benchmarking it. One grep for
  `flagged_sentences` would have shown that the default rewriter ignores it, and would have saved
  two of the three runs.
- **Never benchmark uncommitted work with a harness that reverts files.** A `git checkout` inside a
  killable background job is a destructive operation with no undo, and the window where the tree is
  reverted is exactly the window where something else can read it. Commit first and benchmark the
  committed state, or work from copies outside the tree.

## Result 62

**Zero-width injection clears AI text on 14 of 20 texts — the mirror image of Result 51.**

[Result 60](free-ceiling-measured.md) fixed the tell count against invisible characters and left the
detector score warning rather than stripping, on the grounds that a real detector sees those
characters too. That was the right call, but it was made without measuring **which direction** the
distortion runs. Measured on 20 pairs per corpus, a zero-width space between every character:

| corpus | text | humanness | P(AI) | verdict flips |
|---|---|---|---|---|
| HC3 | **AI** | **+9.71** | **−0.1943** | **14/20** |
| HC3 | human | +2.99 | −0.0600 | 3/20 |
| RAID | AI | +1.02 | −0.0207 | 8/20 |
| RAID | human | −1.83 | +0.0363 | 4/20 |

On HC3 this is a working evasion: AI text loses 0.19 of detector score and **its verdict flips to
clean on 14 of 20 texts**, while humanness rises nearly 10 points. The effect on human text is a
third of that.

**This is the exact opposite direction from the non-breaking space.** U+00A0 produced false
accusations of humans (Result 51: 5/10 → 9/10 flagged, and AI text unaffected). U+200B produces
false clearances of AI. Same family of character, same one-keystroke edit, opposite victim — which
is why "invisible characters distort scoring" is not a finding one can act on, and the direction is.

Two changes, neither of them stripping:

- The caveat now **names the direction and the remedy**: that a clean result on such input is not
  evidence, and that `untell scrub` fixes it. A warning saying only "this affects the score" leaves
  a reader with a cleared verdict and no reason to distrust it.
- `humanness` **surfaces it**. It returns a bare float, so every caveat `score_text` produced was
  being discarded — and this is the one a caller cannot recover any other way, on the surface where
  the drift is largest.

Worth keeping: **a symmetric-sounding defect usually is not symmetric, and the asymmetry is the
actionable part.** Result 51 and this one are the same mechanism at the same layer, and one costs
innocent writers an accusation while the other lets prepared text through. Neither is visible in a
mean taken over both halves of a corpus; both are obvious the moment the halves are split.

## Result 63

**Homoglyphs are the strongest evasion measured, and one earlier fix already covered half of it.**

Continuing the class from [Result 62](free-ceiling-measured.md): if invisible characters clear AI
text, what do *visible* lookalikes do? Mapping `a e o p c` to their Cyrillic counterparts — a
substitution no reader can see — over 15 pairs per corpus:

| corpus | text | P(AI) | tells | verdict flips |
|---|---|---|---|---|
| HC3 | **AI** | **−0.2884** | **+0.00** | **13/15** |
| HC3 | human | −0.2407 | +0.00 | 4/15 |
| RAID | AI | −0.0916 | +0.00 | 2/15 |
| RAID | human | −0.0792 | +0.00 | 1/15 |

Stronger than zero-width injection (−0.1943, 14/20) on the score, and it flips 13 of 15 HC3 AI
verdicts to clean.

**The tells column is the interesting one.** It is `+0.00` everywhere — the tell catalogue is
completely immune, because [Result 60](free-ceiling-measured.md) routed it through `scrub_hidden`,
and scrubbing maps confusables back to ASCII. That fix was written for soft hyphens and zero-width
carriers; homoglyph immunity came free, and was noticed only because this measurement printed a
column nobody expected to be interesting.

`score_text` still warns rather than scrubs, for the reason [Result 60](free-ceiling-measured.md)
gives, so it needed a detector of its own. The signature is precise: **a word containing both Latin
and Cyrillic/Greek letters**. Legitimate multilingual text does not mix scripts *inside* a word —
quoting Russian puts whole Russian words in. Verified: fires on `r{U+0435}sults`, silent on plain
English, silent on `The sign said привет which means hello`.

**One vector in this family is clean.** NFD versus NFC — decomposed and precomposed accents, which
render identically and which macOS produces routinely — moves nothing at all: P(AI) 0.6949 either
way on an accent-heavy paragraph, identical tell count, identical word count. Worth stating
explicitly, because "Unicode normalisation form" sounds exactly like the previous three findings
and is not one of them. Accented text is also rare in these corpora: 0 of 30 HC3 AI texts and 1 of
30 RAID.

Two things worth keeping:

- **A fix aimed at one mechanism can cover a neighbouring one, and you will only know if you
  measure the neighbour.** Nothing about "strip zero-width carriers" advertises "immune to Cyrillic
  substitution". The column that proved it was included out of habit, not design.
- **Detection beats normalisation when the two surfaces answer different questions.** Scrubbing
  would have been the easy fix for both surfaces and the wrong one for `score_text`, which must
  report what a detector sees. A narrow, high-precision *detector* preserved the honest number and
  still told the user their clean verdict was worthless.

## Result 64

**A concurrent finding that could have invalidated nine numbers, checked rather than assumed.**

Another session found that `detector_audit --pairs` was scoring RAID **as stored**: its human
documents are hard-wrapped scrapes at 84.52 single newlines per 1,000 words, its machine
continuations unwrapped at 2.79, and **newline density alone separates the two halves at AUROC
1.0000**. A detector that reads nothing and counts line breaks is perfect on that corpus.

Every RAID figure in this log was produced from `load_pairs` text as-supplied, so the obvious
question is how many of them were measuring layout. Re-run with the same `collapse_layout` applied
to both halves, 100 pairs:

| corpus | | human | AI | gap |
|---|---|---|---|---|
| HC3 | as supplied | 0.642 | 7.320 | +6.678 |
| HC3 | collapsed | 0.642 | 7.320 | **identical** |
| RAID | as supplied | 1.153 | 12.460 | +11.308 |
| RAID | collapsed | 1.161 | 12.457 | +11.296 |

**The tell metric is not affected**: HC3 byte-identical, RAID moving by 0.012 on a gap of 11.3. The
direction result in [Result 45](free-ceiling-measured.md) stands, and so do the RAID rows in the
evasion results, which are within-text comparisons where layout is held constant on both sides
anyway.

Independently confirmed: the session that found the layout bias reached the same conclusion for the
tell catalogue from the other direction (commit `cbbf78f`, "the catalogue AUROC had no layout bias")
— and caught a separate staleness of 0.32 in the published figure while doing so.

Worth keeping: **a confound in a shared corpus is everyone's problem, and "my measurement probably
doesn't depend on that" is a guess until it is a measurement.** The check cost one script and five
minutes. Had it come out the other way, nine published numbers would have needed retracting — and
the reason to run it was not doubt about this metric but the fact that somebody had just proved the
corpus lies about *something*.

## Result 65

**Where each evasion lands, checked surface by surface — and the one that mattered most was silent.**

[Results 62 and 63](free-ceiling-measured.md) measured two evasions that flip an AI verdict to
clean. This traces both through every surface that reports a verdict.

| surface | zero-width | homoglyph | state |
|---|---|---|---|
| rewrite loop, default | removed | removed | safe — `scrub` runs by default |
| rewrite loop, `scrub=False` | **701 survive** | **262 survive** | by request; the caller asked |
| `score_tells` | immune (strips) | immune (strips) | Result 60 |
| `score_text` | warns | warns | Results 62, 63 |
| `humanness` | warns | via `score_text` | Result 62 |
| **`verify`** | **silent** | **silent** | **fixed here** |
| `/tells` | immune | immune | no caveat needed |

`verify` was the gap, and it is the worst one to have. It is the surface that produces a **pass/fail
verdict and a process exit code** — the thing a user consults to decide whether their text is clean,
and the thing a script branches on. It reported PASS on injected text in silence while `score_text`
warned about the identical string.

Both caveats now attach to the result dict, print **after** the verdict rather than before it — a
caveat above the answer gets skimmed past, and a PASS obtained this way is precisely the one to
distrust — and are documented in the REST `/verify` schema, which is all a machine client has.

`/tells` needs no caveat and does not get one: `score_tells` strips, so its numbers are already
correct on injected input. Adding a warning there would be noise about a problem that no longer
exists on that surface.

Worth keeping: **audit by surface, not by mechanism.** Both evasions were understood, measured and
fixed two results ago; the question "which surfaces report a verdict, and does each one carry the
caveat?" is a different question from "is the mechanism handled", and only the second had been
answered. The gap was not in the hard part.

## Result 66

**`--no-scrub` shipped 701 evasion characters in the output and said nothing.**

[Result 65](free-ceiling-measured.md) noted that the rewrite loop is safe by default and that
`scrub=False` lets both evasions through "by request". That was the correct description and the
wrong place to stop: the caller asked to keep their characters in the *input*, and what they get
back is an *output* carrying 701 zero-width characters — with a result dict that had no `warning`
key at all, and a CLI that printed nothing.

Those characters flip an AI verdict to clean on 14 of 20 texts. A caller shipping that output is
shipping an evasion payload, possibly without knowing it exists.

Now reported and still not removed — removing it would be ignoring the flag. The warning fires only
when a payload is actually present *and* survives, so `--no-scrub` on clean text stays silent.

**Two bugs found on the way, both mine, both instructive:**

The wiring landed inside the `stopped=` argument, producing `stopped=result.get("stopped",
"unknown", warning=...)`. The CLI did not crash. It printed a perfectly ordinary plain-text result,
because the rich renderer was wrapped in `except Exception` — so a `TypeError` from a wrong argument
list was indistinguishable from `rich` not being installed. The only symptom was that the output
looked *slightly different from last time*, and the only reason it was caught is that the previous
run's format was still on screen.

That fallback is now `except ImportError`, which is the thing it was written for. A missing optional
dependency should degrade quietly; a bug in the renderer should be loud.

Worth keeping: **a broad `except` around a fallback path converts programming errors into feature
detection.** The handler was correct about what it wanted to catch and wrong about how to say it,
and the cost was that it hid a live bug for as long as nobody compared two runs side by side.

## Result 67

**My fix was obsolete within hours, and keeping its numbers would have been the exact failure this log exists to catch.**

[Results 62 and 63](free-ceiling-measured.md) measured two working evasions and added caveats to
`score_text`, `humanness` and `verify` carrying the numbers: zero-width injection moved AI text
−0.1943 and flipped 14 of 20 verdicts to clean; homoglyph substitution −0.2884 and 13 of 15.

A concurrent session then fixed the **detector layer** — normalising these characters before
scoring (`2e41f57`, `468dcbf`). Re-measured after their commits:

| tier | vector | mean \|Δ P(AI)\| | verdict flips |
|---|---|---|---|
| lite | zero-width | **0.0000** | 0/10 |
| lite | homoglyph | **0.0000** | 0/10 |
| lite | soft hyphen | **0.0000** | 0/10 |
| full | all three | **0.0000** | 0/10 |

Both evasions are dead at both tiers. Which makes every caveat I had just shipped a **false
statement**: they told the reader the score is affected and a clean result is not evidence, and
neither is true any more.

Rewritten to what remains true — the characters are still in the user's text, they will travel with
it, and another tool may not normalise them. `untell scrub` is still the remedy, for a different
reason than the one originally given. The tests that asserted `"14 of 20"` and `"13 of 15"` now
assert the current claim instead.

The `scrub=False` warning from [Result 66](free-ceiling-measured.md) is unaffected and stays exactly
as written: it is about the payload surviving into the *output*, which no detector fix changes.

Three things worth keeping:

- **A fix at a lower layer can obsolete a fix at a higher one, and nothing announces it.** Both
  changes were correct when written. The only reason the staleness was caught within the hour is
  that the other session's commit titles named the characters I had been working on, so I
  re-measured instead of assuming my numbers still held.
- **A caveat carrying a measured number has an expiry date the number does not advertise.** Putting
  "−0.1943, 14 of 20" in user-facing text made the warning concrete and useful, and it also meant
  the warning could go stale in a way a vaguer one could not. That trade is still worth making —
  but only if something re-checks.
- **Two sessions converged on one problem from opposite ends and both fixes were needed.** Theirs
  removed the vulnerability; mine tells the user their document still contains the characters.
  Neither subsumes the other, and the overlap was in the *justification*, not the behaviour.

**And they caught a hollow test of mine.** `test_markup_survives_a_real_rewrite`, written earlier in
this session to pin the LaTeX defect row, called `untell_text` without `rewriter="composite"`. With
no API key configured — which is CI — the loop returns `{"error": ..., "final": <input>}` and every
must-survive token "survived" because nothing had touched it. Five seeds of nothing, passing
cleanly. They added an assertion on `rewrites` so the test fails instead of going quiet.

That is the same defect this log has recorded four times in other people's code and twice in my
own harnesses — a check that cannot fire reads exactly like a check that found nothing — and I
wrote it into a test whose entire purpose was anti-vacuity. Ignoring the `error` key was the
specific mechanism, which is the third time this session that key has been the thing that mattered.
