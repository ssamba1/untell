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

**Do not compare the MAX row here against Result 17's.** That table was 12 texts and this one is
20 different ones; the per-detector *ranking* is what replicates, not the absolute level. The
like-for-like end-to-end figure is Result 20's, on a fixed n = 40 with repeats.

---

## Result 21 — reordering, and two structural moves measured then declined

Every transform in `rewriter/structural.py` was a **local** edit: a word swap, a split, a merge, a
deletion. None changed the order in which information arrives, which is what a curvature detector
reads over a long span — and `fast_detectgpt` is the wall.

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
| `best_of=1`, **×3 repeats** | 0.7737 | **0.3469 ± 0.0193** | 0.95 → **0.408** | 0.9816 | 0.9212 |
| `best_of=3` (**shipped**), ×1 | 0.7737 | **0.3017** | 0.95 → **0.325** | 0.9823 | 0.9595 |

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

### Which number to quote

The **`best_of=1 ×3`** figure leads in the ROADMAP, because the earlier entries in that series used
`best_of=1` and a comparison has to be like for like. The **`best_of=3`** figure is what a user
actually gets, and it is better — but it is a single run, and this document's own rule since
Results 13/14 is **≥3 repeats before a number is quoted**. It is recorded as a single run and
labelled as one rather than promoted to the headline.

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

### Why this is not a one-line fix

`threshold` does two different jobs and they want opposite values:

- **The verdict.** "Is this text flagged?" — wants ~0.45, or it slanders human writing.
- **The loop's stopping condition.** "Rewrite until the score is below this" — wants a LOW value,
  because stopping early is under-rewriting. Raising it to 0.45 would make the loop quit sooner and
  weaken every humanisation run on the lite tier.

The two are the same number today, and the full tier — whose score distribution is different —
shares it as well. Fixing this properly means separating the reporting threshold from the loop
target, and calibrating the reporting one per tier. That is a design change, not a constant edit,
and it is recorded here with the measurement it needs rather than guessed at.

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
