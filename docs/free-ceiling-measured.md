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

> ## ⚠️ The composite numbers here no longer reproduce (re-measured 2026-08-11)
>
> Running the command this document gives for Result 11 —
> `UNTELL_DISABLE_MAGE=1 untell-ceiling --dataset hc3 --n 6 --tier full --best-of 3 --max-iters 5
> --rewriter composite`:
>
> | | post | flagged | `hc3_roberta` |
> |---|---|---|---|
> | recorded here | 0.860 | 1.00 | 0.810 |
> | re-measured | **0.9995** | 1.00 | **0.9992** |
>
> **REPLICATED at `--repeats 3`** (the standard this document sets for a quotable number):
>
> ```
> post mean max P(AI) 0.9994    per-run [0.9995, 0.9993, 0.9993]    stdev 0.0001
> rewrote 18/18                 similarity 0.9848 mean / 0.9523 worst
> ```
>
> A single run was not the problem — the spread is 0.0001. The recorded 0.860 does not reproduce.
>
> **And the per-detector split says why, which the aggregate hides.** Same run, before → after:
>
> | detector | before | after | |
> |---|---|---|---|
> | `roberta_openai` | 0.9986 | **0.5847** | moves 0.41 |
> | `fast_detectgpt` | 0.6563 | **0.4534** | moves |
> | `perplexity_burstiness` | 0.6316 | **0.5584** | moves |
> | `hc3_roberta` | 0.9992 | **0.9992** | **does not move at all** |
>
> So the rewriter is working, and working well: it rewrote every sample, cut the strongest mobile
> detector by 0.41, and held meaning at 0.9848. The ceiling is set by **one immobile detector**.
> `max` reports 0.9994 because `hc3_roberta` sits at 0.9992 and does not shift — which is exactly
> what Results 1–2 originally called the content wall. The old 0.810 figure had it *moving*; it no
> longer does, and the shortcut-closing commits below are the likeliest reason.
>
> **That immobility is HOME-FIELD ADVANTAGE, not a property of the detector.** The sentence above
> first read "will not shift by any amount of meaning-preserving rewriting", which is true on HC3
> and false in general — corrected here rather than quietly reworded. Measured across three corpora
> × two rewriters, mean `hc3_roberta` before → after:
>
> | corpus | `composite` | `structural` |
> |---|---|---|
> | **HC3** (its own training corpus) | 0.9992 → 0.9992 | 0.9992 → 0.9992 |
> | **RAID** | 0.5014 → **0.2546** (−0.247) | 0.5014 → **0.3296** (−0.172) |
> | **MAGE** | 0/3 rewrites — inconclusive | 1/4 rewrites — inconclusive |
>
> The split is by CORPUS, not by rewriter: both rewriters agree within each corpus. `hc3_roberta`
> is immobile when it starts at its ceiling on the distribution it was trained on, and moves
> substantially when it does not. MAGE settles nothing — its texts start near the FLOOR (0.015),
> so there is nothing to reduce, and the rewriter declined to change most of them anyway.
>
> What this does not support: any transfer of the effect SIZES between corpora, and any claim about
> `hc3_roberta` under the composite rewriter on MAGE, where 0 of 3 completed samples were rewritten
> at all. Direction and mobility only.
>
> **Why the MAGE row settles nothing is sharper than "it starts near the floor"** (measured later,
> 2026-08-12). `load_samples` filters at `> 30` words and MAGE is a short-form corpus, so what comes
> back is far below the thresholds untell itself enforces:
>
> | corpus | median words | under 60 words |
> |---|---|---|
> | HC3 | 207 | 0% |
> | RAID | 281 | 0% |
> | MAGE | 37 | **90%** |
>
> `score._MIN_WORDS_FOR_A_VERDICT` is 40 and `tells._MIN_WORDS_FOR_REPETITION` is 60, so on most of
> these documents untell would decline to give a reliable verdict at all and the two strongest tell
> categories cannot fire. The same shape shows in the tell totals through a full loop over 16
> documents each: 169 → 149 on HC3, 377 → 298 on RAID, **36 → 35** on MAGE — not a coverage hole in
> the loop, which changed 9 of those 16 and moved the detector 0.450 → 0.381, but a corpus with
> almost nothing in it to move.
>
> `load_samples` now warns when a quarter or more of what it returns is under the verdict minimum.
> Anyone re-running a MAGE comparison should pass a `min_words` floor — `load_pairs` already
> defaults to 60 — or the number will be dominated by length rather than by whatever was being
> measured.
>
> The rewriter is not the cause — it rewrote 6 of 6, and the opener-dose change made the same day
> was ruled out directly (0.9996 current against 0.9994 old). The detectors are **pinned** on this
> corpus: `mage` 1.0000 on 6/6, `hc3_roberta` 0.9992–0.9993 on 6/6, `roberta_openai` ≥0.999 on 5/6.
> Three of five saturate, so `max` cannot move for *any* rewriter, with or without `mage`.
>
> Ten commits have touched `untell/detectors/` since these figures were taken, several of them
> closing scoring shortcuts — `hc3_roberta` read punctuation spacing as authorship, and collapsing
> newlines still moves `roberta_openai` by up to 0.59 on its own. The most likely reading is that
> these numbers were true when taken and measured evasion of artifacts that have since been removed.
>
> **Re-measured 2026-08-12, and the pinning holds.** Four HC3 documents through the full loop
> (`composite`, `max_iters=2`, `best_of=3`, seed 7), scoring the loop's own before/after:
>
> | run | mean gain in max P(AI) |
> |---|---|
> | full tier, `mage` enabled | **+0.0000** on 4 of 4 |
> | full tier, `UNTELL_DISABLE_MAGE=1` | **+0.0000** on 3 of 4, +0.0002 on the fourth |
>
> So disabling `mage` changes nothing here, which is the sentence above stated as a measurement
> rather than an inference: the other saturating members hold `max` at the ceiling on their own.
> The rewriter was working in every run — tells fell 4→0, 1→0, 1→0 on three of the four documents —
> and `max` did not move, which is the distinction this section exists to draw.
>
> The README's 0.86 → 0.15 table is not in tension with this. It names its corpus (`untell-ceiling`'s
> three built-in paragraphs, mean 36 words) and its command disables `mage`; HC3 is the harder
> corpus, and the difference between them is the point of the caveat under that table.
>
> That does not weaken this document's *conclusions* — "some real AI text is unclearable by
> meaning-preserving rewriting" is, if anything, stronger at 0.9995 than at 0.860. It does mean
> **every composite figure below is a historical record, not a current measurement.** The `neural`
> rows have not been re-run at all.
>
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

## Result 68

**Every measured number in a user-facing string, re-checked: five of six were wrong.**

[Result 67](free-ceiling-measured.md) found one caveat gone stale within an hour. That is not a
one-off risk — it is a property of putting measurements in strings — so an AST walk pulled every
string in `untell/` carrying a number and a word like "measured", "flagged" or "human". 84 hits,
mostly docstrings; six are text a user actually reads. Each was re-measured:

| claim | as written | re-measured | verdict |
|---|---|---|---|
| invisible-char caveat | −0.1943, flips 14/20 | 0.0000, 0/10 | **stale** (Result 67) |
| homoglyph caveat | −0.2884, flips 13/15 | 0.0000, 0/10 | **stale** (Result 67) |
| REST `/verify` schema | "both flip an AI verdict to clean" | no longer true | **stale, missed in 67** |
| `run.py` comments ×2 | "flip … on 14 of 20 texts" | past tense now | **stale tense** |
| stdlib lite: "flags 69% of HUMAN text" | 69% | **64% at 0.30, 30% flagged** | **misleading** |
| tells caveat corpus means | 0.551 / 7.335 | **0.642 / 7.320** | **stale** |
| per-sentence AUROC | 0.493 | **0.501** | **stands** — both are a coin flip |

**The stdlib one is the interesting failure.** "It flags 69% of HUMAN text" is not simply out of
date — it conflates two thresholds. 64% of human text scores above the **0.30 loop threshold**, but
`flagged` is decided by the **0.45 verdict threshold**, where the figure is 30%. A reader maps the
word "flags" onto the `flagged` field and takes away a number more than twice the truth. This is
the same threshold conflation [Result 43](free-ceiling-measured.md) corrected in the docs — and the
warning string was never updated with them. Now states both, and says which decides `flagged`.

**A test caught the corpus-means change and that was the system working.** `test_the_caveat_points_
at_the_count_not_the_rate` pins `0.551` and `7.335` literally, so correcting them broke it. The
right response was to update it consciously, not to loosen it into "quotes two numbers" — a
structural assertion survives any drift, including drift into being wrong. The docstring now records
why the exact pin is deliberate.

Worth keeping: **a measured number in a string is a claim with no owner.** The doc log gets
re-derived, the README gets audited, tests pin constants — but a sentence inside a warning is read
by users and by nothing else. Six of them, and the only one still true was the one whose value was
"indistinguishable from chance", which is the one kind of claim that cannot drift.

## Result 69

**The changelog's historical exemption does not extend to `[Unreleased]`.**

`untell-audit` deliberately exempts the changelog: "a changelog entry records what was true when it
was written, and fixing those to match today's code would destroy the record rather than repair
anything." That reasoning is correct, and it stops being correct one heading up.

[Result 68](free-ceiling-measured.md) re-derived the tell-rate corpus means from 0.551/7.335 to
0.642/7.320 and corrected the caveat in the code. The `[Unreleased]` changelog entry *describing
that very caveat* still carried the old pair — and `[Unreleased]` is not history. It is a draft of
the next release notes. Shipping a superseded number there is shipping a wrong claim, not preserving
a historical one.

Corrected, and now guarded. `check_unreleased_changelog_is_current` reads the numbers **out of the
shipped caveat itself** rather than hard-coding them a second time — two copies of a number is how
they drift apart in the first place — and requires the `[Unreleased]` section to agree. Verified by
reverting the entry to the stale pair: the audit fails and names both numbers.

Scoped narrowly on purpose. It checks only what the entry attributes to a constant or string in the
code; prose claims are left to `check_attribution`, which already requires them to name a source.
Released sections are untouched, and the docstring says why.

Worth keeping: **an exemption is a rule, and rules have boundaries nobody writes down.** "The
changelog is history" was true of every line anyone had looked at when the exemption was written.
The one section where it is false is the section that is about to become the release notes — the
highest-visibility text in the repository, and the only part of that file a user is likely to read.

## Result 70

**A docstring described the fix; the fix covered half the paths.**

`untell/config.py` documents the hazard precisely: *"the SAME key answers `0.30` (float) from a file
and `"0.30"` (str) from the environment, so `get("threshold", 0.30) < 0.5` raises TypeError only
when the env var happens to be set — the worst kind of conditional failure."* `_coerce` exists to
prevent it, and it works.

It is invoked as `_coerce(val, default, key) if default is not None else val`. So the promise holds
for `get(key, default)` and not for `get(key)`. Probed with a real `untell.yaml`:

| call | from file | from env | |
|---|---|---|---|
| `get("threshold", 0.30)` | 0.11 float | 0.99 **float** | correct |
| `get("threshold")` | 0.11 float | **`"0.99"` str** | the documented failure, uncovered |

Only one in-repo caller passes a default, so the gap is latent rather than live — but the docstring
states the invariant without qualification, and a latent contradiction between a documented promise
and the code is the thing this repo treats as a defect in its own right.

Fixed by falling back to the type of the **config-file** value when no default is given. Where
neither exists there is nothing to infer from, and the raw string is returned — a real limit, now
stated and pinned by a test, because guessing would make `UNTELL_X=1` an int while `UNTELL_X=1.0`
is a float.

**The tests I wrote for it failed on their first run**, calling `config.load.cache_clear()`. `load`
is not cached; the attribute never existed. Three tests, one wrong assumption, caught immediately
because they were run — the same class as the `'composite'`-vs-`"composite"` no-op in Result 61,
and the reason a test is worth more the first time it fails than the tenth time it passes.

Worth keeping: **read the qualifier on the code, not the claim in the docstring.** The docstring was
written by someone who understood the bug exactly and fixed the path they were looking at. The
sentence generalises; the code does not; and nothing flags the difference because both are correct
about what they describe.

## Result 71

**Markdown structure survives the loop — except the one break that means "do not join these".**

`layout.py` exists because rewriters reassemble text with `" ".join(sentences)` and flatten
documents. Eight markdown edge cases through the full loop, checking line counts and structural
markers:

| case | lines | markers | |
|---|---|---|---|
| nested list, task list, setext heading | preserved | preserved | ok |
| HTML block, footnote, indented code | preserved | preserved | ok |
| YAML front matter | preserved | preserved | ok |
| fenced code | preserved | **byte-identical** | ok |
| **hard break** (two trailing spaces) | **2 → 1** | — | **broken** |

Seven of eight clean, including a full document with headings, both list kinds, a blockquote, a
table and a code fence — all structure intact, code block byte-identical.

The eighth: `apply_per_block` gathers consecutive plain lines into one block "so a soft-wrapped
paragraph is transformed as a unit", which is right for a soft wrap and wrong for a hard break.
The author asked for a rendered line break; the merge transform joined straight across it and
returned one sentence.

**It survived when nothing else changed**, which is what made it invisible — the loss appears only
once the merge transform fires, so any spot-check on unmodified text says the layout is fine.

Fixed in two parts, and the second was only found by re-measuring the first:

1. A hard break now ends a block. That alone took the line count from 2→1 back to 2→2 — and left
   the output rendering as a soft wrap anyway, because
2. every transform strips trailing whitespace, so the marker was gone. The marker is now held
   aside and re-attached around the transform.

Ending the block costs the transform some context: the following line is rewritten on its own. That
is the right trade — the author asked for a boundary, and this module's job is to honour one rather
than optimise across it.

Worth keeping: **"the line count is right" is not "the layout is right".** The first fix passed the
obvious check and produced output that renders differently from its input. Only asking what the
*characters* were, rather than how many lines there were, showed it.

## Result 72

**A meaning-inverting rewrite that passed all five gates, and the one that still does.**

The repo's central differentiator is five meaning gates. Nobody had tried to defeat them. Seven
adversarial edits to one clinical sentence, with NLI and the role parser both available:

| edit | contradiction | entailment | roles | verdict |
|---|---|---|---|---|
| change the number | — | — | — | blocked (numerals) |
| drop the hedge | — | — | — | blocked (certainty) |
| **negate the finding** | 0.066 | 0.929 | False | **PASSED** |
| **swap the comparison arms** | 0.004 | 0.991 | False | **PASSED** |
| **invert who did what** | 0.004 | 0.991 | False | **PASSED** |
| faithful paraphrase | 0.010 | 0.963 | False | passed (correct) |

**The negation result did not generalise, and saying so is the finding.** Isolating it showed the
trailing hedge was responsible — contradiction fell 0.99 → 0.19 the moment "though the effect may
not hold" was present. Four fresh hedge+negation pairs were then built to confirm: **all four stayed
blocked** (0.604–0.998). So "a hedge masks a negation" is not true as a general claim, and one
example would have published it.

**The role swap is real and fixable.** `_triples` falls back to a prepositional object only when
there is no direct object. "The drug reduced mortality compared with placebo" has one, so `placebo`
was never captured and swapping the arms left every triple identical. In clinical and academic
prose "A compared with B" is the commonest structure whose inversion changes the finding, and that
register is the one this repo targets.

Comparison prepositions now produce a triple of their own, collected **per sentence** rather than
per verb — "compared with" hangs off the participle and "than" off the adjective, so a per-verb scan
finds neither. Rule 1 then sees both entities in one triple and the exchange fires.

| | before | after |
|---|---|---|
| comparison-arm swaps caught | 0 of 3 | **3 of 3** |
| natural-phrasing swaps | — | 4 of 5 |
| false alarms on faithful rewrites | 0 of 5 | **0 of 5** |

The fifth case is a parser limit, not a logic gap: spaCy yields a `than` triple for
"Ibuprofen performed better than aspirin" and not for the same sentence with the arms exchanged, so
detection depends on which side is the source. Pinned as a test that will fail if a spaCy upgrade
fixes it, rather than worked around — forcing the triple would misfire on genuine rephrasing.

Worth keeping: **the gate that exists for a failure mode is not evidence the failure mode is
covered.** `roles.py` was written to catch exactly this class, catches the textbook version
("The dog bit the man"), and missed the form the target register actually uses.

## Result 73

**A sixth gate, and it cost nothing because the rewriter never touches polarity.**

[Result 72](free-ceiling-measured.md) left one attack unfixed: negating the main clause of a 24-word
clinical sentence scored contradiction 0.066 and entailment 0.929 and passed every gate. A polarity
flip is the cheapest possible meaning inversion, so the question was whether a mechanical check
could close it without vetoing real work.

**It can, and the cost is zero.** Negation-marker counts across real loop output:

| corpus | increased | unchanged | decreased | false alarms |
|---|---|---|---|---|
| HC3 (n=30) | 0 | 30 | 0 | **0%** |
| RAID (n=30) | 0 | 30 | 0 | **0%** |

The rewriter's transforms are substitutions, merges and splits. None of them touches polarity, and
contractions keep the marker — so a symmetric "the negation count must not change" veto never fires
on legitimate output. Symmetric on purpose: removing a negation inverts the claim exactly as badly
as adding one, and `certainty_kept` covers hedges rather than polarity.

**Two measurement bugs on the way, both in the instrument rather than the code.**

The first pattern used `\bn't\b`. In "aren't" the apostrophe-t is preceded by a word character, so
the boundary never matches and every contraction read as a lost negation — a phantom "decreased on
4 of 25". That is the [Result 44](free-ceiling-measured.md) failure exactly, committed while
measuring, in the tool doing the measuring.

The second was real and taught the design. With the regex fixed, RAID still showed 1 loss in 30.
Inspecting it: `"not only"` → `""`, the structural rewriter turning "not only X but also Y" into
"X and Y". That is a correlative conjunction, not a polarity marker — the claim is that BOTH hold —
and the transform preserves the meaning exactly. Excluded with a lookahead, and RAID went to 0/30.
Excluding a marker can only remove mismatches, never create one, so HC3's 0/30 stands unrecomputed.

Worth keeping: **the outlier was the design.** One text in thirty disagreed, and the choice was
between an asymmetric veto that would miss half the attack surface and a symmetric one that seemed
to cost 3%. Reading what that single text actually did showed the 3% was not a cost at all — it was
a marker that should never have been counted.

## Result 74

**Three quantity changes the numerals gate lets through, and only one of them is its job.**

Ten probes at the mechanical quantity gate. It correctly blocks 240 → 420, "three years" → "five
years" and "9 of 10" → "9 of 12", and correctly allows the formatting variants that a rewriter
actually produces: 12% → "12 percent", $1,200 → $1200, "2.5 mg" → "2.5mg".

Three quantity changes pass:

| | |
|---|---|
| "half the cohort" → "most of the cohort" | not its job |
| "a third of patients" → "two thirds" | not its job |
| "the rate doubled" → "tripled" | not its job |

The module docstring is explicit — *"it asserts only that each numeral in the source is still
findable in the rewrite… It makes no judgement about meaning, which is what the NLI gate is for."*
None of those three contains a numeral. The gate is honest about its scope and the scope is
defensible: a fraction-and-multiplier vocabulary is a meaning judgement, and the NLI gate owns
those.

**The fourth case was its job and it failed.** The same docstring promises a numeral counts "as a
numeral **or as its English word**", and 240 → "two hundred and forty" was vetoed. `_spelled_value`
summed the parts, reading it as 2 + 40 = 42. That 5, 12, 20 and 100 all round-tripped is what hid
it: the small values are covered by exact word forms and 100 by a loose-synonym map, so everything
compound fell through both and nothing pointed at the gap.

Multipliers now scale what precedes them. 240, 100, 999 and twenty-four all read correctly; the 23
existing tests still pass and a changed spelled quantity ("two hundred and **fifty**") is still
caught — widening what counts as a number must not widen what counts as equal.

Unreachable from the free path: no in-repo rewriter spells numbers out. The LLM rewriter writes
prose and can spell whatever it likes, which is where this bites.

"one thousand two hundred and forty" still reads as two numbers, pinned as a known limit — one
multiplier per match, no observed instance, and the alternative is a materially more complex regex.
The same call as the spaCy parse asymmetry in [Result 72](free-ceiling-measured.md).

Worth keeping: **a gate that is honest about its scope is not thereby correct within it.** Three of
the four misses were out of scope and documented as such; the fourth was squarely inside a promise
the docstring makes in the same paragraph, and the passing cases either side of it made the gap
invisible.

## Result 75

**A check that fired ten times and was right none of them.**

`check_test_inventory` requires the documented module count to equal the count on disk, exactly. In
a single-session repository that is correct and cheap. With two sessions committing it fired **ten
times**, every time because a module landed between one session reading the count and writing it,
and **not once** on a document that was actually stale.

The cost is not the noise. It is that a red gate carrying no information trains everyone to look
past it — and this one sat red across several commits while both sessions treated it as background.

The test-count check next to it never had this problem, because its contract is asymmetric:

```
assert claimed <= actual                 # overstating is always a defect
assert actual - claimed < 200            # understating a little is just concurrency
```

Overstating claims coverage that does not exist. Understating by a few is what a moving repository
looks like. The module check now uses the same shape with a five-module window, verified against
all three cases:

| doc claims | actual | verdict |
|---|---|---|
| 120 | 100 | **FAIL** — claims coverage that does not exist |
| 75 | 100 | **FAIL** — stale by more than 5 |
| 98 | 100 | pass — two behind, which is concurrency |

The failure the check exists for is a document abandoned at 75 while the suite grows past 100, and
a five-module window does not hide that.

**One of the ten was mine and self-inflicted**: I read the module count, then committed a new test
file, then wrote the count I had read — one behind, by my own hand, in the same sequence I had been
attributing to the other session.

Worth keeping: **decide which direction of an error is the defect before choosing equality.** Both
checks measure drift between a document and the code. One asked "are these equal", the other asked
"is the document claiming more than exists" — and only the second question survives a repository
that more than one person is writing to.

**A second multi-session hazard, learned twice.** The git index is shared. Staging a file and not
committing it immediately means the next `git commit -a` from the other session absorbs it — which
happened to `run.py` and then to `test_the_loop_is_reproducible.py`, both landing under commit
messages describing something else. Nothing is lost and the author is the same either way, but the
history stops explaining itself. Stage and commit in one step; never leave work staged.

## Result 76

**The first rewrite in a process is not reproducible with the ones after it.**

Every measurement in this log assumes the loop is deterministic under a fixed seed, and nothing had
asserted it. It is — with one exception that took six probes to corner.

| what was tested | result |
|---|---|
| fresh rewriter, 6 HC3 texts, 3 runs each | 6/6 reproducible |
| **fresh rewriter, synthetic text, 4 runs** | **2 distinct outputs** |
| reused rewriter, same seed | reproducible |
| one text's output after another ran on the same instance | identical — no state leakage |

The failing case narrowed to a cold start: **run 0 differs, runs 1–4 are byte-identical.**

It is not the rewriter. `rw.rewrite()` called directly is identical 4 of 4, fresh instance or
reused. It is not the scorers — `score_text`, `score_tells` and `similarity` return the same values
on five consecutive calls. It is not the gates: `entailment.available()`, `roles.available()`,
`meaning_preserved` and `role_swap` are stable. It is not sentence targeting.

The first call **lazy-loads models, and that loading draws from the global RNG.** The substitution
step downstream then sees a different stream, and picks different synonyms — "setup taps into"
against "structure uses", with identical `rewrites`, `adopted`, `stopped` and `post` values. Once
warm, the RNG state after each call is identical and a fresh rewriter reproduces exactly.

**What this does and does not mean for the numbers in this log.** A harness that seeds before its
first call gets exactly one perturbed result — at n=6 that is 17% of the sample. But every
comparison here is *paired*: both arms process the same corpus in the same order, so text 0 takes
the cold-start hit in both, and the difference between arms is unaffected. The measurements stand,
and they stand for a reason that had not been checked until now.

Worth keeping: **"deterministic" is a property of a warm process, and nothing says so.** Six
components were individually verified stable before the cause turned out to be the *act of loading
them*. A test that seeds and asserts on its first call is testing the loading, not the loop.

## Result 77

**The citation guarantee worked; the check that would tell you it had stopped working did not.**

`--against` is the academic headline — report any citation a rewrite lost. Probed with twelve
citation forms:

| family | recognised |
|---|---|
| natbib `\citet` `\citep` `\cite`, APA `\citeA`, `\nocite` | yes |
| **biblatex `\parencite` `\textcite` `\footcite` `\autocite`** | **no** |
| **starred `\citep*` `\parencite*`** | **no** |

`CITE` matched `\(?:cite[a-zA-Z]*|nocite)` — commands that *start* with "cite". biblatex, which is
the modern standard, puts the stem in the middle. Those returned **no keys at all**, so `--against`
printed "keeps every citation" on a rewrite that had destroyed every one of them, and no biblatex
key was ever checked against the `.bib`. The starred forms failed separately: the star sits between
the command and its optional argument.

**`preserve.lock()` was never fooled.** It masks LaTeX commands structurally, and measured on a
full rewrite, `\parencite{smith2023}`, `\textcite{jones2022}` and `\citep*{li2024}` all survive
byte-exact. So the guarantee held the whole time — and the instrument that reports on it was blind.
That is the more dangerous half: a broken guarantee with working reporting gets fixed, and a
working guarantee with blind reporting is discovered the day it breaks.

Fixed, and end to end a lost biblatex key is now named and the exit code is 1.

**Two false alarms of my own, both from the shell.** The first: `latex … | tail` reported exit 0
because `$?` is `tail`'s — the identical pipeline mistake recorded earlier in this session, made
again while checking a feature's exit code. The second: a `printf` fixture turned the `\t` of
`\textcite` into a literal tab, so the tool correctly counted 2 citations in a 3-citation file and
I nearly wrote up a phantom inconsistency between the counter and the loss check.

**And the comment describing the fix was itself mangled by the same class of bug.** Writing it
through a shell turned the `\t` of `\textcite` into a tab, the `\f` of `\footcite` into a form
feed and the `\a` of `\autocite` into a BEL — three control characters committed into a source
file, in a comment about escape handling. `check_no_control_characters`, added in
[Result 44](free-ceiling-measured.md) after exactly this, caught all three on the next audit run.
Sixth escape mangling this session, and the first one a standing check found rather than a reader.

Worth keeping: **check whether a guarantee and its report share a code path.** They did not here,
and nothing in either file said so. The locking is structural and the reporting is a command
whitelist, which is why one covered biblatex and the other did not — and why the gap could sit
there indefinitely without a single citation ever being lost.

## Result 78

**Three surfaces probed, two clean, and the third was the same shape for the fourth time.**

`untell-audit` and the gate work covered the scoring and rewriting paths. These are the surfaces
nothing had touched.

**The REST server is solid.** With `UNTELL_API_KEY` set: 401 without a key, 401 with a wrong one,
200 with the right one, and `/health`, `/docs`, `/openapi.json` open by design. Payloads over
`MAX_INPUT_CHARS` are rejected 422 in milliseconds, every numeric parameter carries a `Field`
bound, and each rejection names its limit — *"String should have at most 50000 characters"*,
*"Input should be less than or equal to 32"*. Nothing to fix.

I did report one gap that was not there: the 50,000 limit looked undocumented because I searched
`docs/api-server.md` for `50000` and the document writes `50,000`. Reading it rather than trusting
the grep is what caught that — the same class as the substring and boundary failures recorded
throughout this log, in the check rather than the code again.

**`voice_distance` had the recurring defect.** `voice_report` returns the thin-sample caveat as a
`warning` key. `voice_distance` returns a bare float and returned it in silence — a **9-word sample
against a documented 150-word minimum answered 2.6543**, with nothing to say the number sits where
the same-author/cross-author AUROC is 0.680 and the feature noise rivals the signal.

That is the fourth instance of one shape:

| surface | rich form carries the caveat | scalar form dropped it |
|---|---|---|
| `humanness` | `score_text`'s `warning` | fixed, Result 62 |
| meaning gates | `meaning_preserved` conjunction | polarity added, Result 73 |
| `--against` | `lock()` protects structurally | reporting was blind, Result 77 |
| **`voice_distance`** | **`voice_report`'s `warning`** | **fixed here** |

The loop guarded it separately in every case — `untell humanize --voice-sample` warns on stderr — so
each gap was on the direct-call path only, which is exactly the path a library user takes and the
one no CLI test covers.

Worth keeping: **a scalar return value is where caveats go to die.** Four times in this codebase the
rich function knew the limit and the convenient one discarded it, and each time the convenient one
is what a caller reaches for. Returning a float is a decision to throw away everything the
computation learned except its answer.

## Result 79

**A warning can be present, prominent, and still describe the wrong event.**

Result 78 ended on the shape where a scalar drops its caveat. The obvious next question is whether
the caveats that *are* carried say the right thing. On the voice path, one did not.

There are two floors on a voice sample, in two different files:

| floor | where | what happens below it |
|---|---|---|
| 20 words | `run._MIN_VOICE_SAMPLE_WORDS` | `_voice_key` returns a constant — **the tie-break does not run** |
| 150 words | `voice.MIN_SAMPLE_WORDS` | it runs, on a profile whose same-author/cross-author AUROC is 0.680 |

The structured `voice_warning` tested only the second. MEASURED, over the `untell_text` result dict:

```
  5 words -> "voice_sample is 5 words; ... the voice tie-break is close to arbitrary."
 75 words -> "voice_sample is 75 words; ... the voice tie-break is close to arbitrary."
200 words -> None
```

The same sentence for both, though at 5 words there was no tie-break to be arbitrary. A caller reads
"close to arbitrary" as *your voice was used, weakly* and acts on it by trusting the output a little
less. The truth was *your sample had no effect at all*, which calls for a different action entirely:
supply more text, or stop believing the feature is on. The distance between those two readings is
the whole value of the warning.

The stderr message on the same condition has always been right — *"voice matching is disabled for
this run"*. So the CLI user, who has a human watching a terminal, was told the truth, and the REST
and MCP callers, who read only the dict, were told the other thing. That is the fifth consecutive
instance of one asymmetry: **the surface with a human watching is guarded, the programmatic surface
is not.** Results 62, 73, 77, 78 and this one.

The fix branches on which floor was crossed. The test that matters is not the wording but the
behaviour underneath it: below 20, all three candidates key identically (`{0.0}`); above it, all
three key differently. A message about a tie-break is now pinned to whether a tie-break happened.

Worth keeping: **checking that a caveat exists is not checking that it is true.** Every audit so far
has looked for missing warnings. This one was present, was read, and was wrong — and no count of
warnings, no coverage number, and no test asserting `warning is not None` would have found it.

## Result 80

**A check designed from a defect that would not have caught the defect.**

Result 79 suggested a mechanical rule: *a warning naming a literal number must name the constant
that gated it.* Written as an AST pass over `untell/`, it fired twice across 57 files:

```
tells.py:970  gate={_MIN_WORDS_FOR_A_RATE: 14}  msg names 100    "a rate per 100 words"
tells.py:970  gate={_MIN_WORDS_FOR_A_RATE: 14}  msg names 0.642, 7.32, 60, 100
```

Both are correct code. The first is the unit the rate is expressed in; the second is a quoted corpus
mean. Zero true positives.

And the decisive part: **it would not have caught Result 79.** That message interpolated
`{MIN_SAMPLE_WORDS}` — it named its gate, accurately. The bug was that the gate itself was the wrong
constant, chosen in a different module from the one controlling the behaviour. A rule about the
relationship between a message and its own branch cannot see a bug about the relationship between
two branches. Not shipped.

**What was worth doing instead: count them.** Seven constants gate a text-length decision, in seven
modules that do not reference one another:

|  value | constant | module |
|---:|---|---|
| 5 | `_MIN_WORDS_FOR_SIGNAL` | `detectors/perplexity_burstiness.py` |
| 5 | `_MIN_WORDS_FOR_SIGNAL` | `humanness.py` |
| 14 | `_MIN_WORDS_FOR_A_RATE` | `scripts/tells.py` |
| 20 | `_MIN_VOICE_SAMPLE_WORDS` | `scripts/run.py` |
| 40 | `_MIN_WORDS_FOR_A_VERDICT` | `scripts/score.py` |
| 60 | `_MIN_WORDS_FOR_REPETITION` | `scripts/tells.py` |
| 150 | `MIN_SAMPLE_WORDS` | `scripts/voice.py` |

They are not meant to agree — five words is enough to refuse a perplexity score and nowhere near
enough to profile six style features. Two of them are the same concept twice: `humanness` abstains
where its detector abstains, and between two different floors is a band where a score is reported
over an abstention. That pair is now asserted equal.

Each of the others is a published number some result in this log was measured against, so a silent
change invalidates a result without touching the document. The census pins all seven with their
derivations, and a final scan fails if an eighth appears — which is the case Result 79 was.

Worth keeping: **when a check built from a bug cannot catch that bug, the bug was not the kind the
check models.** The honest move is to say so and count the thing instead. An enumeration is weaker
than a rule and it was available; the rule was stronger and was fiction.

## Result 81

**A guard against accusing humans, switched off by the failure it was built for.**

Result 79's lesson was that a caveat can be present and untrue, so the next step was to enumerate
every caveat in `untell/` that makes a checkable claim about behaviour — *disabled*, *ignored*,
*falls back*, *excluded*, *abstains*. Thirteen of them. This is the one that was wrong, and it is
worse than the voice case, because the field involved exists for no other purpose than to answer
this question.

`perplexity_burstiness` has two scoring paths. Its own docstring carries the difference:

```
path      FPR     TPR     AUROC    human mean
gpt2      6.0%    98.0%   0.9972   0.129
stdlib   69.0%    93.0%   0.7545   0.399
```

`mode()` returned `"gpt2" if self._torch_ready() else "stdlib"` — **which path would run**, not which
one did. The two answers separate on precisely the failure `score()` already logs: torch imports
fine, the model raises at scoring time, the stdlib heuristic produces the number, and the field
reports the model.

That would be a mislabel if `detector_modes` were only diagnostic. It is not.
`score._verdict_threshold` reads it and raises the reported cut from 0.30 to 0.45 when the stdlib
path is the whole verdict — because the average human paragraph scores 0.399 on that path, above
0.30. MEASURED end to end, on a human paragraph, with the full path forced to raise:

```
healthy    mode=gpt2      cut 0.30    max 0.1502    not flagged
before     mode=gpt2      cut 0.30    max 0.4044    FLAGGED
after      mode=stdlib    cut 0.45    max 0.4044    not flagged
```

A GPU running out of memory told someone their own writing reads as AI. The guard that exists to
prevent exactly that was disabled by the failure it exists to cover, and — the question memory says
to ask of an asymmetric error — it landed on the accusing side.

The first probe of this was wrong and worth recording. I broke the full path on a one-sentence
fixture and got a byte-identical score, which reads as "the fallback changes nothing." It changed
nothing because burstiness over a single sentence is undefined, so `_full_score` was already
returning the lite value — full and lite agreed at 0.37863636363636366 before anything was broken.
A fixture where the two paths coincide cannot test which label was attached to them. Establishing
that they differ (0.6221 vs 0.1086) was the step that made the probe mean anything, and it is now
an assertion in the test file rather than a fact I happened to check.

Worth keeping: **a field that reports a capability is not reporting an event.** `_torch_ready()`
answers "can this run", `mode()` was asked "what ran", and the gap between them is invisible until
the thing that can run, doesn't.

## Result 82

**The ensemble handled a dead detector correctly and reported the consequence nowhere.**

Continuing the sweep of the thirteen behavioural caveats. `commercial.py` claims a broken adapter
"was EXCLUDED from the ensemble", and that claim is **true** — better than true, the surface is
carefully built:

```
HEALTHY   detectors={pb: 0.0843, roberta: 0.6566, hc3: 0.0911, fast: 0.1058}   mean 0.2344
ABSTAIN   detectors={pb: 0.0843, roberta: None,   hc3: 0.0911, fast: 0.1058}   mean 0.0937
RAISE     ... plus roberta_openai__error, failed_detectors=['roberta_openai']
```

The mean is taken over three, not over four-with-a-zero — a `None` coerced to 0.0 would have dragged
the mean down while looking like a measurement. Abstention and crash are distinguished. Nothing to
fix in the mechanism.

**The verdict is where it goes wrong.** `max` over fewer members can only fall, so a lost detector
errs in exactly one direction:

```
all four live    max 0.6566    flagged True
one silent       max 0.1058    flagged False
```

The verdict flipped from *this is AI* to *this is clean*, and the only trace was a `null` nested
inside `detectors` — a `null` in the JSON that no API client has a reason to inspect once `flagged`
has answered the question. `failed_detectors` covers the raising case, but it names *which* detector
died and says nothing about what its absence did to the answer.

This is precisely the scenario `commercial.py`'s docstring already describes: a provider changes its
response shape, the adapter starts returning None, and a detector the user is being billed for
leaves the ensemble quietly. The adapter warns on stderr. The result dict did not. Sixth instance of
the same asymmetry.

**The caveat is rare by measurement, not by hope.** Over 80 real HC3 texts at ≥60 words, partial
abstentions were **0/80**. The path is reachable only through a genuinely broken detector, so the
warning cannot fire on healthy scoring — which is the whole reason it is worth reading when it does.

One methodological note. The first version of the flip test asserted `flagged is False` after
silencing the top member. It passed with torch and **failed under `UNTELL_LITE_NO_TORCH=1`**, where
a different set of detectors loads and both maxima land above 0.30. The claim was never about 0.30:
it is that a band exists where the same text is flagged with the full ensemble and cleared without
it. Taking the cut from the two measured maxima states that claim directly and holds on whatever
detectors the machine has.

Worth keeping: **a test that encodes an environment instead of a claim passes where it was written
and fails where it matters.** The fix was not to relax the assertion but to find what the assertion
was actually about.

## Result 83

**"Defaults are in use" was false whenever a second config file existed.**

`config.load()` returns the first source that yields anything — `untell.yaml`, then
`pyproject.toml`. Falling through is deliberate and documented: a repo with both files and no
PyYAML installed should still get its pyproject settings. But both readers told the user the
opposite about the consequence:

> *"Its settings are NOT applied and defaults are in use."*

The first clause is true. The second is false exactly when the fallthrough does its job. MEASURED
with a malformed `untell.yaml` beside a `pyproject.toml` carrying `threshold = 0.91`:

```
warning:    "...are NOT applied and defaults are in use."
effective:  {'threshold': 0.91}
```

0.91 is a cut at which almost nothing flags. Someone reading that warning concludes their clean
verdicts came from the 0.30 default; they came from a file they had just been told was not in play.
Third result running, the error lands on the reassuring side.

The readers now stop at what they can know — *its settings are NOT applied* — and `load()` says the
rest, naming the file that actually supplied the values, because it is the only place that knows
which source won.

Most of the work in the fix was keeping it quiet. Three shapes must produce nothing: no config at
all, a lone `pyproject.toml` with settings, and a `pyproject.toml` with no `[tool.untell]` — that
last one yields `{}` and is the final source, so there is nothing below it to report, and it is the
shape of most real repositories.

Worth keeping: **a warning that names a cause is safer than one that predicts an effect.** "Your
file was dropped" is knowable at the point of dropping. "Defaults are in use" is a claim about the
whole resolution chain, made by a function that can see one link of it.

## Result 84

**A count of working rewriters that could go negative.**

`EnsembleRewriter` warns when a member raises, because a shrinking pool makes the class look like it
is simply not helping rather than like it is missing parts. The count was
`len(self._members) - len(_MEMBER_FAILED)`, and `_MEMBER_FAILED` is module-level — it accumulates
every member name that has failed anywhere in the process, across ensembles with different members.
MEASURED with three ensembles built in one process, one member failing in each:

```
A (3 members)    "2 of 3"      correct
B (2 members)    "0 of 2"      one live member, reported as none
C (1 member)     "-2 of 1"     a negative count of rewriters
```

"0 of 2" states that the ensemble is selecting over nothing — that it cannot function — while it had
a working member producing rewrites. The warning was added so a degraded ensemble would not be
mistaken for a useless one, and in this state it asserted precisely the thing it existed to prevent.

Counted against `self._members` now. Note what makes the bug visible: **three ensembles in one
process.** Any test that builds one ensemble passes on the old arithmetic and the new one
identically, which is presumably why a warning added with care carried this for as long as it did.

The two remaining behavioural caveats from the sweep are sound. `targeted.py`'s "nothing to work on"
really does fall back to a whole-text rewrite rather than returning the input, and says so; the
comment beside it records that returning the input was the previous behaviour and why it was worse.
`commercial.py`'s exclusion claim was verified in Result 82.

Worth keeping: **process-global state makes per-instance arithmetic wrong in a way one instance
cannot show.** The set was global for a good reason — say it once, not once per call — and the
count was local. Nothing in either decision is wrong alone.

## Result 85

**The bug was in the output of the probe, not in the thing the probe was testing.**

I was verifying `targeted.py`'s claim that "nothing to work on" falls back to a whole-text rewrite
rather than returning the input. It does — the claim is true, the output changed, the inner rewriter
ran. But the output it produced was:

> *It greatly improves **in the end efficiency** and accuracy across the checked corpus*

`overall` → `in the end`, in a slot where "overall" is an adjective.

Two separate defects came out of pulling that thread, and both are invisible to every measurement
this repo has. A tell catalogue scores "in the end efficiency" as clean. A detector scores it as
human — more human, if anything, since it is not fluent machine prose. Only reading it finds it.

**Defect one: an adjective sense with adverb-only substitutes.** All three of `overall`'s
substitutes are sentence adverbs, so all three break before a noun:

```
the overall cost             -> the all told cost / the in the end cost / the on the whole cost
The overall distribution     -> The in the end distribution
improves overall efficiency  -> improves in the end efficiency
```

Derived rather than guessed. Every `_SYN` entry with a phrasal substitute was scanned for
`<determiner> <head> <noun>` across 240 HC3 texts; `overall` is the only hit with a live adjective
sense. It is also frequent — **4 of its 35 corpus occurrences are adjectival**, so this fired on
about one occurrence in nine.

The important half of the fix is what it does *not* touch. Measured slot by slot:

| slot | example | all three substitutes |
|---|---|---|
| adjective | `the overall cost` | break |
| sentence-final | `improved overall.` | fine |
| comma-flanked | `the result, overall, was` | fine |
| sentence-initial | `Overall, the price` | already declined, left to the transition stripper |

So the test is not the determiner in front — one of the broken examples has none — but the word
behind. A letter after it means the next token is what `overall` is modifying, and an adverb phrase
cannot modify a noun.

**Defect two, found by the same scan: a substitute that brings its own determiner.** One corpus case
of the shape, and it produced:

```
There was a significantly longer wait  ->  There was an a lot longer wait
```

`agree_article` had faithfully re-agreed "a" to "an" for the vowel in "a lot" — the article-agreement
fix working correctly on input it should never have been handed, which made the output worse instead
of catching it. Filtered rather than declined, matching the separable-particle rule beside it:
"sharply longer" and "greatly longer" are fine and still fire.

Worth keeping: **the fix for a bad substitution is not always to delete the entry.** The table's
established remedy has been removal (`arguably`, `possibly`, `significantly` under `profound`), and
removal here would have cost the 89% of `overall` occurrences that substitute perfectly. A slot
guard keeps them. What made that possible was measuring each slot separately instead of the entry as
a whole: read the output, then ask which *positions* the failure occupies rather than whether it
occurs at all.

## Result 86

**The damage battery was quiet because it was incomplete, not because the output was clean.**

Result 85 found two ungrammatical substitutions by reading output. The obvious follow-up is whether
the existing mechanical-soundness battery — eleven regex checks plus fragment, quote and bracket
counting — would have caught either. Neither:

- `an a lot longer wait` slips past `an_before_consonant`, because "a" is a vowel. The article-
  agreement code had *correctly* re-agreed "a" to "an" for it.
- `the all told cost` matches nothing in the set at all.

And the battery ran on four hand-written fixtures. MEASURED over 60 real HC3 AI paragraphs rewritten
by `composite`, the eleven checks introduce **1** finding (a stub sentence). So the surface is
genuinely clean by what it measures, and what it measures had a hole the size of the defect.

Two checks added. `stacked_determiners` covers the first shape. `determiner_then_phrase` covers the
second and is **built from `_SYN` itself**, so a phrase added to the table later is covered without
anyone remembering this check exists. Both probes are real rewriter output rather than invented
shapes.

**The false positive is the interesting part.** The first version of the second check included
`this/that/these/those`, and the EdgeFlow fixture flagged immediately:

> *...edge-guided flow **that leans on** edge-guided flow...*

A relative pronoun in front of a perfectly good substitute for "leverages". A demonstrative and a
relative pronoun are the same token, so those four words make the check fire on correct English —
and a damage check that cries wolf gets its fixture edited instead of the bug fixed. Narrowed to
articles and possessives: still fires on both real defects, 0 false positives across 60 rewritten
texts and their untouched inputs.

Note which method caught that. **The 60-text corpus sweep did not; the four hand-written fixtures
did.** Those fixtures carry shapes chosen because each one broke something once — an appositive,
a serial list, a quotation containing a coordinator, a relative clause. That is a different kind of
coverage from volume, and this is the first time in this log that the difference has been visible
in a result rather than argued for.

**What the battery still cannot do, stated rather than papered over.** The third shape from the same
defect, `improves in the end efficiency`, has no determiner in front of the phrase. Separating it
from a legitimate "in the end we decided" requires knowing that "efficiency" is a noun and "we" is
not, and there is no POS tagger on the zero-dependency path. That shape stays guarded at the source
by `_ADVERB_SLOT_ONLY`, which declines the substitution instead of detecting it afterwards. Two
layers where the output is checkable, one where it is not — written into the module so the gap is a
decision on record rather than an oversight waiting to be rediscovered.

**A correction to Result 82, found by someone else reading the test.** Those tests silenced
`roberta_openai` and called it "the strongest member". On the full model set that is false — the
ensemble reads `mage 1.0000, perplexity_burstiness 0.8264, roberta_openai 0.2991` — so `mage`
saturates the max, silencing roberta moves it not at all, and both tests fail on their own premise.
They passed when written because the probe environment had `UNTELL_DISABLE_MAGE=1` set, leaving four
detectors with roberta on top.

That is the same defect Result 82 recorded one paragraph earlier, at a different level: I fixed the
version that encoded a *threshold* from the environment and shipped one that encoded a *member*.
Which detector tops an ensemble is a property of the model set and the input; the invariant under
test — losing a member can only push `max` down, and that has to be said out loud — is not. The
member is now resolved from the measurement rather than named.

Worth keeping: **"the checks pass" and "the output is sound" are different claims, and only the
first one is ever measured.** The gap between them is exactly the set of failures nobody has thought
of yet, which is why reading real output keeps paying and running a green battery does not.

## Result 87

**Ten paragraphs of real loop output, read rather than scored, gave two defects.**

Result 86 ended on the claim that reading output keeps paying where a green battery does not. This
is the test of that: ten HC3 AI paragraphs through `composite`, printed side by side, read.

**One: the parenthesiser closed its bracket inside the aside.**

```
one called melanin, which gives your skin, hair, and eyes their color, and another called...
  -> one called melanin (which gives your skin) hair, and eyes their color, and another...
```

`_ASIDE_RE` excludes commas from the aside body, so when the real aside contains one the pattern
matches a *prefix* and brackets that — leaving a dangling "hair, and eyes their color". The
transform is documented to change punctuation and nothing else, and every meaning gate agrees with
that documentation: no word is added, removed or reordered, so cosine, NLI and semantic roles all
pass a sentence that has been cut in half.

The fix reads what FOLLOWS the closing comma. A serial list continues with more items and a
coordinator; a genuine aside end is followed by the sentence resuming — "...of your eye, **and by
the way that** the iris scatters light" — where the coordinator comes first and no item list
precedes it. Checked after the match rather than by widening the body, because a body that allowed
commas would swallow the coordinate clause after a real aside: the opposite error, same damage.

**Two: the splitter guarded one half of the split and not the other.**

```
These TVs can only display SD channels, so if we only had HD channels, those people wouldn't...
  -> These TVs can only display SD channels, so if we only had HD channels.
     Those people wouldn't be able to watch TV.
```

`_cannot_start_a_sentence` has guarded the right half for a long time, and the right half here is a
perfectly good sentence — which is exactly why it passed. Nobody was asking whether the LEFT half
could close a clause. A conditional with nothing conditional on it.

The existing `fragment_lead` check cannot see this either: it reads the first word of a sentence,
and this sentence begins with "These".

The first version of the guard tested only the head of the final segment, and the same paragraph
immediately produced a second one — *"Basically, this means that if we only had HD channels."* —
where the subordinator is buried mid-segment behind an innocent "this". So the check looks for a
clause opener anywhere in the segment, which is sound because `rsplit` guarantees the segment
contains no commas: a clause opened inside it is still open at the split point.

Which words go in that "anywhere" set is the whole difficulty. `as`, `since`, `while`, `after`,
`before`, `until`, `once` are prepositions at least as often as subordinators — *"as many HD
channels as we have"*, *"before deployment"* — so testing for them anywhere rejects correct splits.
They stay in the head-of-segment check, where they are unambiguous. Two sets, and the reason for
the difference is written down.

MEASURED over 60 HC3 AI paragraphs after both fixes: **0 orphaned subordinate clauses introduced,
with 30 net new sentence terminators** — the fragments are gone and the splitting still happens.
Both numbers are needed; either alone is satisfied by a transform that has quietly stopped working.

**Three: re-reading the same ten paragraphs found the fix's own leftover.**

```
...pigments in your iris. (which is the colored part of your eye) and by the way...
```

Not a new rule — an interaction. `_parenthesise_asides` runs *before* the split is judged, so by the
time `_cannot_start_a_sentence` looks at the right half it reads `(which`, and `which` is in its
fragment set while `(which` is in nothing. The guard was working correctly the whole time and the
token had changed underneath it: the same fragment, one character wider.

Verified directly rather than through the pipeline — `_cannot_start_a_sentence` returned `True` for
`"which ..."` and `False` for `"(which ..."` on identical text. Leading brackets and quotes are now
stripped before the word is read, and a bracketed clause that genuinely can stand alone is still
allowed, so the strip did not turn every parenthesis into a fragment.

**Three defects from one reading of ten paragraphs**, in code that passes 4300 tests, a 13-check
damage battery and every meaning gate.

Worth keeping: **a guard on one side of a symmetric operation is not half a guard, it is a guard
with a blind spot the shape of the other side.** All three had a careful, well-documented check
sitting next to the hole — the aside pattern reasoned about restrictive versus non-restrictive
clauses and never about its own closing comma; the splitter reasoned about what the second half
opens with and never about what the first half ends with; and the fragment set reasoned about words
while the pass upstream of it was busy prefixing those words with brackets.

And the corollary, which is why the re-read mattered: **fixing two defects in a pipeline changes
what the third one looks like.** The bracketed fragment was present in the very first batch and I
read past it, because at that point it was one line below a worse fragment and a destroyed serial
list. Reading output is not a step that completes.

## Result 88

**A different corpus, read the same way: there was no "natural midpoint", only a midpoint.**

Result 87 read HC3. RAID is academic abstracts — longer sentences, quoted titles, compound technical
terms — and the first paragraph produced this:

```
...a team of experts in the field of artificial.
Intelligence (AI) and medical imaging set out a set of guiding principles...
```

Straight through the middle of "artificial intelligence". Nothing downstream could catch it: the
right half opens with a capitalised noun and reads as a perfectly good sentence to every guard in
the file, including the two added one result ago.

The cause is one line. `_split_long_sentences` initialised `split_at = mid` and only moved it if a
comma turned up nearby, so **a sentence with no comma was cut at whatever word sat halfway.** The
comment above it called this "a natural midpoint". MEASURED over 269 long sentences (>28 words)
across HC3 and RAID:

| | count | share |
|---|---:|---:|
| a plain comma token is found | 242 | 90.0% |
| a comma only visible after stripping a closing quote | 1 | 0.4% |
| **no comma at all — cut at the midpoint** | **26** | **9.7%** |

Not splitting those 26 costs a transform on a tenth of long sentences. Splitting them costs grammar
on all of it.

**And the 1 is the sentence above.** Its only comma is in `Imaging,"` — a comma closing a quoted
title — which does not `endswith(",")`, so the search found nothing and fell through to the
midpoint. Stripping the closing quote makes that boundary visible, and then the appositive guard
*correctly refuses to split there*, because `In the paper X,` followed by `a team of experts` is
exactly the shape that guard exists for. Visible-then-rejected and invisible-then-butchered produce
very different sentences, and only the first leaves this one intact.

Splits still happen after the change: 18 net new sentence terminators on HC3 and 76 on RAID, over 40
texts each.

**The test measured the wrong thing first, and passed.** `_split_long_sentences` returns one element
per INPUT sentence and puts the split *inside* the string, so `len(result)` is always 1 —
`assert len(...) == 1` was true no matter what the code did. It was caught by the neighbouring
guard-the-guard test failing: the fixture that was supposed to split also reported 1, which is the
only reason the measure got examined at all. Counting terminators instead makes both assertions real.

**Re-reading again found the next one, in the next sentence of the same abstract.**

```
...to address the ethical.
Social, and technical challenges associated with the use of AI in medical imaging.
```

A serial list of adjectives cut in half. `_split_one` has refused this shape for a long time — its
`list_like` guard counts comma-terminated tokens and this sentence has four — and
`_split_long_sentences` had no such guard at all.

That is the **third** time these two functions have been found with the same hole in one of them.
The fragment guard was the first, the midpoint default the second. Both times the file's own comments
record that fixing one left the damage rate unmoved because the other kept producing it. A predicate
that one splitter can have and the other can lack *is* the shape of this bug, so it is now one
function with two callers, and a test asserts the threshold appears exactly once in the module.

Split rate barely moves: HC3 18 → 13, RAID 76 → 75 over 40 texts each. The guard is precise rather
than blunt, which is what a 4-comma threshold should be.

Worth keeping: **a vacuous assertion and a correct one look identical when the code is right.** The
positive control is what separates them — not as a nicety, but as the only mechanism that surfaces a
measure which cannot fail. Every "does it still work?" test in this log has now earned its place
twice: once for the regression it guards, and once for exposing a sibling assertion that measured
nothing.

## Result 89

**With the splitting damage gone, the substitution damage underneath it became readable.**

Fourth pass over the same RAID abstracts. The structural breakage from Results 87 and 88 is absent —
the quoted title survives, the serial lists survive, no sentence ends mid-term. What is left is one
bad verb:

> *a fundamental task in computer vision that **needs allowing** a user to interact with an image*

`involves` → `needs`. Those are different sentences. *"involves X-ing"* means **includes the
activity of** X-ing; *"needs X-ing"* means **requires being** X-ed. With an object following the
gerund, the second reading collapses into nothing.

MEASURED across 240 HC3 and RAID texts, `involves` is followed by a gerund in **33% of its HC3
occurrences and 72% of its RAID ones**. In academic prose it is the majority case, not an edge, so
this fired on most uses of the word in the corpus this repo has an explicit niche in.

`means allowing` reads correctly, so the fix filters the option list rather than declining the swap —
the same shape as the separable-particle rule beside it.

**The near-miss matters more than the fix.** `requires`/`require` → `needs`/`need` looks like exactly
the same pattern and is correct: *"requires calibrating"* and *"needs calibrating"* both carry the
passive reading. A rule stated as "needs cannot take a gerund" would have broken working output. The
rule is about `involves` specifically, and there is a test asserting `requires calibrating` still
converts, so a future tidy-up that generalises this cannot do so silently.

The scan that produced the entry found 29 headwords that ever precede an `-ing` word. All the others
are adjective-plus-noun (`robust testing`, `novel tracking`) or noun-plus-participle (`approach
using`) — no verb complement involved at all. One real case out of 29 candidates.

**And the guard caught my own entry within the hour.** I wrote `_GERUND_UNSAFE` with two keys,
`involves` and `involved`. The table has no `involved` headword, so that entry guarded a
substitution that cannot happen — a guard pointing at nothing, which reads as protection forever.
`test_the_unsafe_map_names_real_substitutes` failed on the first run and named it.

**One more read, and the worst one yet — because it is a tell, not just bad grammar.**

```
However, existing methods for interactive segmentation are limited...
  -> But, existing techniques ...
  -> Though, existing techniques ...
```

Neither is English. And measured across the same 240 texts, neither is anything at all:

| form | occurrences |
|---|---:|
| `However,` | 95 |
| `But,` | **0** |
| `Though,` | **0** |

Zero in the human half and zero in the AI half. The substitution did not merely produce bad grammar:
it produced **a form nobody in the reference corpus writes**, which is the definition of the tell
this rewriter exists to remove. The pass meant to erase a fingerprint was minting one.

`however` is not in `_TRANSITIONS_RE`, so the sentence-start decline that protects `moreover`,
`furthermore` and `therefore` never applied to it — and it should not, because those are deleted
outright and `however` carries a contrast that deletion would lose. It needed the other kind of
guard, and had neither.

86% of the 117 `however` occurrences carry that comma, so this is the usual slot. Bare, the same
substitutes are correct — "the method is fast, however it fails" → "...but it fails" — so the rule
filters on the comma rather than dropping them. `by contrast` is a sentence adverb and works in both.

Worth keeping: **the guard-the-guard test is not only for the future.** It has now caught a defect in
the very commit that introduced it, twice in this log — the fixture that was supposed to split and
reported 1 in Result 88, and the phantom `involved` entry here. Writing the negative case is cheap
enough that it is worth doing even when the positive case is the point.

And the sharper one: **a rewriter that substitutes from a table can invent a tell the table was
built to remove.** Three of this session's substitution defects share that shape — `in the end
efficiency`, `an a lot longer`, `But,` — and none of them is visible to a detector, a tell
catalogue, or a meaning gate. The only instrument that finds them is a reader, and the only
instrument that keeps them out afterwards is a corpus count of the form being emitted.

## Result 90

**A budget that rounds turns a multiplier into a no-op.**

Not from reading output — from a red suite. The opener-dose rework replaced a per-sentence
probability with a spend-a-budget rule:

```python
budget = max(0, round(rate * len(sentences)) - marked)
```

Correct in intent, and it made two style flags inert. The style knobs are **multipliers** on that
rate: `blunt` and `minimalist` are 1.2x the neutral opener rate. On a paragraph of the test's length
0.30 and 0.36 round to the same integer, so those styles produced **byte-identical output to no-style
at every one of 60 seeds** — and `test_the_previously_inert_styles_now_bite`, a test written for
exactly that regression, failed on both.

The fix is the idiom this file already uses twice, for the fronting budget and the parentheses
budget, both with a comment saying why:

```python
raw = rate * len(sentences) - marked
budget = max(0, int(raw))
if random.random() < raw - budget:
    budget += 1
```

Carrying the remainder as a probability keeps the dose right on average — the entire point of the
budget — while letting a 1.2x rate still appear somewhere in a 60-seed sweep.

Worth keeping: **rounding is a lossy operation on a knob.** Any continuous parameter that reaches
its effect through `round()` has a dead band around every half-integer, and a multiplier smaller than
that band does nothing at all. The two earlier budgets in this file each hit it and each solved it;
the third one was written without them in view. That the file already contained the answer twice is
the useful part — a fix recorded next to the code it fixes is not the same as a fix that transfers.

A note on where this came from, since it matters for how much to trust it: this was found because
the suite went red on work another session had in flight, in the same file I was editing. The first
suspicion was my own change, and the way to settle it was to run the failing test with only the
other session's edits present — not to read the diff and reason about it. Reading the diff would have
pointed at the opener rework, which is right, but "the diff looks responsible" and "the diff is
responsible" are different claims, and only one of them is cheap to check.

## Result 91

**The `However,` fix closed a category, and the way to know that is to scan for the category.**

Result 89 fixed one substitution. The question that matters afterwards is whether it was one
instance or one of many, and the table is small enough to ask directly. Every `"<substitute>,"`
sentence opener `_SYN` can emit, against its frequency in 240 HC3 and RAID texts:

```
headword          n   substitute+,        corpus  human
however          95   but,                     0      0
however          95   though,                  0      0
overall          66   all told,                0      0
additionally     32   plus,                    0      0
furthermore      15   and,                     0      0
moreover         14   what is more,            0      0
therefore         7   that is why,             0      0
...
therefore         7   so,                     18      1
consequently      1   as a result,             3      1
```

Twenty forms at zero. **And a zero-frequency rule would have been wrong.** `still,`, `yet,` and
`even so,` are ordinary English openers that a 240-text corpus simply does not happen to contain —
sparsity is not evidence of a fingerprint. Building the obvious check here would have produced a
guard that fires on correct output, which is how a damage check gets its fixture edited instead of
its bug fixed.

What separates the real cases is grammatical, not statistical: **a coordinating conjunction cannot
take that comma at all.** Filtering the scan to bare single-word conjunctions, and then to headwords
that are not already protected, the whole table yields:

| headword | conjunction substitutes | protected? |
|---|---|---|
| `however` | `but`, `though` | yes — `_COMMA_UNSAFE`, added in Result 89 |
| `strengths` | `plus points` | not a conjunction — a noun phrase, and a phrase before a comma is fine |

The category is closed. Every other headword with a conjunction substitute is already deleted at a
sentence start by `_TRANSITIONS_RE` rather than substituted.

That is now a standing test rather than a fact about today. It reads `_SYN`, `_TRANSITIONS_RE` and
`_COMMA_UNSAFE` and requires every conjunction-substitute headword to have one protection or the
other — so a new table entry, or a headword leaving `_TRANSITIONS_RE`, fails instead of quietly
reopening the hole. Confirmed non-vacuous by clearing `_COMMA_UNSAFE` and watching it name
`however` and both substitutes.

The test also records why the two mechanisms are not interchangeable, because they look it. Deleting
`Moreover,` drops a join and nothing else; deleting `However,` drops a contrast the sentence is
making. One is right for `_TRANSITIONS_RE`, the other needs the filter. Without that written down, a
later tidy-up collapsing them into one list is the obvious next move.

Worth keeping: **after fixing an instance, scan for the category — and expect the obvious rule to be
wrong.** The scan took one query and turned a single fix into a closed set. The rule the scan first
suggested, "never emit a form the corpus has zero of", would have been a new bug.

## Result 92

**The end-state sweep, and the check it caught being wrong was mine.**

With the substitution and splitting work done, the state of the rewriter over 40 texts from each
corpus, `composite`, seed-per-text:

| | HC3 | RAID |
|---|---|---|
| 13-check damage battery introduced | nothing | `stub_sentence: 2` |
| orphaned subordinate clauses | 0 | 0 |
| `But,` / `Though,` openers | 0 | 0 |
| `needs`/`takes` before a gerund | 0 | 0 |
| stacked determiners | 0 | 0 |
| determiner + adverb phrase | 0 | 0 |

That is the version after one correction. The first run of this sweep reported
**`determiner_then_phrase: 8`** on RAID — my own check, added in Result 86, firing on output I had
just finished fixing. Two distinct spans behind those eight:

```
mixes the plus points of global and local contrastive learning
with a focus on semi-supervised learning and ...
```

**`a focus on` was in the untouched input.** `focus on` is a substitute for `prioritize`, so the
check matched a phrase the rewriter had never touched, in text it had not written. Correct English,
flagged as damage.

The error is the same one as the `that leans on` false positive in Result 86, one level up. There I
narrowed the *determiner* set and left the *phrase* set as "every phrasal substitute in the table" —
but most phrasal substitutes are noun or verb phrases and follow a determiner perfectly well: `the
plus points of`, `a focus on`. Only an **adverb** phrase cannot, and that was the whole defect being
modelled. The set is now derived from the headwords already known to be adverb-slot-only, which is
both narrower and self-maintaining.

Result 86 recorded that the four hand-written fixtures caught what a 60-text sweep missed. This is
the converse in the same file: the 40-text RAID sweep caught what the fixtures could not, because
none of them contains `a focus on`. Neither method dominates. The reason the check survived a
session with a false positive in it is that nothing ran it over a corpus until now.

**One observation deliberately not acted on.** `strengths → plus points` produced those eight, and
`plus points` occurs **0 times in the human half and 0 in the AI half** of 240 texts, against
`advantages` at 3 and 9. That is the same signature as `But,` in Result 89. But Result 91's lesson
was written one result ago: a 240-text corpus at zero is not evidence when the phrase is ordinary
English elsewhere, and `plus points` is ordinary if informal. Removing it would be acting on
sparsity, and the register argument — informal British in an academic abstract — is real but is not
what the measurement shows. Recorded, not fixed.

Worth keeping: **a damage check is code, and it gets the same treatment as code.** This one was
added with a measurement, a probe, and an explicit narrowing after a false positive — and still
shipped with a second false positive that only a corpus sweep would find. The instrument needs the
same auditing as the thing it measures, and "it found real bugs" is not evidence that it is right.

## Result 93

**Chasing the last residual: two stubs, one artefact, one real — and a self-inflicted crash.**

Result 92's sweep left `stub_sentence: 2` on RAID. Both, looked at:

```
text 23:  "TAN is"                      source ends mid-sentence at "In conclusion, TAN represents"
text 10:  "Put simply, in this paper."  source ends normally
```

The first is the truncated-source artefact already documented beside the check. The second is a
defect, and an interaction rather than a rule:

```
In this paper, we present a new method...            -> refused, "In this paper" is 3 words
Put simply, in this paper, we present a new method   -> "Put simply, in this paper."
```

`_MIN_SPLIT_SIDE` exists to stop a fronted adverbial becoming a sentence. A marker `_vary_openers`
prepended inflates the token count by exactly enough to clear it — three content words either way,
five tokens with the marker. One pass fragmenting the output of the pass before it, which is the
same shape the `"Of course."` comment beside `_split_one` already records, one marker further along.
The battery strips these before judging a fragment; the splitter that produces them was counting
them.

Counting content words on the left half fixes it: RAID `stub_sentence` 2 → 1, and the remaining one
is the artefact.

**The fix broke the module on its first run, and the crash is worth recording.** I named the helper
`_content_words`. `structural` already had a `_content_words` — returning a **set** of words, used by
`_drop_restatements` — and mine returned an **int**. The later definition wins, so an unrelated
function began raising

```
TypeError: object of type 'int' has no len()
```

Not caught by any test, because I ran the corpus sweep before the suite and the sweep crashed. A
2500-line module has room for two functions to want the same name, and `grep` before defining is the
whole cost of avoiding it. Both names now exist and differ — `_content_words` for the set,
`_content_word_count` for the number — with a test asserting they still return different types,
since the collision is only safe while that holds.

Worth keeping: **the guard against fragments and the pass that creates them measure the same
sentence differently.** The battery strips markers before judging; the splitter counted them. Every
defect in Results 87–93 is one pass disagreeing with another about what a sentence is — where it
ends, what opens it, what counts as a word in it — and none of them is visible from inside either
pass alone.

## Result 94

**The collision from Result 93, turned into a check that costs one AST pass.**

Python keeps the last definition of a name, silently, and hands every caller of the first one the
second. That is what turned `_drop_restatements` into

```
TypeError: object of type 'int' has no len()
```

without anyone editing it. No test caught it — the suite reaches that function through the rewriter,
and the rewriter crashed only on a corpus sweep that happened to run before the suite did.

`check_no_shadowed_definitions` scans `untell/`, `eval/` and `tests/` for a module-level name defined
twice. **1708 definitions, none shadowed** — so it is clean now and would have named my bug the
moment it existed, with the shadowing line and the shadowed one.

Verified by planting a duplicate rather than by trusting the pass:

```
PASS  no module defines the same top-level name twice  (1708 definitions, none shadowed)
FAIL  no module defines the same top-level name twice  (_thing redefined at line 2, shadowing line 1)
```

Module level only, deliberately. A method redefined inside a class is the same defect, but nested
scopes carry legitimate redefinition — a `try`/`except ImportError` pair defining a fallback is the
common shape in this repo — and a check that has to be argued with is a check that gets suppressed.

Worth keeping: **a defect that no test can see is a candidate for a check rather than a test.** The
distinction is whether the failure is a property of *behaviour* — which a test can exercise — or a
property of the *source*, which only something reading the source can see. This one is the second
kind: the code was correct, each function was correct, and the file was wrong. That is the same
family as `check_no_control_characters` (Result 44) and `check_no_dead_functions`, and it is now the
third time a session-inflicted mistake has been converted into a standing check instead of a note
saying "be careful".

## Result 95

**Layout protection was a property of one rewriter, not of the pipeline.**

Every defect in Results 85–93 came from prose. The obvious next question is what the loop does to
text that is not only prose — a README, a paper draft, anything with a table or a code block.

Three constructs were rewritten as if they were sentences, all at every seed:

```
| Method | Score |               ->  | Way | Score |  /  | Approach | ... |  /  | Technique | ... |
title: Moreover the framework    ->  title: What is more the system
    def f():                         def f():
        return utilize(x)        ->          return use(x)
```

The table heading is a label the surrounding text refers to and often a term of art. The YAML title
is document metadata. The third is the worst: the identifier was renamed **and the first line lost
its indent**, so what is left does not render as code at all — it renders as prose.

`layout` had no notion of a table row, indented code, or front matter. A table row carries no line
marker, so it was gathered into the surrounding block like any wrapped paragraph.

**And the deeper finding is where the protection lived.** `apply_per_block` was called by
`structural` and `mt_pivot` — nothing else. So:

```
--rewriter structural   code block INTACT
--rewriter surgical     code block DAMAGED
--rewriter composite    code block DAMAGED     <- the default
```

The same document was safe or corrupted depending on a flag, and the safe one was not the default.

**The first fix was wrong in an instructive way.** Making `surgical` run per block protects the
layout and costs quality, because this rewriter ranks its swaps by a detector score and a short
block scores badly. MEASURED over 50 HC3 and RAID texts:

| | max P(AI) | tells/100w |
|---|---|---|
| whole document (unsafe) | 0.5621 / 0.3962 | 5.612 / 9.576 |
| per block (safe) | 0.5662 / 0.3962 | 5.825 / **10.616** |
| whole + restore (shipped) | 0.5621 / 0.3962 | **5.612 / 9.576** |

11% worse tell removal on RAID — the corpus this repo claims a niche in — for protection that was
available for free. `surgical` substitutes words in place and never reflows: line count was
identical on all 50 texts and both structured fixtures. So run it on the whole document, then put
the non-prose lines back **by line index**. Same output as the unsafe version, byte for byte, with
the layout guaranteed.

Five further constructs — setext headings, thematic breaks, HTML blocks, footnote definitions, link
reference definitions — reach the transform as prose and come back intact. They are now pinned
anyway. Reaching the transform is exposure, and the only reason they are not damage today is that
no transform happens to touch them; that is a fact about the transform list, not a property of the
document.

Worth keeping: **"is it protected?" is a question about the pipeline, not about a function.** The
protection existed, was well written, had its own tests, and covered one of four backends. Nothing
in a per-function view of the code shows that — it took running the same document through every
rewriter in the registry, which is four lines of probe.

## Result 96

**Four probes that found nothing, which is worth the same paragraph as one that did.**

After Result 95, the natural worry is that layout was one instance of a general problem: protections
attached to a backend rather than to the pipeline. Checked, by measurement rather than by reading
the call sites:

- **`lock()` / `restore()`** — citations, numbers, entities. Applied in `run.py`, so uniform. Ran a
  LaTeX paragraph through all four CPU rewriters at four seeds each: `\citet{smith2023}`,
  `\citep{jones2022}`, `\cite{li2024mage}`, `12.4`, `$\alpha = 0.01$`, `3 seeds`, `NASA` and
  `Dr. Chen` survived every one.
- **Inline structures in prose** — a URL, a code span, a file path, an email address, a version
  string, a CLI flag and a markdown link, each embedded in an AI-sounding sentence. All seven intact
  across five seeds.
- **CLI file handling** — a BOM is stripped, CRLF is read, an empty file answers `{"error": "empty
  input"}`, accented UTF-8 works, and a binary file gets the best error message in the repo:
  *"decoded text contains NUL bytes — this is a binary file, or text in an encoding this reader
  could not identify."*
- **Effort spread on a long document** — 2761 words, 14 paragraphs. All 14 changed, 7/7 in each
  half. No early-concentration bug, which is the failure a document-wide substitution budget would
  produce.

**And one measured non-fix.** The loop sometimes leaves text with MORE tells than it started with —
4/30 on HC3, 1/30 on RAID. That looks like a defect until the trade is measured:

```
raid  # 9   tells +1.84   score -0.0859
hc3   # 0   tells +1.32   score -0.0920
hc3   #24   tells +1.00   score -0.1691
hc3   #21   tells +0.10   score -0.1939
hc3   # 7   tells +0.02   score -0.0080   <- inside the noise band, a wash
```

Four of the five bought a substantial score improvement with a small tell increase, which is the
trade the loop exists to make: the detector score is the objective and tells are the tie-break. The
mean movement is −0.643 tells/100w on HC3 and −2.233 on RAID. Not changed.

Worth keeping: **a probe that finds nothing has told you where not to look next.** Four surfaces are
now known-clean by measurement rather than by assumption, and the fifth — the one place a rewriter
touched something it should not — was found in the same afternoon precisely because the search had
somewhere specific left to go.

## Result 97

**Found in the one output path I had not been reading.**

Every reading so far has gone through the library API. Checking the CLI's `--json` — the path a
caller actually pipes text out of — surfaced this in the first paragraph:

> *It **a lot improves** overall efficiency and accuracy across the corpus.*

`significantly` → `a lot`. "a lot" is a noun phrase. It can follow what it modifies — *"improved a
lot"* is right — and premodify nothing but a comparative.

MEASURED across 240 HC3 and RAID texts: **67 of the 68** `significantly` occurrences are followed by
a word. So the broken slot is not an edge case, it is the position the word almost always occupies,
and one substitute in three was wrong there.

The exception is what keeps this from being a blanket rule, and it is the same shape as Result 85's
`overall`:

| slot | example | `a lot` |
|---|---|---|
| before a verb | `significantly improves` | broken |
| before a plain adjective | `significantly difficult` | broken |
| **before a comparative** | `significantly longer`, `significantly better` | **correct** |
| clause-final | `improved significantly,` | **correct** |

A noun-phrase adverbial premodifies a comparative and nothing else. That is a rule about the
following *word* — `-er`, or one of the suppletive forms — rather than about its part of speech, so
it is decidable without a parser on the zero-dependency tier.

Filtered rather than declined: `sharply` and `greatly` are correct before a verb, and leaving
`significantly` in place would leave an AI-vocabulary word the table exists to flatten.

**The category is closed and pinned.** Scanning `_SYN` for every `-ly` headword offering a
noun-phrase substitute — multi-word, opening with a determiner or quantifier — returns
`significantly` and nothing else. A standing test asserts that stays true, the same shape as the
conjunction-opener check in Result 91.

Worth keeping: **each output path is its own reading.** The library API, the CLI report, the `--json`
field and the REST response are four renderings of the same run, and the defect had been in every
one of them for as long as the table has existed. It surfaced when I looked at a different one,
which is the only variable that changed.

## Result 98

**Four surfaces, one question asked of all four at once.**

Result 97 ended on "each output path is its own reading". The stronger version is to ask whether the
paths *agree*, and that is mechanically checkable — they take the same arguments and return the same
shape.

**Scoring agrees exactly.** Library `score_text` against `POST /score`, same text, defaults:

```
field              library    REST
tier               full       full
max                0.7253     0.7253
mean               0.3524     0.3524
flagged            True       True
verdict_threshold  0.3        0.3
detectors          same four names
warning            same string
```

MCP's `score` declares the same defaults in its own signature. Nothing to fix — earlier work on that
surface holds.

**Humanizing did not.** Comparing declared defaults across the three:

| param | library | MCP | REST |
|---|---|---|---|
| `rewriter` | **None** | `"composite"` | `"composite"` |

`get_rewriter()` with no preference returns `None` unless a key or a local policy is configured, so:

```
untell humanize        composite   works
MCP untell()           composite   works
POST /humanize         composite   works
untell_text(text)      None        {"error": "no rewriter configured"}
```

The library entry point is the one a Python user reaches for first, and it was the only one that
refused on a fresh install. MCP and REST were each changed to default to `composite` earlier, and
their own comments record the reason in almost these words — *"the flagship tool failed out of the
box while the identical CLI invocation worked"*. The argument had simply never been carried back to
the library.

**The fix is in the caller, not in `get_rewriter`.** That function answers "is a HOSTED or
local-policy rewriter configured", and `None` is the correct answer to that question — the test
pinning it stays. What was wrong is `run.py` reading that as "no rewriter exists" when `composite`
is always available, free, and the documented zero-dependency path. It now falls back, and says so
once on stderr: a caller who set a key and expected the hosted rewriter needs to know it was not
reached, which is the failure mode this log keeps finding on other surfaces.

**And a second divergence one layer up.** `--rewriter auto` is in the CLI's advertised choice list
and the CLI translates it to `None` before calling the loop. Nothing else did, so a caller who read
the CLI help and passed `rewriter="auto"` to `untell_text` got

> *rewriter 'auto' is not available — check the name*

about the one value the documentation calls the default. Accepted as a synonym now, with a
guard-the-guard test that an unknown name still fails — the fallback is for "choose for me", not for
a backend that is not there.

Worth keeping: **a default is part of an interface, and four interfaces to one function means four
places for it to drift.** Both defects here are the same shape as the MCP ones fixed earlier, found
by putting the four signatures side by side rather than by reading any one of them.

## Result 99

**Removing an error path exposed three things that had been leaning on it.**

Result 98 made `untell_text` fall back to `composite` instead of returning `{"error": "no rewriter
configured"}`. That error was load-bearing in ways nothing recorded, and the failures that followed
were all more interesting than the change itself.

**One: an eval baseline that measured the machine, not the corpus.** `test_baseline_without_rewriter`
asked for `rewriter=None` and asserted `rewriter_available is False` — which held only because the
loop refused when nothing was configured. So the same command produced a baseline-only report on a
developer box and a full before/after report in CI, and the difference was an environment variable.
A baseline is now requested with `max_iters=0`, which says what it means and answers the same
everywhere.

**Two: `rewriter_available` never measured what it says.** It is `rewrote > 0`, and `rewrote` was
incremented on every result that carried a `post` — which is every result that did not error. It
counted **loop invocations**, and was accidentally correct only because the one error path it cared
about returned no `post` at all. The moment that path became a fallback, a `max_iters=0` baseline
started reporting `rewriter_available: True`. It now counts a result that reports rewrites or whose
text actually changed.

**Three: `post_flagged_rate is None` was an artefact of the same error.** A baseline run now reports
post == pre, which is strictly more useful — it shows the loop ran and changed nothing — and is the
same shape as every other run, so a caller does not special-case it.

**And a fourth, from a change another session made in parallel.** Warnings are now merged into one
field, so two tests asserting `result.get("warning") is None` began failing on a caveat that has
nothing to do with what they test. `is None` had meant "nothing to report about scrubbing" and
silently became "nothing to report about anything" — a much stronger claim than either test makes.
Both now assert the absence of the specific caveat.

Worth keeping: **an error path is an interface, and things lean on it.** Four separate assertions
here were reading "this run errored" as a proxy for something else — no rewriter configured, no
rewrite performed, a baseline was requested, no caveats apply. None of them said so, and each was
correct until the day the error stopped happening. When an error becomes a fallback, the search is
not for callers of the error but for **tests that were quietly using it as a signal**.

## Result 100

**A sweep that reported three dead knobs, all three of which work.**

The defect class is real and this repo has had it repeatedly: five guards that "declined the job
they exist to do", four style flags that could not change the output at any seed, a fronting budget
permanently full. So sweeping every knob of `untell_text` and asking whether each can change a run
is an obvious check to want.

The obvious version of it is wrong. One seed, one fixture:

```
threshold=0.9          changes the run
max_iters=3            changes the run
best_of=1              changes the run
polish=True            changes the run
style=academic         changes the run
style=casual           NO EFFECT
margin=0.2             NO EFFECT
scrub=False            NO EFFECT
rewriter=surgical      changes the run
rewriter=structural    changes the run
rewriter=targeted      changes the run
```

Three findings, none of them a finding:

- **`style` sets rates.** At one seed the styled and unstyled paths can coincide. Over 40 seeds,
  `casual` differs on 3 — which the existing style tests already record as its genuine weakness, and
  which is not the same claim as "inert".
- **`margin` decides nothing unless the text would otherwise PASS.** The sweep ran at
  `threshold=0.0`, where nothing can ever pass, so there was no borderline pass to withhold. Given a
  threshold that straddles the measured score — 0.8225, threshold 0.873 — it is unambiguous:
  `margin=0.00` stops at `passed` with **0 iterations**, `margin=0.10` runs **1**.
- **`scrub` only matters when something is hidden.** On clean text it is a no-op by construction.
  With zero-width characters injected: 0 survive with `scrub=True`, 3 with `scrub=False`.

Every knob works. The check is now a test that builds each knob's condition and says in its docstring
which one, so the next person to run the naive version finds the answer instead of the false
positive.

Worth keeping: **"this knob does nothing" and "my fixture does not exercise this knob" produce the
same reading, and the second is far more common.** The discipline that separates them is the same
one that has been paying all session — construct the condition the thing responds to, then check.
Three false positives in one sweep is a high enough rate that the sweep would have been actively
misleading shipped as-is: a future reader deleting `margin` on its evidence would have removed a
working feature.

## Result 101

**Running the README instead of reading it.**

`untell-audit` verifies the repo's *numeric* claims. Nothing verifies its *behavioural* ones — a
README that says "type this and get that" is a promise no check tests. So: extract every `untell`
command from the README's fenced blocks and run it.

Thirty candidates, thirteen of them offline and safe to run here. All thirteen work:

```
untell humanize                   rc=0
untell humanize --rewriter surgical    rc=0
untell humanize --rewriter ensemble    rc=0
untell score / tells / loop (alias)    rc=0
untell verify --file                   rc=1   <- correct; documented as "exit 0 = all pass"
untell-score / -loop / -tells          rc=0
untell-verify                          rc=1   <- same contract
```

The `verify` exit codes are the documented contract, not failures, and checking that they are the
documented ones rather than assuming is the whole reason to run the commands.

**Two things the run surfaced that reading could not.**

`untell-humanness` and `untell-audit` are declared in `pyproject.toml` and were **not present in the
virtualenv** — 13 of 23 console scripts installed. That is a stale editable install rather than a
repo defect: the other ten entry points were added after the last `pip install -e`. Worth knowing
anyway, because a user who installed once and pulled since is in exactly that state, and the failure
they see is `command not found` with no hint that a reinstall is the fix.

And it raised the question that mattered: **do all 23 entry points actually resolve?** They do —
checked by importing each module and confirming the named attribute exists and is callable.

**The existing packaging test could not have caught it if they did not.** It checks that each
script's module NAME sits inside a declared package, which is textual. It passes for
`untell-voice = "untell.scripts.voice:main"` after `main` is renamed, after the module stops
importing, and after the attribute becomes a constant — three states that install cleanly and fail
the first time a user types the command. That is now a companion test, confirmed to catch all three
by planting each one.

Worth keeping: **the failures that reach users live between the declaration and the code.** Every
test in this repo imports the package the way a developer does; nobody was checking the way a
`pip install` does. The check costs one import per entry point and covers the entire gap between
"the repo works" and "the install works".

## Result 102

**The attack this repo ships can produce a word its own warning cannot see.**

`untell.attacks` was the last unread module. Two probes:

**Invisible characters — nothing to fix.** Nineteen distinct zero-width, directional, and exotic
space characters, one at a time: zero-width space/joiner/non-joiner, word joiner, soft hyphen, BOM,
LTR and RTL marks, directional overrides, non-breaking and narrow and hair spaces, en quad,
ideographic space, Mongolian vowel separator, invisible times, function application, and a Unicode
tag character. **All nineteen counted by `count_hidden` and removed by `scrub_hidden`.**

**Homoglyphs — a gap, and it took a second look to see it.** `homoglyph_substitute` on a 90-character
sentence replaced 34 characters, and `score_text`'s warning appeared not to mention it. That reading
was wrong: warnings are merged into one field and I had truncated the display at 100 characters. The
homoglyph caveat was there, at the end.

What *is* real is what the caveat counts. It flags words containing **both** Latin and Cyrillic/Greek
letters — the signature of a partial substitution. A word where every letter was replaced mixes
nothing:

```
"саре"   c, a, p, e all Cyrillic, renders as "cape"   ->   no warning
```

That word carries exactly the risk the warning exists for. The score is unaffected — the detectors
normalise confusables, measured at 0.0000 movement — but the substitution is still in the text and
another tool may not normalise it.

**The rule has to be confusability, not script.** Flagging any non-Latin word would fire on a
Russian quotation inside an English document, which is ordinary multilingual text, and would tell
someone to `untell scrub` their own quotation. A converted word is one whose every letter has an
ASCII lookalike — tested against `unicode_tricks._UNHOMOGLYPH`, the scrubber's own map, so the
detector and the remedy cannot drift apart. Verified in both directions: `саре` and a partly
converted `cаpe` both warn; plain English, Russian `привет`, Greek `λογος` and Bulgarian `читалище`
do not.

**And the test taught me the invariant.** The first version asserted that every convertible word
converts fully, and failed on three of five — correctly. `space` cannot be fully converted, because
`s` has no homoglyph in the emit map, so it comes out mixed, which is what the original branch was
for. The invariant worth asserting is not that words convert fully; it is that **nothing the attack
emits escapes both branches**. A further test asserts every value in the emit map appears in the
scrub map, so an attack this repo performs cannot become invisible to this repo.

Worth keeping: **a tool that ships an attack owes its own detector the same coverage.** The gap was
not in the attack or in the scrubber — both handle the fully converted case correctly — but in the
warning that tells a user the text still contains one. Three components, and only the one nobody
tested against the attack's own output had the hole.

## Result 103

**The report a user reads claimed 61% of words changed. The real figure was 2.9%.**

`rich_output` renders the before/after view of every `untell humanize` run — the single most-read
output this tool has, and the one that answers *"did it rewrite my paragraph or edit it?"*

`_diff_words` was not a diff. It compared word *i* of the original against word *i* of the rewrite:

```python
for w in a_words:
    if b_idx < len(b_words) and w == b_words[b_idx]:   # same position, same word -> unchanged
    else:                                              # anything else -> mark it changed
```

That is correct only when the rewrite preserves word count exactly. One insertion shifts every
following word out of alignment, and each one is then compared against its neighbour and painted.
MEASURED on a seven-word sentence:

| edit | words marked changed |
|---|---|
| one word inserted at the front | **7 of 8** |
| one word inserted mid-sentence | 6 of 8 |
| one word deleted | 5 of 6 |
| one word substituted | 1 of 7 — the only shape it got right |

And the shape it got right is the one the rewriter almost never produces. `composite` inserts
openers, deletes transitions and splits sentences on nearly every run. MEASURED over **17 real
rewrites** of HC3 paragraphs:

```
words the report marked as changed
   positional zip   61.2%
   difflib           2.9%
```

**A 21x overstatement, arguing against the thing the tool exists to demonstrate.** The whole claim of
a detector-feedback loop with meaning gates is that it makes small, targeted edits. The report was
telling every user it had rewritten two thirds of their paragraph.

A second defect in the same function: a deleted word appended a bare space. So a dropped clause left
**no trace at all** in the report — and "did the rewriter drop my content?" is one of the questions
that view exists to answer. Deletions now render struck through, showing what was cut.

`difflib.SequenceMatcher` is stdlib, so the fix costs nothing on the zero-dependency tier.

Two notes on the tests, both cases of my own bookkeeping being wrong rather than the code:

- Two assertions failed because `difflib` emits contiguous **runs** — a four-word replacement is one
  span, not four — so a set built per span held `"epsilon zeta eta theta"` as a single element. That
  is better output; the classifier was counting the wrong unit.
- The guard-the-guard matters more than usual here. A diff that marked *nothing* would pass every
  accuracy test in the file, and "the report is now silent" is a worse failure than the one being
  fixed. An unrelated rewrite must still come back mostly marked.

Worth keeping: **the code that displays a result is as capable of being wrong as the code that
computes it, and nobody tests it.** Every measurement in this log has been about what the loop does.
This one was about what the loop *says* it does, and it was off by a factor of twenty in the only
place a user looks.

## Result 104

**Two surfaces read the same text and disagreed about whether it could be read at all.**

`languages.py` and the rest of the display layer were the last unprobed modules. Script detection is
sound — Han, Hiragana, Hangul, Cyrillic, Arabic, Hebrew and Greek all identified, and a
mostly-English passage quoting Chinese correctly keeps its English catalogue. What it does with text
that has **no letters** is not:

```
empty string        script=Latin   catalogue=English
punctuation only    script=Latin   catalogue=English
digits only         script=Latin   catalogue=English
```

`_language_supported` compares Latin letters against non-Latin ones and returns True when there are
no non-Latin ones — which is exactly the letterless case, since digits and punctuation are neither.
MEASURED on `... --- !!! ??? ;;; ::: ,,,`:

```
tells 7   by_category {'rule_of_three': 1, 'semicolon_crutch': 6}   words 0
```

**Six "semicolon crutches" in `;;; ;;;`.** A semicolon crutch is a prose habit. There is no prose —
`words` is zero, `matches` is empty, and the total does not reconcile with its own breakdown. The
catalogue was matching its punctuation patterns against punctuation and reporting the result as a
finding about writing.

And `humanness` returned **50.0 — undetermined —** on every one of these inputs. Two surfaces, one
text, opposite answers about whether it is readable. The CJK case had already been fixed to report
`language_supported: False`; letterless text is the same situation and reached the opposite verdict
through a branch that never considered it.

**The message needed the same fix as the verdict.** With `language_supported` corrected, the warning
read *"the text is mostly non-Latin script"* — true of a Chinese paragraph, false of `;;; ...`, which
has no script at all. That is precisely the defect fixed earlier when a 40-character Chinese
paragraph was reported as "shorter than 5 words": the right verdict for the wrong stated reason,
which sends the reader at the wrong fix. Both branches now name their own cause.

The tells are caveated, not suppressed. Hiding them would be a second wrong answer, and a caller who
wants the raw pattern count can still have it.

**One existing fixture moved rather than being deleted.** `""` sat in `test_tells.py`'s list of
"English text stays supported" cases. An empty string is not an example of English, and calling it
supported is the same claim that let punctuation report six semicolon crutches — so it moved to the
new file with a note saying why, rather than being quietly dropped from a list it was failing.

Worth keeping: **when two surfaces disagree about the same input, one of them is wrong and neither
will tell you.** `humanness` and `score_tells` had disagreed about letterless text for as long as
both have existed. Nothing failed, because nothing compares them — the same shape as Result 98's four
surfaces, on a question about the input rather than about the defaults.

## Result 105

**Any three-digit number in an error message made a permanent failure look transient.**

`_retry.py` already carried two documented fixes, which is usually a sign a module has been looked
at. What it had not been asked is whether its *classification* is right, and the way to ask is to
hand it messages providers actually emit.

`_is_retryable` read status codes with a bare `\b([1-5]\d{2})\b`. MEASURED against nine realistic
non-retryable messages, **four were retried**:

```
invalid_request_error: max_tokens must be <= 500
context length 502 tokens exceeds the 500 token limit
ValueError: expected 429 items in the batch, got 12
invalid parameter: timeout must be a positive number
```

The first three are configuration mistakes: three attempts with exponential backoff for an answer
that cannot change, multiplied by best-of-N draws across iterations. The fourth is worse — a bug in
our own call, masked by retrying it.

**Tightening broke the other direction twice**, which is the part worth recording. Requiring a word
boundary before the keyword lost `HTTPError: 500` and `APIStatusError: 500`, where there is no
boundary inside the token. Requiring the code at the head of the message lost
`(429) rate_limit_exceeded`. Both were caught only because the genuine-retryable list was checked as
carefully as the false-positive list on every iteration — a rule that is getting stricter is exactly
when the other side breaks, and a one-sided check would have shipped a classifier that never retried
an SDK exception.

**And the tightening surfaced a gap in the code set itself.** Checking
`anthropic.APIStatusError: 529 overloaded` failed — not because of the regex, but because **529 was
not in `_RETRYABLE_HTTP`**. That is Anthropic's capacity code, on a package that ships an Anthropic
rewriter: the provider whose overload signal we would see most often was the one not retried. 408
Request Timeout was missing for the same reason — the set had been built from the familiar 5xx
family and 429.

Final: **15 of 15** transient messages retried, **13 of 13** permanent ones refused on the first
attempt.

**Then the suite failed, and the failure was the biggest finding of the three.**
`test_retry_exhausts_on_persistent_error` raises `TimeoutError("timeout")`, which had been matching
on the bare `timeout` keyword in its message. With the keyword tightened it stopped — and the class
check did not catch it either, because `_RETRYABLE_ERRS` contains the string `"Timeout"` and the
builtin is named `TimeoutError`.

Pulling on that exposed a pre-existing hole the whole time. The class set matches by NAME, so it
misses every subclass:

```
ConnectionError          retryable
ConnectionResetError     NOT retried
ConnectionAbortedError   NOT retried
ConnectionRefusedError   NOT retried
TimeoutError             NOT retried
BrokenPipeError          retried — only because its default message says "broken pipe"
```

`ConnectionError` is in the set and is a base class **nobody raises directly**. The three subclasses
that are actually raised — reset, aborted, refused — are the commonest transient network failures in
Python, and all three were reaching the classifier through their message text or not at all. Change
`BrokenPipeError`'s message and it stops being retryable.

Matched by type now, with the name set kept for third-party SDK exceptions that cannot be imported
without depending on them. `PermissionError` and `FileNotFoundError` are `OSError` subclasses and
stay refused, which is what a type check written one level too high would have broken.

Final: **15 of 15** transient messages retried, **13 of 13** permanent refused, all six builtin
transient exceptions retried, five builtin permanent ones refused.

Worth keeping: **a set that looks complete is complete for the cases you thought of.** `{429, 500,
502, 503, 504}` reads as the canonical retryable list and is, for a generic HTTP client — the gap
opened where this package stopped being generic. And matching exceptions by name reads as
equivalent to matching by type until you notice that the entry in the set is the one class the
runtime never hands you.

## Result 106

**The measurement tool is correct and its report contradicts itself.**

`eval/detector_audit.py` produces every AUROC claim in this repo, so the first question is whether
its primitive is right. It is, exactly:

| case | `auroc` |
|---|---|
| perfect separation | 1.0 |
| perfect inversion | 0.0 |
| all tied | 0.5 |
| either side empty | `None` |

and it matches `sklearn.metrics.roc_auc_score` to within 1e-9 on five random 40-versus-40 trials.
Ties counted as half, threshold-free. Nothing to fix in the number that everything else rests on.

**The report built from it does not read as consistent.** The smoke run prints:

```
fast_detectgpt [sentence]  INVERTED  0.444  0.355  0.212  -0.142  67%  33%
...
BROKEN: none — every available detector responds in the correct direction.
```

Both lines are correct. Sentence rows are deliberately held to `AUROC <= 0.20` before counting as
broken, and the reason is written down beside the list: six probes per class is 36 pairs, 0.444 is
chance, and the same detector scores **0.915 on 40 real HC3 sentence pairs**. Gating CI on the smoke
number would turn the build red over sampling. That judgement is right.

But a reader sees `INVERTED` four lines above `every available detector responds in the correct
direction` and cannot reconcile them without opening the source — and the summary is the line people
quote. It now names what it excluded and why, with the bar stated rather than referenced.

This is the third instance in this log of one shape: **a value that is true about its own computation
and misleading beside the data it is printed next to.** `mode()` reported what `_torch_ready()`
predicted rather than what ran; `rewriter_available` reported that a loop had returned rather than
that a rewrite happened; and here a summary reports its own filtered list beside the unfiltered
table. Each was defensible in isolation and wrong in context.

The guard-the-guard matters more than usual: an AUROC of 0.000 on the same 36 pairs is a **real**
inversion — chance cannot produce it — and must stay in the broken list. A caveat that excused
everything would turn the small-sample allowance into a way to hide the defect it exists to
contextualise.

Worth keeping: **check what two lines say together, not what each says alone.** Every reporting
defect found in this session — the 61%/2.9% diff, the mode label, this — survived because each
component was individually defensible. Nothing in a per-function review reads two lines at once; only
running the thing and looking at the output does.

## Result 107

**Reading every report in turn, and the two that reconciled.**

Result 106 named the method: check what two lines say *together*. Applied to each reporting surface:

- **`score`** — coherent. `max 0.6091` against `verdict_threshold 0.45` gives `flagged: true`, and
  the two thresholds it carries (0.30 loop, 0.45 verdict) are both present with a warning saying
  they answer different questions. `detector_modes: stdlib` matches the caveat about that path.
- **`tells`** — coherent, and reconciles three ways: `AI-tells: 2` equals `by evidence: moderate 1,
  weak 1` equals `by category: formulaic_transition 1, ai_vocab 1`.
- **`verify`** — did not.

The verify table prints:

```
  local:perplexity_burstiness AI=0.609  [FAIL]
  local:max (lite)            AI=0.609  [FAIL]

FAILS — 0/1 checkers passed
```

Two rows, denominator of one. And in the JSON, `configured` lists **two** names while
`n_configured` says **one** — two fields describing the same thing, disagreeing.

The count is right, and deliberately so. `local:max` is an aggregate of the local detectors rather
than an independent checker, and the comment beside its exclusion records the bug that motivated it:
*"two of five passing were reported as 2/5 checkers passed, and a run with one local detector read
as 1/2"*. What a reader had no way to tell is which of the two rows is not a checker.

Marked now, and asserted as an invariant rather than as a string: **rows shown, minus rows marked as
aggregates, equals the number the summary divides by.** `passes_all` is untouched and still computed
over every row — the max is below threshold exactly when every local detector is, so including it
cannot change the verdict.

Worth keeping: **two of three reports reconciled, and finding that out cost one command each.** The
value of reading them all is not the hit rate; it is that "this report is fine" stops being an
assumption. `tells` reconciling three different ways is now a fact rather than a hope, and that is
the same kind of result as the defect.

## Result 108

**The Verdict row was labelling P(AI) with a calibration fitted to a different metric.**

Continuing to read reports. The humanize table is otherwise sound — the arithmetic reconciles
(`0.49 → 0.15`, delta `-0.34`), the header's iteration count matches the row, the Original and
Humanized panels match the diff, and a run that changes nothing says so. One row does not.

```
│ P(AI) max  │ 0.49    │ 0.15   │ -0.34 │
│ Verdict    │ mixed   │ human  │       │
```

`0.49` is above the `0.45` verdict threshold, so `flagged` is **true** for that number — while the
row beside it says *mixed*.

The cause is a scale borrowed from elsewhere. The row called `classification((1 - p_ai) * 100)`, and
`classification`'s boundaries are fitted to `humanness()` scores specifically. Its own docstring
gives the fit: *"lowest HUMAN score 75.6, highest AI score 72.0 ... a boundary at 75 misclassifies 0
of 80."* Those numbers describe `humanness()`. `(1 - P(AI)) * 100` is a different quantity.

MEASURED on 60 HC3 and RAID texts, comparing `classification(humanness(t))` against
`classification((1 - max) * 100)`:

```
labels agree on 18 of 60 — 30%
```

**`untell humanize` and `untell humanness` disagreed about the same paragraph seven times in ten**,
through the same labelling function, because they fed it different quantities.

The row sits directly under `P(AI) max` and glosses it, so it is now labelled against
`verdict_threshold` — the cut that decides `flagged`, and the only calibrated decision this repo
makes about that number. The two can no longer disagree.

**The comment above the old code was recording a real earlier fix**, and that is the part worth
keeping in view. Passing P(AI) in raw put every value under the bottom band, so the row printed
"AI" → "AI" for every input, including a run that took 0.86 down to 0.02 — *"not merely wrong, it was
constant"*. The repair rescaled the input into a calibration that did not apply, which replaced a
constant with a mislabel. The test therefore asserts both properties: the label follows the
threshold, **and** the row discriminates at all, because a regression to any constant would satisfy
whichever equality case happened to match it.

Worth keeping: **a fix that removes the symptom can install a subtler version of the same fault.**
"The row is constant" and "the row uses the wrong scale" are both failures of the same thing — the
label not being derived from the number beside it — and the first repair addressed the appearance
rather than the derivation. The question that separates them is not "does this look right now" but
"what is this value computed from, and is that the quantity being displayed".

## Result 109

**The Claude skill works end to end, and the gates it runs are complementary in a way nothing had
written down.**

`untell/SKILL.md` is a shipped surface making behavioural claims that no check verifies — it
instructs Claude to run twelve scripts by path (`python scripts/preserve.py …`) rather than through
the console entry points, so none of the packaging work covers it. Run:

- All twelve referenced scripts exist and execute standalone.
- The pipeline round-trips: `scrub` → `preserve` masks `Smith (2020)` and `47%` behind sentinels →
  the gates run on the masked pair → `preserve --restore` returns both verbatim.
- `sentences` prints its own AUROC caveat to stderr on the stdlib path, as it should.

Nothing to fix. Which left the more interesting question: the skill runs the gates as five separate
scripts, and the loop calls them as one conjunction. Do they agree, and does the conjunction earn
its complexity?

```
pair             sim    passes  numbers  polarity  certainty  roles  contradicts
faithful         0.877  True    True     True      True       False  False
number changed   0.848  True    False    True      True       False  True
negated          0.726  False   True     False     True       True   True
hedge dropped    0.989  True    True     True      False      False  False
role swapped     0.988  True    True     True      True       True   False
unrelated        0.000  False   True     True      True       False  False
```

**Similarity alone would let four of six through.** A changed number scores **0.848**, a dropped
hedge **0.989**, a swapped role **0.988** — all comfortably above the 0.76 bar, and each is a
different kind of lie about the source. `47%` becoming `74%`, "may improve" becoming "improves", and
the compiler and parser trading places are invisible to a cosine.

And the converse is why similarity stays. An unrelated paragraph **contradicts nothing** — NLI is
right that rainfall does not contradict frameworks — and every lexical gate passes it, because
nothing was dropped or negated. Only similarity catches that one. Dropping it as the weakest gate
would open exactly that hole.

Each gate was already tested alone. What was not written down is the claim those tests add up to,
which is the argument for having five: **every gate is the only one that catches its own class, and
one of them catches a class none of the others can see.** That is now a table in a test rather than
a design intention.

Worth keeping: **a conjunction of guards needs a test that each conjunct is load-bearing.** Five
gates that all fire on the same defects would be four gates of theatre, and nothing in a per-gate
test suite can tell the difference — every one of them passes either way. The distinguishing
measurement is the cross-product, and it takes one table.

## Result 110

**The catalogue and the detector that implements it had never been compared.**

`untell/references/ai-tells.md` is the tell catalogue; `untell/scripts/tells.py` implements it. A
documentation/implementation pair, and nothing checked they agree. The doc's headline section lists
"the 20 highest-signal tells", so: write a textbook example of each and run it.

**The first pass measured the wrong thing**, in a way worth recording. I appended a shared padding
sentence to every probe and accepted "any category fired" as a hit, which gave 18 of 20. Both
choices were wrong: the pad changed sentence-length variance, so the burstiness probe was measuring
my padding, and five "hits" had fired only on `low_burstiness` rather than on the tell being tested.
Re-run with no pad and requiring the tell's **own** category: **13 of 16** that name a detector.

The three that did not are all documentation mismatches rather than dead code, and each wanted a
different answer:

**`false_range` missed the catalogue's own quoted example.** Item 17 gives *"from ancient
civilizations to modern startups"*; the pattern required `to the`, and that half has no article. The
scope word at the front is what stops it matching an ordinary range, so the article was carrying no
weight. MEASURED over 120 HC3 and RAID pairs, dropping it changes the counts by **zero in both
corpora** — the shape does not occur there — so closing a documented-example gap cost nothing. Fixed,
with `from Monday to Friday` and `from London to Paris` asserted to stay unmatched.

**`rule_of_three` implements half the item, deliberately.** It detects the staccato form
("Fast. Simple. Effective.") and skips the comma tricolon, and its docstring records why with
numbers: POS-tagging the coordinated items and keeping the adjective runs the catalogue describes
gives RAID 1.04, HC3 2.10, MAGE 0.36 — no signal, inverted on one corpus. The doc lists both forms.

**`markdown_artifact` implements a different tell than the one it is named for.** Item 12 describes
heading and bullet density ("3+ headings in <300 words"); the pattern matches boilerplate section
titles — "Key takeaways", "TL;DR", a heading containing an emoji.

The last two are pinned as **known divergences** rather than fixed. Narrowing the doc would lose real
writing advice — the comma tricolon is a genuine tell to avoid even where detecting it costs more
than it earns — and widening the detectors was already measured and rejected in their own docstrings.
The test asserts they still do NOT fire, so the divergence stays a decision on record: if one starts
firing, the note describing the limit is stale and should go.

Worth keeping: **a doc that guides generation and a detector that measures it will diverge, and the
divergence is only a defect when nobody has written it down.** Two of these three are legitimate —
the catalogue is advice for a writer, the detector is an instrument, and they answer to different
constraints. What was missing was any place recording which items are which, so a reader of either
file would assume the other agreed.

## Result 111

**Five documented constants, all correct, and nothing keeping them so.**

`untell/references/thresholds.md` ships with the skill and is the reference a user reads to
understand what the loop's numbers mean. It is **not in `audit.LIVE_DOCS`**, so neither the claim
check nor the attribution check touches it. Checked by hand against the code:

| doc | code | |
|---|---|---|
| `threshold` `0.30` | `untell_text(threshold=0.3)` | ✓ |
| similarity bar `0.76` embedding | `recommended_bar()` = 0.76, `method()` = embedding | ✓ |
| contradiction `< 0.50` | `DEFAULT_CONTRADICTION_BAR` = 0.5 | ✓ |
| entailment `≥ 0.005` | `DEFAULT_ENTAILMENT_FLOOR` = 0.005 | ✓ |
| relaxed sim bar `0.30` | `RELAXED_SIM_BAR` = 0.3 | ✓ |

All five right today, by nobody's arrangement. Now pinned.

**The test was wrong twice, and both corrections are the point of this result.**

The first version asked whether each value appeared *anywhere* in the document. Its own non-vacuity
probe killed it: of three invented "moved constants", **two — `0.35` and `0.007` — already appear
elsewhere in the file**. The doc quotes 46 numbers, so a threshold drifting to a coincidental value
would have been reported as documented. "Present in the file" is not "documented as this constant".

Anchoring each value to a line mentioning its name fixed that, and introduced the second error. I
anchored the entailment floor on the word **"entailment"** — which also appears in the *quantity
check* row's prose: *"contradiction `0.011`, entailment `0.007` — clearing the floor by `0.002`"*.
So the anchor matched a second row and let exactly the coincidence back in. Both NLI bars live on
the `meaning gate` row, and anchoring there is what actually works.

Confirmed after: four coincidental values, including both that defeated the loose version, are now
caught.

Deliberately not solved by adding the file to `LIVE_DOCS`. That list subjects every numeric claim in
a document to the attribution rule, and this one quotes 46 numbers — most of them measurements from
tables rather than constants. Pinning the five that ARE constants is the part that can drift
silently.

Worth keeping: **an anchor has to name the row, not a word the row happens to use.** Both failures
here are the same mistake at different scales — "somewhere in the document" and "somewhere on a line
containing this word" are both proximity standing in for reference. The check only becomes real when
it points at the thing that defines the value, and finding that out took writing the failing case
rather than reading the passing one.

## Result 112

**The last three unprobed modules, and the one claim among them worth pinning.**

**`browser_check.py`** — sound, and instructively so. `parse_ai_percent` handles 14 of 16 probe
shapes exactly, and both apparent failures are **deliberate refusals in the safe direction**:

- A human-only percentage returns `None`. "Human: 45%" means 45% human, i.e. 55% AI, and returning
  0.45 would hand the loop a verdict wrong in the dangerous direction. Sites word their output
  differently and change it without notice, so an ambiguous readout is refused rather than guessed.
- A negative percentage returns `None`. The digit-only pattern cannot see a leading sign, so
  "-10% AI" once read as 0.10 — a low score, i.e. "looks human".

The asymmetry is stated outright in the docstring: *"A reading that OVER-states AI is safe — the
loop simply keeps rewriting. One that UNDER-states it is how text ships believing it passed."* And
an unparseable page raises a named `RuntimeError` quoting the raw text rather than fabricating 0.5,
with the reason recorded: a fake score enters the numeric list, drives `max()`, and suppresses the
all-checkers-failed flag that exists for exactly that case.

Worth noticing what this costs, since nothing else says it: **the parser can read a failure verdict
but not a success one.** A page reporting only "100% Human written" is unparseable, so the checker
is excluded precisely when the rewrite worked. That is the safe direction — exclusion, loudly — but
it means a browser check can never confirm success on a site that reports only the human share.

**`training/`** — all modules import cleanly.

**`prompt-rubric.md`** — the one testable behavioural claim in the reference docs, and it had no
test. Its first and most emphatic item:

> **Em dashes (`—`).** The single most recognizable AI signature. Do not add them. … If the original
> had one, you may keep it, but never *add*.

`ai-tells.md` calls the em-dash "the most measurable single tell (GPT-4.1 ~10 per 1,000 words)" and
`tells.py` counts it as a category — so an injecting rewriter would have this repo scoring its own
output for a tell it had just added. MEASURED over 80 HC3 and RAID paragraphs through `composite`:

```
hc3    40 texts | em-dash 0 -> 0 (added 0) | semicolon 0 -> 0 (added 0)
raid   40 texts | em-dash 0 -> 0 (added 0) | semicolon 3 -> 3 (added 0)
```

Zero added of either, and the three semicolons RAID's sources carried all survive. Now asserted
across all four CPU rewriters — the layout defect in Result 95 was one backend behaving differently
from the rest, and this is the same shape of question.

The test keeps the rubric's own asymmetry: **keeping** a mark the source had is fine, and a test
demanding removal would push the rewriter into deleting the author's punctuation — a different kind
of damage that nothing here asks for.

Worth keeping: **a rule written for the LLM rewriter is a rule the free rewriters are silently held
to as well.** `prompt-rubric.md` reads as instructions for a model, so nothing thought to check the
deterministic path against it — and that path is the default.

## Result 113

**The settings a user actually runs surface defects one iteration does not.**

Every read so far has been `max_iters=1`, `best_of=1` — the cheapest configuration. The default CLI
is `best_of=3`, and a real run goes to five iterations. Fifteen rewrites per document instead of
one, each transform seeing the output of the last. Read at those settings:

> ...condone the assassination of any individual, **regardless of their actions or beliefs.**
>   →  ...condone the assassination of any individual.
>      **Regardless of their actions or beliefs.**

A fronted adverbial severed into its own sentence.

**Neither existing guard was wrong.** `_orphans_a_subordinate_clause(left)` correctly returned
False — the left half *is* a complete sentence. `_cannot_start_a_sentence(right, left)` returned
False, and that is the one that should have fired: `_CANNOT_OPEN_A_CLAUSE` holds seventeen
prepositions including **`regarding`**, and `regardless` was simply missed.

**But it cannot just be added to that set**, and the reason is the interesting part. That set is
unconditional, and these leads are the one family where the same word opens a fragment *and* a
sentence:

```
Regardless of their actions or beliefs.        fragment
Regardless of the cost, we proceed.            sentence
```

Adding `regardless` there would have blocked the second — trading a fragment for a refused
legitimate split, which is how a guard set accumulates until the transform stops working. What
separates the two readings is whether a **main clause** follows, and a fronted adverbial that has one
is separated from it by a comma. Checked on ten pairs — a fragment and a sentence for each of five
leads — the comma rule splits all ten correctly.

So it is a second set with a condition, and a test asserts the two sets **do not overlap**: an entry
in both is unconditionally blocked, which silently undoes the comma rule while every fragment test
still passes.

Three further defects were visible in the same read and are not fixed here, recorded so they are not
lost: `"Now, when it's used in pairing with other ways, by contrast, salt is..."` stacks two
discourse markers and inserts a contrastive where no contrast exists; `"By contrast, despite these
potential downsides, ..."` stacks a contrastive on a concessive; and `"...for many communities,
especially."` strands a modifier whose complement was moved to another sentence. All three are
compounding artefacts — one transform acting on another's output — which is exactly what more
iterations buys.

Worth keeping: **the cheap configuration is a different program.** Every probe in this log until now
ran one iteration of one draw, because that is fast and deterministic enough to reason about. The
shipped default runs fifteen rewrites per document, and the defects that only appear there are
compounding ones — a transform mangling what another transform produced — which is precisely the
class a single pass cannot exhibit.

## Result 114

**A correction to Result 113, and the defect that was real underneath it.**

Result 113 listed three further defects seen in the same deep read and not fixed. One of them was
not a defect at all, and finding that out is worth more than the note was.

> `"By contrast, despite these potential downsides, ..."` stacks a contrastive on a concessive.

The source already reads **"However, despite these potential downsides, many communities continue to
use salt..."** The stacking is in the original HC3 text. The rewriter substituted `However` →
`By contrast` faithfully and changed nothing about the shape.

I attributed a corpus artefact to the rewriter by reading the output alone. The battery in
`test_output_is_mechanically_sound.py` exists precisely to prevent that — it scores every check on
the OUTPUT **and** the SOURCE and fails only on a positive delta, with a comment saying the corpora
contain their own artefacts. I violated that discipline the moment I read by eye instead.

**The second note was also mine to correct**, in the other direction. `"...for many communities,
especially."` — a stranded modifier — does not come from `structural_rewrite`: across 40 seeds it
never strands `especially`. It appeared only in the five-iteration loop, so it is a compounding
artefact, which is what Result 113 said about the class but not about this instance.

**And chasing that produced a real defect.** The same 40-seed sweep showed what `structural_rewrite`
*does* do to that sentence:

```
used in combination with other methods   ->   used in pairing with other methods
                                         ->   used in mix with other methods
                                         ->   used in blend with other methods
```

`combination` was not in `_PREPOSITION_BOUND`. "in combination **with**" is a fixed frame and none of
its substitutes fit it — the same shape as `approach to`, `reliance on` and `capacity for` already in
that map.

Bound to `with` only, and the measurement is why: across 240 HC3 and RAID texts, `combination`
appears 47 times and **46 of them are "combination of"**, which takes every substitute cleanly ("a
mix of", "a blend of"). Binding the word outright would have cost the common case to fix the rare
one.

Worth keeping: **reading output without the source beside it is guessing.** Two of the three notes in
Result 113 were wrong about where the text came from, and the tool that would have told me — score
the source too, blame only the delta — was already in the repository, written for this exact failure.
The real defect surfaced only when I stopped reading the loop's output and started diffing a single
transform against its own input.

## Result 115

**Every transform diffed against its own input, and the one gap that matters is a tell nothing could
remove.**

Result 114 ended on the method: stop reading loop output, diff a single transform against its own
input. Applied to all eight text-in/text-out transforms in `structural.py`, over 50 HC3 and RAID
documents, scoring damage on the OUTPUT and the SOURCE and counting only the delta:

```
_flatten_cliches                 changed 10/50   stub_sentence: 1
_flatten_copula                  changed  4/50   clean
_flatten_negated_contrast        changed  3/50   clean
_flatten_participial_trailers    changed  1/50   clean
_flatten_vague_attribution       changed  0/50   clean
_parenthesise_asides             changed 18/50   clean
_semicolons_to_periods           changed  0/50   clean
_strip_filler_openers            changed  0/50   clean
```

The one stub is `"In conclusion, TAN represents"` → `"TAN represents"` — the already-documented
truncated-source artefact, not damage.

**The interesting column is `changed 0/50`.** A transform that never fires is not necessarily broken,
so the question is whether the tell it exists to fix is being *detected*. Counting detections against
fixes over 120 texts:

```
vague_attribution    detected in 1 text, flattener acts on 0
semicolon_crutch     detected in 1 text, flattener acts on 1
filler_phrase        detected in 0 texts, flattener acts on 0
```

`vague_attribution` is **flagged and unfixable**. The phrase is *"it is generally accepted"*: the
detector covers `it is (widely|often|generally) (believed|said|understood|accepted)`, the flattener
had only `it is (widely )?believed`. The loop counts the tell, spends a draw trying to remove it,
fails, and scores the result as no better — every iteration.

**The rest of the detector's vocabulary stays out, and that is the measured part.** It also flags
attributed subjects — reports, surveys, analysts, observers, critics, sources — and rewriting
*"Critics argue that X"* into *"Evidence suggests that X"* changes **who said it**. Asked whether the
gates would catch that:

| pair | similarity | contradicts | role_swap |
|---|---|---|---|
| `Critics argue` → `Evidence suggests` | 0.905 | False | False |
| `Analysts say` → `Evidence suggests` | 0.928 | False | False |

**No gate catches an attribution change.** A wider flattener would ship one past every guard this
repository has. The impersonal forms have no attributor to lose, which is precisely why they are the
safe ones to add — and that is a distinction the gates cannot make for you.

**And the widening exposed a defect it would otherwise have shipped.** The substitution was a flat
lowercase string, so a sentence-initial match produced `". evidence suggests"` — caught by the
battery's own `lowercase_after_full_stop` check, firing on the output and not the source. It had gone
unnoticed for the reason the whole result turns on: the transform never fired on real text, so its
one bug was unreachable. Making it reachable and fixing the case belong in the same change.

Worth keeping: **a detector and its remedy are a pair, and only counting them together shows the
gap.** Everything in this repo measures whether a tell is *found*. Nothing measured whether the
matching transform can *act* on what was found, and the two vocabularies had drifted apart with no
test able to notice — each is correct in isolation.

## Result 116

**Every tell category, asked whether anything can act on it.**

Result 115 found one detector without a working remedy by checking three categories. The same
question asked of all of them, over 120 corpus texts — flagged, and does the rule-based rewriter
reduce the count:

```
repeated_phrasing            80 flagged   52 reduced
ai_vocab                     60           60
formulaic_transition         57           52
repeated_sentence_openers    47           17
cliche                       17           17
hedge_stacking                6            5
participial_trailer           4            4
false_range                   2            0   <- never reduced
meta_closer                   1            0   <- never reduced
challenges_section            1            0   <- never reduced
vague_attribution             1            1   <- fixed one result ago
```

Three categories the catalogue counts and no transform touches — confirmed by name: nothing in
`untell/rewriter/` mentions any of the three.

`meta_closer` is the one with an obvious safe action. "I hope this helps!" carries no content, so
removing it is a deletion of scaffolding rather than a rewrite, and every gate agrees: tell 1 → 0,
similarity 0.981–0.997, `passes` True, `contradicts` False, numerals kept.

**Then the transform deleted a paragraph's conclusion.** The corpus's one real instance is

> *"I hope this helps to explain why we might not have high resolution color cameras on some space
> probes and satellites."*

— substance wearing a sign-off as a prefix. Deleting a trailing sentence because the pattern matched
it would have removed the answer to the question the paragraph was answering. **A tell fix that
deletes the user's last sentence is a far worse defect than the tell.**

The remainder is what separates them. Measured over seven sign-offs and three content sentences
beginning with the same phrases:

```
scaffolding remainders   0, 0, 3, 4, 5, 5, 5
content remainders       10, 11, 17
```

Six sits between the groups with margin. The evidence is thin — one of those content sentences is
real and the rest are constructed — so the constant is documented as something to re-measure if a
document ever loses a sentence it should have kept, not as a fitted value.

**And the sweep still reports `meta_closer` 1 flagged, 0 reduced — correctly.** That instance should
not be reduced. What looked like a missing transform turned out to be, for the only case the corpus
actually contains, a **detector false positive**. The gap was real and the evidence for it was not
evidence of what it appeared to be.

Built on `tells._META_CLOSER_RE` rather than a second pattern, because the defect one result earlier
was exactly two vocabularies drifting apart.

Worth keeping: **"the rewriter cannot fix this tell" and "this tell should not be fixed here" produce
the same number.** The sweep column that found a real gap in Result 115 pointed at a false positive
in Result 116, and only opening the actual text distinguishes them. A count of unfixed detections is
a place to look, never a verdict.

## Result 117

**The largest gap in the sweep was not a missing transform. The detector fires on a share and scores
a count.**

Result 116 chased the three categories at zero. The biggest absolute gap was elsewhere:
`repeated_sentence_openers`, 47 texts flagged and 15 reduced. Opening the other 32 showed the
repeated openers are *the*, *in*, *we*, *our* — ordinary function words, not the AI markers
`_vary_openers` targets. That much was expected. The numbers next to them were not.

`_duplicate_sentence_starts` fires when duplicate openers reach **40% of sentences** and then returns
the **raw duplicate count**. A rewrite that adds sentences grows the denominator. Over the 47 texts
that fire — sentence count changed on 34 of them:

```
share improved, count did not fall     15
share worsened, count did not rise      0
the two agree                          32
```

~~One row carries it: **share 70.0% → 53.8%, count 7 → 7.** A sixteen-point improvement on the
detector's own criterion, scored as no change at all. Nearly a third of the texts where this tell
fires get no credit for a real improvement.~~

~~**The error is one-directional, and that is the whole reason it stays.** Fifteen cases hide an
improvement; zero hide damage. The loop under-credits a good rewrite and is never fooled by a bad
one — the safe side of the ledger.~~

> **Correction ([Result 118](#result-118)):** there was no improvement to credit. On that row the
> duplicate openers are 7 before and 7 after — the share fell only because the rewriter added three
> sentences. Across the cases, 14 of 18 have identical repetition before and after and 4 got
> genuinely worse while the share said better. The count was right and the share is the confounded
> number. Everything below stands; the framing above does not.

**The obvious fix was built, measured, and reverted.** Reporting the excess above the threshold
(`dupes - ceil(0.40 * n)`) compresses the magnitude out of the signal:

| variant | RAID AUROC | HC3 AUROC |
|---|---|---|
| shipped, raw count | **0.9555** | 0.8696 |
| excess, floored at 1 | 0.9381 | 0.8738 |
| excess, unfloored | 0.9336 | 0.8756 |

A residual above a threshold is nearly binary, and that is what costs the RAID AUROC. The unfloored
variant has a second defect: a text can sit above the 40% bar and report 0, so the detector fires and
contributes nothing — the criterion-disagrees-with-value defect relocated. (The share-based columns
this table originally carried have been dropped; see the correction above.)

**And the guard for it was vacuous on the first attempt.** The test meant to reject the excess
variants compared a repetitive text against a sparse one — and the sparse one was under the 60-word
repetition floor, so it scored 0 under every variant and the comparison decided nothing. It passed
under the fix it existed to reject. Replaced with a direct assertion that the reported magnitude *is*
the duplicate count, which fails under both variants; verified by running the suite against each.

Worth keeping: **the size of a gap says nothing about where the defect is.** Three categories at zero
turned out to be one real gap, one detector false positive and two by-design. The category with the
largest gap had no rewriter defect at all — ~~the tell was being reduced and the number could not
show it~~ **and no detector defect either; see the correction above.**


## Result 118

**I read the disagreement backwards. Density fell; repetition did not.**

Result 117 found `repeated_sentence_openers` firing on a share and scoring a count, and called the
gap between them a blind spot that hid real improvements. The next category checked is what showed
that was wrong.

`_repeated_trigrams` is built identically — fires at 5% of tokens, returns the repeat count — so the
same three-way table should apply. It does, pointing the other way: over the 80 texts it fires on,
the share worsened without the count rising **8** times against **2** the other way. Opening those 8
settles it, because the repeat counts are printed beside the shares:

```
share 10.05 -> 10.34 | words 209 -> 203 | repeats 21 -> 21
share 15.95 -> 16.25 | words 163 -> 160 | repeats 26 -> 26
share 16.35 -> 16.61 | words 312 -> 307 | repeats 51 -> 51
```

**Identical repeats in every one.** The rewriter deleted filler; nothing repeated more than before.
The share rose because the denominator shrank.

Going back to Result 117's cases with the same column added:

```
duplicate openers IDENTICAL before and after    14
duplicate openers actually ROSE                  4
```

The row I quoted as the headline — share 70.0% → 53.8% — is **7 duplicate openers before and 7
after.** Not one repetition removed. The rewriter added three sentences with fresh openers and
diluted the ratio. And in 4 cases the share reported an improvement while the repetition got worse,
the clearest being 14 sentences with 8 duplicate openers becoming 18 with 10.

So the shipped count was never a defect. **A share measures density, a count measures incidents, and
a rewriter changes the denominator of the first by construction** — it adds sentences and deletes
words. The trigram docstring had already worked this out for its own metric, recording that roughly
40% of that tell's raw AUROC was length rather than style. Both repetition detectors report counts
for the same reason, and I spent a result treating that as a bug.

**The trigram docstring did have a real defect, in its first line.** It described the return as
*"a share of its tokens (percent, floored)"* while the code returns the raw count, and the line
*"counted once per repeat"* four paragraphs down says so. A 150-word text with 143 repeats returns
143, not 95. Three descriptions, two of them right, in one docstring. Fixed and pinned with an
assertion that the value exceeds 100 on that text, which no percentage can.

Worth keeping: **when two measurements of the same thing disagree, the reason to prefer one is not
which moved in the direction you expected.** I had the per-item record available in Result 117 —
sentence counts were right there in the output — and read the aggregate instead. One extra column,
the raw incident count, inverts the conclusion.

## Result 119

**The tells catalogue beats counting words by 0.025 on RAID.**

Result 118 ended on a rewriter changing the denominator of a density. The same question asked of the
headline metric: `tells_per_100w` divides by words, so it looks length-controlled. It is not — the
two repetition categories only fire above thresholds a longer text crosses more easily, and the rate
climbs steeply with length. Measured on RAID+HC3 AI text:

```
under 150 words     3.68 tells/100w
over  250 words    12.33 tells/100w
```

So the catalogue was measured against the dumbest competitor available, `len(text.split())`, at 200
pairs per corpus:

| corpus | catalogue AUROC | word count alone | margin | AI words | human words |
|---|---|---|---|---|---|
| RAID | 0.9555 | **0.9303** | **+0.025** | 285.9 | 194.6 |
| HC3 | 0.8696 | 0.6922 | +0.177 | 190.1 | 184.9 |

**Fifteen categories, five hundred-odd patterns, two repetition statistics and a burstiness
coefficient beat a word counter by two and a half points on RAID.** Its AI halves are 47% longer
than its human halves, and that asymmetry is most of what the headline number reports.

HC3 is the control that makes this a finding rather than a corpus complaint: near-identical lengths,
and there the same catalogue earns +0.177. Same code, opposite readings.

**Truncating both halves to a fixed window was tried first and does not answer the question.** RAID
lands at 0.619 / 0.695 / 0.815 for a 120 / 150 / 180-word window — a wider window removes less of the
asymmetry *and* hands the repetition tells more text to fire on, so the two effects run in opposite
directions and no single window is the honest one. The word-count baseline needs no truncation,
discards no pairs, and is not a control so much as a competitor.

`eval/tells_auroc` now prints it on every run beside the mean word counts, with a NOTE when the
margin falls under 0.10 — a floor the two corpora sit either side of by a wide margin, so it is not
doing discrimination it cannot support.

Worth keeping: **a separation number means nothing without the dumbest baseline printed beside it.**
This module was built precisely so the catalogue's AUROC could not go stale in a comment, and it
reported 0.9555 for months. The number was correct. What it measured was mostly that RAID's machine
half is longer.

## Result 120

**The headline score depends on how much you paste, and its "cannot tell" answer is also a real
answer.**

Result 119 found the tell rate climbing with length. `humanness` weights that rate at 0.30, so the
next question is whether the user-facing number inherits it. Measured by truncating 24 corpus texts
of 220+ words to a series of windows and comparing each against its own 220-word score:

```
window            60w    100w   140w   180w
mean |delta|      8.9     7.3    5.1    2.5
max  |delta|     21.1    23.4   22.8    9.4
```

**Fifteen of the twenty-four change band somewhere across that range.** If it were only evidence
accumulating, the drift would run one way; it does not. One human text reads *human* at 100 words and
*mixed* at 220 (79.7 → 56.3); another reads *mixed* at 60 and *mostly human* at 220. Two documents of
different lengths cannot be ranked by this number, and a long document cannot be spot-checked on an
excerpt.

The docstring already warns the score is not comparable across *tiers*, with a measurement. The same
caveat one axis over was missing, and it is the axis a user moves without noticing — pasting more.

**And the length sweep turned up something else.** One 100-word answer came back at exactly 50.0
while the detector ensemble read **P(AI) = 0.9992**. Nothing abstained; the terms summed there —
0.50 × 0.9992 of detector against near-zero tells and healthy burstiness.

50.0 is the value `humanness` returns for empty text, for text under `_MIN_WORDS_FOR_SIGNAL`, and for
scripts the catalogue cannot read. The docstring calls it *"the same 'cannot tell' answer empty text
gets"*. **It is also a score the function can compute, at the loudest AI reading a detector can
produce.**

Checked before writing it up: nothing in `untell/` or `eval/` branches on `== 50.0`, so this is an
ambiguity rather than a live defect. Only tests mention the value, and they assert that abstention
*returns* 50.0 rather than reading 50.0 *as* abstention — the safe direction. Pinned with a test that
solves for the detector reading which lands on the tie for a given text, asserts it sits above the
shipped verdict bar, and greps the tree for anyone who starts branching on it.

Worth keeping: **a sentinel that shares a type with real values is a bug waiting for its first
caller.** This one has none yet, and it was found by accident while measuring something else — the
`[44.0, 50.0, 50.0, 50.0, 50.0]` row stood out only because four identical values in a row do not
look computed.

## Result 121

**Two clean halves make a flagged document, and that is the whole of Result 120's drift.**

Result 120 measured `humanness` moving up to 23 points with paste length and left the cause open.
Decomposing the same 24 texts between their 60-word and 220-word windows, in points of the final
score:

```
                 tells   burstiness   detector
AI text          -5.4       -0.7        0.0
human text       -0.9       +0.3        0.0
```

**The detector contributes nothing.** It is saturated at P(AI) = 1.000 on every AI window — 13 texts,
five windows each — and flat near 0.38 on the human ones. That is worth stating on its own: the
component carrying half the weight is the one that does *not* move with length, so the drift belongs
entirely to the mechanical half.

The tells term rises 0.036 → 0.215 on identical prose. The mechanism is Result 119's, arriving at the
user-facing surface: both repetition categories fire on a SHARE, and a longer text crosses that bar
on writing every part of which sat under it.

**Constructed to remove all doubt.** Two halves, 66 and 67 words, six sentences each, three opening
with *"The"* — 33% duplicate openers, under the 40% bar:

```
first half    words  66   tells 0   /100w 0.00
second half   words  67   tells 0   /100w 0.00
both          words 133   tells 5   /100w 3.76
```

Each half clears the 60-word repetition floor and the four-sentence opener floor, so those zeros are
verdicts rather than abstentions. Nothing is added between the second line and the third. **A rate
that rises when you concatenate two texts is not a rate.**

Not fixed, and the reason is specific rather than general caution: the two repetition categories are
the strongest in the catalogue, and the threshold is what makes them precise — Result 117 already
measured what removing a threshold does to one of them (RAID AUROC 0.9555 → 0.9381). The scale
dependence is the price of the precision, and what was missing was the caveat, which now sits on
`humanness` next to the tier caveat it mirrors.

Worth keeping: **the term that carries half the weight was not the term that moved.** Three results
of length findings all pointed at the detector by association — it is the strongest signal, so it
must be the one doing this — and it turned out to be perfectly flat. Decomposition took one probe;
the assumption would have survived indefinitely without it.

## Result 122

**The fix was already written. It was applied to one rewriter and not the one next to it.**

Result 121 noted in passing that the detector ensemble sits at P(AI) = 1.000 on every AI window.
Following that up: over 80 corpus texts, the ensemble max reaches ≥ 0.999 on **100% of HC3 AI text**
and 30% of RAID's, against 0% of human text in both. `roberta_openai` returns 0.9992 on nearly every
HC3 sentence.

A saturated maximum is a flat objective. Five seeded candidate rewrites per text, six texts:

```
distinct values of MAX across candidates    1 on 4 of 6 texts   (spread ≤ 0.0006)
distinct values of MEAN across candidates   1 on 1 of 6 texts   (spread up to 0.2195)
```

The mean carries information exactly where the max carries none. That is not a new discovery here —
`composite._selection_key` was written for it, with its own measurement, and ranks candidates by
`(max, mean)`.

**`targeted` was still comparing bare floats.** Both of its accept tests read `after < before` on
`max` alone. Measured over 8 HC3 answers, per sentence:

```
max improved (adopted)        4
max worse (rejected)          0
max TIED, mean improved      15   <- every one discarded
max TIED, mean not improved   0
```

**Fifteen of nineteen real improvements thrown away, and not one tie that was neutral or worse.**
Mean 0.6839 → 0.5821, 0.7663 → 0.6978, 0.7504 → 0.6792 — all rejected because 0.9992 is not less
than 0.9992.

End to end on the same 8 documents, seeded identically, with the max-only ordering reproduced
faithfully rather than described:

```
BEFORE (max only)    3/8 texts changed
AFTER  (max, mean)   7/8 texts changed, every one lowering the ensemble mean
                     similarity min 0.966, meaning gates 7/7
```

The deltas are not uniformly larger — one document improved by 0.0314 under `max` alone and by less
afterwards, because adopting a different sentence changes what the rest of the pass sees. The claim
is *more documents improved*, not *every document improved more*.

The selector moved to `untell/rewriter/base.py` rather than being copied. Two selectors ordering the
same candidates differently is a failure this repo has now found three times — the vocabulary drift
in Result 115, the pattern drift in Result 116, and this.

**And the guard for it was wrong about the code it guards.** My `min_score` test asserted that a
document with no targetable sentence comes back unchanged. That is behaviour this module
deliberately stopped having: `targetable == 0` falls back to a whole-text rewrite, documented at the
call site with the measurement that motivated it. The test was written against what the gate *sounds
like* rather than what the module does, and only failing made me read the fallback.

Worth keeping: **a fix with a measurement attached is a fix for a class, and the class needs
grepping.** `_selection_key` carried a careful docstring explaining why `max` alone disables a
rewriter on the input it exists for. The same three-line comparison sat two files away, untouched,
for as long as the fix has existed.

## Result 123

**The grep that found the second instance is now something the repository does every run.**

Result 122 ended on "a fix with a measurement attached is a fix for a class, and the class needs
grepping". So the grep became an AST pass. Every comparison in `untell/` with a detector `max` on
either side, keyed by enclosing function:

```
untell/scripts/run.py::_passed                          acceptance against the shipped threshold
untell/scripts/run.py::untell_text                      selection, with the measured tells tie-break
untell/scripts/verify.py::verify                        reports the verdict a caller asked for
untell/attacks/word_importance.py::surgical_substitute  score-only branch is the caller's opt-out
```

Four sites, and **none of them is a third instance of the defect.** That is the useful outcome, not a
disappointing one: the loop's own selector reads `max` and then breaks ties on tells inside
`_TELLS_EPS`, which is a different measured secondary objective rather than a missing one, and the
comment there already cites "the same no-harm principle as the composite/ensemble selectors". The
search that would have found the `targeted` defect months earlier finds nothing left today.

**Written as an allowlist rather than a pattern**, because every one of those four is a legitimate
read of `max` and no expression-level rule separates them from the illegitimate kind. Each entry
carries its reason, and a test asserts the reasons are sentences rather than a suppression file.

The check fails in both directions:

- a NEW site not on the list fails — verified against a synthetic module containing exactly the
  `targeted` defect, `if score["max"] < best["max"]`;
- a LISTED site that disappears fails too, so a reason cannot outlive the call site it explains.

The second half matters more than it looks. An allowlist that only checks one direction becomes a
list of claims about code that may not exist any more — the same decay this audit was built to catch
in documents, reintroduced in the audit itself.

Worth keeping: **turning a one-off search into a standing check is cheap, and the moment to do it is
immediately after it finds something.** The AST pass is thirty lines. It would have caught the
`targeted` defect the day `_selection_key` was written, and the reason it did not exist is that
nobody had yet been burned twice.

## Result 124

**I measured my own fix at the wrong layer, and the pipeline says something the rewriter could not.**

Result 122 shipped a selector change on a rewriter-level measurement: `targeted` alone, 3/8 documents
changed → 7/8. The obvious next question is what `untell_text` does with it, and the first answer was
that nothing happens at all:

```
lite tier, 6 texts    changed 4/6, adopted 7, post-max 0.5227, tells/100w 3.66, sim 0.962
                      — IDENTICAL in both arms
```

Byte-identical. Two reasons, and both were already written down in the module I changed. The lite
detector does not saturate — its max sits near 0.52, so `after < before` separates candidates
perfectly well and the tie-break never fires. And `min_score` is an absolute 0.30 that no single
sentence clears on the stdlib path, which `targeted`'s own docstring records as 0 of 64 sentences, so
the per-sentence loop never runs and the whole-text fallback takes over.

**The saturation this selector exists for is a full-tier condition.** At `tier="full"`:

```
BEFORE (max only)    changed 3/4   adopted 3   tells/100w 3.80   sim min 0.992   post-max 0.9997
AFTER  (max, mean)   changed 4/4   adopted 4   tells/100w 2.98   sim min 0.971   post-max 0.9997
```

A 22% cut in tell density, similarity still far above the 0.76 bar — and **`post-max` does not move.**
It sits at 0.9997 in both arms.

That last line is the finding. The number the pipeline reports to the user is the same saturated
maximum that could not see the improvement in the first place, so a real gain in the output is
invisible in the verdict beside it. Result 122 fixed the selector; the reporting surface has the
identical blind spot and reports 0.9997 either way.

Result 122's claim needed this qualification and did not have it: *"7/8 texts changed"* is true of the
rewriter called directly, at the default tier of a bare `score_text` call, and says nothing about the
lite path a user gets without `.[full]` installed. One layer up, on one tier, the same change does
exactly nothing.

Worth keeping: **a fix measured at the layer you edited is measured at the layer least able to
contradict you.** The rewriter-level number was correct and the conclusion drawn from it was too
broad — the pipeline has a `min_score` gate, a fallback path and a tier that each decide whether the
edited line is reached at all, and none of them is visible from inside the function.

## Result 125

**The check written two results ago caught the code written in this one.**

Result 124 found the reporting surface carrying the same blind spot the selector had: at the full
tier, 4 documents rewritten, tells/100w 3.80 → 2.98, and `max` sat at **0.9997 before and after**, so
the Delta column printed `—` on a 22% cut in tell density. Fixing the selector and leaving that in
place would mean the product does better work and reports the same number.

So both surfaces now say when the comparison cannot move:

- the CLI report prints *"the hardest detector is pinned at 0.9997, so the P(AI) delta above cannot
  show an improvement either way"*, with the ensemble mean that did move (0.8100 → 0.6200);
- the result dict carries the same sentence on `warning`, composed with the existing caveats rather
  than replacing them, because a JSON, MCP or REST caller reads only that field and would otherwise
  see `pre` and `post` identical to four decimals on text that improved.

The bar is 0.99 rather than 0.999, so a detector pinned just under the rounding edge is caught. The
human side of both corpora never exceeded 0.4, so nothing legitimate is near it.

**And then the audit failed.** `check_selection_does_not_read_a_bare_max`, added in Result 123,
flagged `untell/rich_output.py::print_humanize_result` as an unlisted bare-max comparison — my own
new code, in the same session, three loops after building the check.

It is a legitimate read: the new comparison tests whether the max is *pinned* so the report can say
the delta beside it means nothing, which is the opposite of trusting it to choose. But that is
exactly what the allowlist is for, and the check did the one thing an allowlist-based guard has to do
— it refused to let a new site in silently, without any judgement about whether the site was fine.

Worth keeping: **the first thing a new guard catches is usually you.** Result 123 ended with "thirty
lines of AST would have caught the `targeted` defect the day `_selection_key` was written". Its first
real firing was two loops later, on code added by the person who wrote the guard, for a reason the
guard could not have known was good. That is not the guard being wrong. It is the only design that
could have caught the original defect, behaving identically on the case where the answer is "fine,
write it down".

## Result 126

**Two endpoints returned a `warning` field the OpenAPI spec did not mention, and the test for that
only looked one way.**

Result 125 put the pinned-max caveat on the result dict specifically so a machine client could read
it. Checking that it actually arrives: it does, and it is undocumented. Diffing every endpoint's real
response against its declared schema:

```
/health      5 fields   undocumented: []
/score      11 fields   undocumented: []
/humanize   15 fields   undocumented: ['warning']
/tells       9 fields   undocumented: ['warning']
/sentences   5 fields   undocumented: []
/verify      6 fields   undocumented: []
```

On `/humanize` that is the field carrying *"the hardest detector is pinned, so the before/after P(AI)
comparison cannot move"* — the only channel a machine client has for it, and absent from the spec a
generated client is built from. On `/tells` it is the one that says the counts are not evidence
because the text is in a script the catalogue cannot read.

**The suite already had a test for schema drift, and it could not see this.**
`test_no_documented_field_is_stale` compares schema → payload: a property the endpoint no longer
returns. Nothing compared payload → schema. `warning` even appears in that test's `conditional`
exclusion set, which is correct for the direction it checks and is exactly why the other direction
went unnoticed — the field was named in the test file as a known-conditional, so it read as handled.

Both schemas now declare `warning` (and `/humanize` declares `voice_warning`), and the missing
direction is a test. Verified by removing the declaration again and watching it fail on `/tells`.

This is the second one-directional guard found in three loops. The audit allowlist in Result 123 was
built to fail on additions and on removals from the start, because Result 122 had just made the cost
of a half-check obvious. This one predates that and had the same hole.

Worth keeping: **naming something in a test does not mean the test checks it.** `warning` was in
`conditional = {"warning", "failed_detectors", "detector_errors"}` — written deliberately, with a
comment about a previous exclusion that had been guessed rather than measured. It was still the field
that slipped through, because an exclusion list makes a field *look* considered from either side
while only one side is actually running.

## Result 127

**The parity file checked that shared operations agree. Nothing checked which operations were
shared.**

`test_surface_parity.py` is thorough about the operations it knows: same parameters, same defaults,
same tier and style vocabularies, on CLI, REST and MCP. It takes the operation list as given, and the
list had drifted:

```
REST only   health
MCP only    compare, scrub
both        ceiling, score, sentences, tells, humanize/untell, verify/verify_commercial
```

`health` is a liveness probe with nothing to mirror. `compare` runs every technique over a corpus and
takes minutes, which is why `/ceiling` caps `n` and why this one is deliberately not an endpoint.

**`scrub` was the one that cost a caller something they could not work around.** The CLI has
`untell-scrub`, the MCP server has a `scrub` tool, and a REST client holding untrusted text had no
way to strip hidden characters at all. The repo's own measurement is why that matters: those
characters do not move *this* ensemble — normalised, verified at 0.0000 on both tiers — but the same
text took an external detector from 0.0002 to 0.7900 on those bytes alone. A caller cleaning text
before submitting it elsewhere is the exact use, and REST was the surface without it.

`POST /scrub` closes it, returning the same `{clean, hidden_chars_removed}` the MCP tool does, with a
test asserting the two agree rather than merely both existing.

What remains is declared with a reason, and checked **both ways**: an operation added to one surface
fails until it is mirrored or listed, and a listed asymmetry that no longer exists fails too.
Verified by deleting the endpoint again — three tests fail, including the one that would catch a
future divergence rather than only this one.

Worth keeping: **a parity test can be exhaustive about the wrong axis.** Six tests compared
parameters and defaults across three surfaces, in a file whose docstring says "the same operation
must mean the same thing on the CLI, the REST API and the MCP server". Every one of them started from
a hard-coded list of two operations. The question they never asked was the cheaper one.

## Result 128

**The strongest caveat in the codebase was told to one caller per process.**

Chasing whether `targeted`'s `min_score` gate discriminates, the per-sentence score distribution
turned out to be the story. Over 100 HC3 sentences:

| tier | distinct values / 100 sentences | most common | sentence-level AUROC |
|---|---|---|---|
| lite (stdlib) | 6 | **0.250 × 91** | 0.515 |
| full | 39 | 0.9992 × 50 | 0.965 |

The repo already knew the direction — `score_sentences` records AUROC 0.493 in its docstring and
logs *"the 'flagged' sentences are close to arbitrary"*. What the count adds is that this is not a
weak ranking. **Ninety-one of a hundred sentences return the identical number.** It is a constant
with a few exceptions, sorted, and then the worst third of that ordering is handed to the user as
"rewrite these first".

It also explains the `min_score` behaviour that started this: 0 of 64 sentences clear the absolute
0.30 bar on the stdlib path and 64 of 64 clear it at the full tier, because the stdlib path never
leaves 0.250. The existing note calls that a scale mismatch between sentence and document scores.
It is narrower than that — there is no scale to mismatch.

**And the warning fires once per process.** `_WARNED_UNINFORMATIVE` is a module global, which is
right for a terminal and wrong for a server: a long-running API process tells its first request and
is silent for every caller afterwards, and no HTTP client reads the server's log in any case. So the
one caveat that says *the output you are holding is a coin flip* was the least likely to reach the
person holding it.

Split the two: the log line stays once-per-process, the **result carries the caveat on every call**,
and `/sentences` declares it in the schema — Result 126's lesson applied on the way in rather than
after the fact. `note`, which is always present and is about per-sentence noise in general, stays
separate; folding this into it would bury "these results are arbitrary" inside a sentence that is
true of every tier.

Worth keeping: **rate-limiting is a property of the channel, not of the fact.** Once-per-process is
the correct policy for a log line and was inherited by the caveat itself, because the caveat had no
other channel. Everything else about this was already measured, documented and warned about, three
years of care upstream of a `global` that made it invisible.

## Result 129

**The argument was already in the file, twelve lines below the branch that ignored it.**

Result 128 fixed one warn-once caveat with no other channel. The obvious question is how many there
are, so: every module-global warn-once flag in `untell/`, asked whether the fact reaches the caller
any other way.

Ten flags. Nine are fine — the detector adapters' `_warned` guards a load failure that `score_text`
already reports through `scored`, `detector_modes` and `failed_detectors`. One was not.

`untell_text` falls back to `composite` when no hosted or local-policy rewriter is configured, and
its comment says:

> *"Said once, on stderr, because a caller with a key who expected the hosted rewriter should know
> the free path ran instead — silently substituting a weaker backend is the failure this repo keeps
> finding on other surfaces."*

Twelve lines below, the voice-sample block makes the same argument and finishes it:

> *"`untell humanize --voice-sample` warns about exactly this on stderr; REST and MCP take the
> sample as TEXT and said nothing, so the two network surfaces silently used a sample the CLI would
> have flagged."*

— and sets `voice_warning` on the result. Same function, same failure named in both comments, one
of them acted on.

`_WARNED_FREE_FALLBACK` is a module global, so the practical behaviour on a server is: the first
request logs a line nobody reads, and every request after that gets `composite` with nothing on the
result and nothing in the log. A caller who set `ANTHROPIC_API_KEY`, expecting the hosted rewriter,
has no way to discover it was never reached.

`rewriter_warning` now mirrors `voice_warning` — same shape, same placement, kept separate from
`warning` because it says which BACKEND ran rather than how to read the numbers. Log line and field
read one constant, so the two cannot drift.

Worth keeping: **a comment that names a failure is not a fix for it, and the two can sit in the same
function.** Both blocks were written by someone who had the principle exactly right. What separated
them was that one had a `voice_warning` key already in the return dict and the other had a `logger`
in scope.

## Result 130

**Checking a claim I made without checking it, and the check found something else.**

Result 129 asserted that nine of the ten warn-once flags are fine because "`score_text` already
reports that load failure through `scored`, `detector_modes` and `failed_detectors`". That was
reasoning, not measurement, and it went into a committed result. So: break three detectors on
purpose and read what comes out.

**The first attempt measured nothing.** Patching `untell.detectors.base.load_detectors` left both
arms byte-identical — `score.py` imports the name into its own namespace, so the seam was one module
over. The premise line existed only because the probe printed the detector values, and they were
unchanged. A probe that cannot fail is worth nothing, and this one nearly shipped as evidence.

Patched at the right seam, the claim holds:

```
3 of 4 broken   failed_detectors ['roberta_openai','hc3_roberta','fast_detectgpt'], surviving score used
4 of 4 broken   scored False, max 0.0, flagged False, warning names every failure
```

**But the same probe showed the failure messages riding inside the scores on two surfaces.**
`api_server._numeric_detectors` exists precisely to stop that, and its docstring names the failure:
`max(detectors.values())` raises `TypeError: '>' not supported between instances of 'str' and
'float'`, and the field looks like a map of numbers because in every other response it is one. It was
called on `/score` and nowhere else:

```
/score      detectors numeric-or-null, detector_errors populated
/humanize   post.detectors -> {'perplexity_burstiness': 0.1111, 'roberta_openai': None,
            'roberta_openai__error': 'broken on purpose', ...}   detector_errors None
            mixed float / NoneType / str, and TWO such dicts per response (pre and post)
MCP         no normalisation at all, on either tool
```

The endpoint that returns *two* score dicts normalised neither, and the surface with no HTTP layer in
front of it had nothing. The helper moved to `untell/scripts/score.py`, recurses into `pre` and
`post`, and all three surfaces read it. The library shape is deliberately unchanged: the sidecars are
the internal convention and in-repo consumers filter on the suffix.

Worth keeping: **verifying an old claim is worth doing even when the claim turns out to be true.**
The answer here was "yes, Result 129 was right" — and the probe built to confirm it is what surfaced
a live defect two surfaces wide, which no amount of re-reading the assertion would have.

## Result 131

**Question: is the lite detector's near-constant output a property of the detector, or of the
question it was asked?**

Result 128 found `score_sentences` on the stdlib path returning 6 distinct values across 100
sentences, 91 of them exactly 0.250, at AUROC 0.515. That reads as a weak detector. Asked the same
question one granularity up, over 120 documents per corpus:

```
hc3    119 distinct scores of 120 documents    AUROC 0.864
raid   119 distinct scores of 120 documents    AUROC 0.791
```

**The same detector, on the same corpus, is fine.** The constancy is a property of the input length,
not of the heuristic.

The mechanism is in the detector's name. It is perplexity *and burstiness*, and burstiness is the
variation in sentence length — undefined on one sentence. Measured over 60 real HC3 sentences,
scoring the first sentence alone against the first two together:

```
single-sentence scores      8 distinct values of 60, and 82% are exactly 0.2500
|delta| from one more       median 0.406, mean 0.367, range 0.000-0.672
share moving by >0.30       67%
```

0.2500 is what falls out when half the detector has no input. It is a placeholder wearing the shape
of a score, and the existing short-text guard does not catch it: that guard counts WORDS, and a
71-word single sentence clears its 40-word bar and scored exactly 0.2500 with nothing said. Length
and sentence count are different limits, and a long run-on has only the second one.

`score_text` now says so, scoped to the case where the stdlib heuristic is the only detector — a
transformer scores a lone sentence perfectly well, and warning on the full tier would train readers
to skip the sentence.

**The first version of the caveat quoted 0.68, from one hand-picked pair.** The pair I then used in
the test moves 0.063, the assertion failed, and that failure is the only reason the distribution
above exists. The caveat now quotes the median and the range.

Worth keeping: **"weak signal" and "no signal" look identical in an AUROC and are different bugs.**
The first invites re-tuning a threshold; the second means the question is wrong. One extra
measurement at a different granularity separated them, and the answer changed what the fix should be
— from "warn that lite is weak" to "warn that this specific input has nothing for half the detector
to read".

## Result 132

**Question: six meaning gates guard every rewrite. Which of them has ever vetoed real output?**

Evaluated separately rather than as a conjunction, over 49 genuine rewrites from `structural`,
`surgical` and `composite` across 20 HC3 and RAID documents:

```
numerals        0        contradiction   1
certainty       0        role_swap       2
polarity        0        entailment      0
similarity      0
```

**Two gates did all the vetoing, and both are the model-backed ones.** The six zeros are not dead
code and this is not an argument to remove them — `meaning_preserved` already records the same
result for polarity in its own comment, with the reason: the free rewriter's transforms are
substitutions, merges and splits, none of which touches negation. They are insurance against a
rewriter this path does not have.

**The part that matters is what the two live gates cost when they are absent.** All three vetoed
candidates scored similarity **0.969, 0.981, 0.981** against a 0.76 bar. So on an install without
NLI and spaCy the conjunction admits **3 of 3** — not "most of them", and not at a similarity a
reader would find suspicious.

The pipeline already reports `meaning_gate: "nli"` or `"similarity-only (...)"`, and its docstring
already carries a constructed example — *"runs faster" → "runs slower"*, similarity 0.983, admitted.
What it did not have is the rate on real output, and the rate is total: **under `similarity-only`
this conjunction has never rejected anything on measured corpus output.** That is a different claim
from "weaker", and it is the one a user deciding whether to install the extra needs.

Worth keeping: **a conjunction of eight checks can have its entire behaviour supplied by two of
them, and the count of checks tells you nothing about which.** Six gates reporting zero is the
expected, correct outcome for the rewriter in use — and it means the guarantee the product actually
delivers rests on two optional dependencies, which is not visible from the list.

## Result 133

**The field that reports which guarantees are in force did not know about the larger one.**

Result 132 ended on the guarantee resting on two optional dependencies. `meaning_gate` exists
precisely to say which are present, and `"nli"` is documented as *"the full conjunction ... plus the
predicate-argument role check"*. It was computed from the NLI import alone:

```
full install                 nli
NLI present, no spaCy model  nli          <- role check silently absent
veto disabled                similarity-only (veto disabled)
```

With the parser gone `role_swap` returns None — correct, an unavailable check must never become a
veto — and nothing anywhere said the check had stopped running.

**It is the larger half.** From Result 132's per-gate table over 49 real rewrites: contradiction 1,
role_swap 2, everything else 0. Two of the three vetoes the whole conjunction produced came from the
check the mode string did not mention.

`"nli (no role check)"` is its own value rather than folded into either neighbour, because it is
strictly stronger than `similarity-only` — contradiction and entailment still run — and strictly
weaker than `nli`. A caller comparing runs across two installs needs to see which.

`parser_available()` is a separate function rather than "call `role_swap` and check for None",
because None is also what an empty pair returns. *"This pair had no roles to compare"* and *"this
install cannot compare roles"* are different facts and only the second is a missing guarantee — the
same distinction `score_text` draws between a detector that abstained and one that failed.

Worth keeping: **a field that reports degradation is itself a place degradation can hide.** This one
was added for exactly the right reason, names the role check in its own docstring, and had no code
path that could observe it. The check it forgot is the one doing most of the work.

## Result 134

**Nine new ways the rewriter could break a sentence. Seven of them: zero, on both sides.**

The output battery has thirteen checks and the metrics cannot see grammar, so the question is what
it still misses. Nine candidate breakages the transform set could plausibly emit — merges,
splits, substitutions and deletions — scored on the OUTPUT and the SOURCE over 40 HC3+RAID documents
through `structural` and `composite`:

```
check                       source  output  DELTA
comma_splice                    34      20      5
repeated_connective             41      38      1
no_space_after_stop              0       0      0
unbalanced_square                0       0      0
unbalanced_curly                 0       0      0
orphan_trailing_prep             0       0      0
duplicate_sentence               0       0      0
sentence_starts_with_comma       0       0      0
space_before_apostrophe          0       0      0
```

**The two that fire are not damage checks.** `comma_splice` matches 34 times on untouched corpus
prose and `repeated_connective` 41 times; both fall on the output. A check that fires thirty-four
times on text the rewriter never touched is detecting a shape of English, not a defect, and the
battery's own rule covers this: *"a damage check that cries wolf gets its fixture edited instead of
the bug fixed."* Rejected, with the numbers recorded so the idea is not re-proposed.

The seven zeros are the useful answer. They say the transform set genuinely cannot produce those
shapes on this corpus, which narrows where future breakage can come from — so they are added as a
floor rather than as a discovery, each with a known-positive probe. A check that has never matched
anything and cannot be shown to match is indistinguishable from a broken regex, and this repo has
shipped three of those, with a literal `0x08` where `\b` was meant.

**And adding them exposed an older gap.** `test_every_check_can_actually_fire` iterates `_CHECKS`,
the regex table. The checks `_damage` computes in Python — fragment leads, unbalanced quotes,
unbalanced parens, stub sentences — were never in it and had no known-positive at all. Now driven
off `_damage`'s own key set, so a new derived counter cannot be added without one.

Worth keeping: **a battery of thirteen checks and a probe test for eleven of them looks complete
from either end.** The probe test asserts `set(probes) == set(_CHECKS)` and passes; the four
Python-counted checks are simply not in `_CHECKS` and so were never in scope for the completeness
assertion that exists.

## Result 135

**A command that printed "the patterns did not apply, NOT that the text reads as human" exited 0.**

`untell-verify` had just been fixed for returning 0 when no checker ran — *"a CI job gating on this
command was told the text passed every major AI checker when not one had been consulted"* — and its
comment settles a vocabulary worth reusing: **2 means nothing ran**, deliberately not 1, because 1 is
a verdict a caller may act on by rewriting and a configuration problem is not.

So: does any sibling command have the same hole? Measured across the report entry points, on inputs
where each is known to abstain:

```
untell-score, every detector broken   "scored": false, "max": 0.0, "flagged": false   exit 0
untell-tells, Chinese paragraph       "language_supported": false, tells 0, words 0   exit 0
```

Both carry the diagnosis in their JSON, and `tells` prints the sentence in the heading of this
result — then exits 0, which says the opposite to anything reading the status. A shell branching on
`untell-score` saw success and a max of 0.0, which reads as *not AI*.

Both now return 2 on those paths, quoting `verify`'s reasoning at the call site.

**What deliberately did NOT change is the interesting half.** A flagged score still exits 0. A
document with forty tells still exits 0. These are reports; `untell-verify` is the gate and owns
exit 1. Two commands in one toolchain disagreeing about what exit 1 means would be worse than the
silence being replaced — so the rule is one sentence: *the count never becomes a verdict, and only
the gate returns one.*

**And the first probe of this was wrong.** I measured exit codes through a pipe — `cmd | tail;
echo $?` reports `tail`'s status, not the command's — and read back `humanness normal=1`, a defect
that does not exist. Re-run without the pipe, every entry point returned 0 on normal input. The
harness has to be checked before its output is, which is the third time in this session a probe has
needed that.

Worth keeping: **an exit code is an API with exactly three consumers and no schema.** Every one of
these commands already reported its abstention correctly in the payload — the JSON was right, the
prose was right, and the one-byte channel that CI actually reads said the opposite.

## Result 137

**Sixteen of the audit's eighteen checks have never been shown able to fail.**

The audit is what makes this repository's correctness argument checkable: eighteen checks, eighteen
PASS lines, exit 0. So the obvious question is whether a PASS means anything. Cross-referencing every
`check_*` against the test suite for a known-negative — a test that constructs a failing input and
asserts the check reports FAIL:

```
has a known-negative test          2 of 18
referenced from tests at all       6 of 18
```

Twelve of the eighteen are not mentioned anywhere in 4949 tests. This is the shape of the defect that
once left three regexes matching nothing across 2526 tests: **a check nobody has watched fail is a
check nobody has watched.** Recorded as a measured, open gap rather than closed in one loop.

**One of them was measurable immediately, and the first measurement was wrong.** A harness that
deleted each document and re-ran every check reported `README.md` disappearing *silently* — findings
dropped, no failure. Running the real command instead: a `FileNotFoundError` traceback and exit 1.
The swallow was `except Exception: pass` in my own harness. **A probe that hides the failure mode it
is looking for will find the opposite of the truth**, and this one nearly went into a result.

What survived the correction is real, and it is two answers to one question living in the same file:

```
checks doing `if not doc.exists(): continue`   findings vanish, run still reports success
checks calling read_text bare                  FileNotFoundError traceback, exit 1
```

Neither is a report. The audit's own contract is to say what it could *not* check — it publishes
checked / attributed / unattributed totals precisely so it never claims coverage it lacks — and a
stack trace says nothing while a silent skip says the wrong thing. Both now route through one reader
that records a named failure and lets the run continue.

**The guard against a third answer found one while being written.** A test asserting no `LIVE_DOCS`
entry is read outside the shared reader failed immediately on
`(REPO / "README.md").read_text(encoding="utf-8", errors="replace")` — a fourth call site I had not
patched, differing from the one I had by an argument. Two more turned up in loops over explicit
document tuples.

**And it exposed which documents nothing was watching.** Deleting each `LIVE_DOCS` entry in turn and
recording who reported it:

```
README.md                                   check_derivable, check_dynamic_env_vars, check_named_repo_stars
ROADMAP.md                                  check_derivable, check_named_repo_stars
docs/why-best-open-repo.md                  check_derivable, check_largest_repo_claims, check_named_repo_stars
docs/index.md                               check_derivable
docs/what-would-make-this-the-top-repo.md   check_derivable
```

Two of the five live documents rest on a single check. That is not a defect today, but it is the
number to know before trusting any one of them.

Worth keeping: **a green audit is evidence about the code only to the extent its checks have been
seen to go red.** Eighteen PASS lines and two demonstrated failure paths are not eighteen results;
they are two results and sixteen assumptions.

## Result 138

**Every audit check made to fail on purpose, and five of the first ten mutations were the story.**

Result 137 measured the gap and left it open: 2 of 18 checks had a known-negative, 12 were not
mentioned anywhere in 4949 tests. Closing it means one mutation per check — break the thing it
guards, on a real copy of the repository, and require a FAIL. **A mutation that does not trip its
check is the finding.**

Ten written, five did not trip. Every one was informative, and only two were the audit's fault.

**1. `check_no_control_characters` reported "clean" over zero files.** The copy has no `.git`;
`_tracked_text_files` returns `[]` when `git ls-files` fails; the loop ran zero times and the check
passed with detail `"clean"`. A BEL byte sat in `docs/index.md` unseen. **Zero files inspected is an
unperformed check, not a clean repository** — the same absence-read-as-success this session has now
fixed on four CLI exit codes, two REST surfaces and the audit's document reader. Now a named failure.

**2. `check_test_inventory` was right and the repository was stale.** 173 claimed against 180 on
disk — drift that arrived between loops. Resynced.

**3. The dead-function probe put its own subject into the haystack.** A function named
`_never_called_anywhere` added to `untell/layout.py` was reported as *referenced*, correctly: the
check searches `tests/` too, and the name was written out in the test file asserting it was dead. The
name is now assembled at runtime from three fragments.

**4 and 5. Two mutations aimed at patterns that were not there.** `check_dynamic_env_vars` covers
only the family `config.py` BUILDS as `f"UNTELL_{key.upper()}"`, so an arbitrary `os.environ.get`
literal is out of scope. `check_test_count_claims` matches `(\d{3,5})\s+tests`, and the document
carried no such phrase at all — the mutation rewrote nothing and `mutate()` caught it only because it
asserts the text actually changed.

Three more surfaced while finishing the set: `check_test_inventory`'s real pattern spans a line break
where a literal space fails; `check_attribution` only sees **bold** numbers, by design, because those
are the ones a reader takes away; `check_unreleased_changelog_is_current` compares the shipped
caveat's own values and only once the section mentions "corpus means", so an invented `0.123` is not
its subject.

**All 18 checks now have a demonstrated failure path** — 15 mutations here plus the missing-document
tests, each paired with a `assert_passes` on the unmutated copy so a check that failed for an
unrelated reason cannot masquerade as a caught mutation.

Worth keeping: **writing the known-negative is where you learn what the check actually checks.**
Three of the five misses were my mutations misunderstanding the check's scope, and that
misunderstanding is exactly what a reader of a green PASS line would have had too. The eight `assert
that it passes cleanly first` lines are half the value of the file: without them, a check broken for
any reason at all would make its own mutation test pass.

## Result 139

**The gate with no column in the table was the only one that caught deletion — and my first fix for
it broke the loop.**

Result 138's lesson applied to the meaning gates: has each been *seen* to reject? Mostly yes, and
that is the honest first half — `test_the_gates_are_complementary.py` already pins a rejecting case
for numbers, polarity, certainty, roles, contradiction and similarity, as a table. **Not every
question yields a defect.**

But the table has six columns and the conjunction has seven terms. The entailment floor has no row,
and `run.py` records it vetoing **0** of 49 real rewrites. A term that never fires is either
insurance or decoration, and only making it fire tells you which.

It fires — and on one case it fires *alone*:

```
candidate         sim     entailment   contradiction   NLI verdict   similarity-only
drop 1 of 3     0.949        0.0015         0.007        rejected       ADMITTED
drop 2 of 3     0.897        0.0014         0.009        rejected       ADMITTED
half a clause   0.761        0.0012         0.021        rejected       ADMITTED
unrelated       0.000        0.0012         0.177        rejected       rejected  (similarity)
negated         0.973        0.0017         0.997        rejected       rejected  (contradiction)
```

**Deleting a third of a document scores similarity 0.949 against a 0.76 bar and contradicts
nothing** — a truncation asserts nothing to contradict. Every gate but entailment passes it, and that
floor needs the NLI stack, so on the advertised zero-dependency default it was admitted. The
`token_overlap` docstring documents the analogous hole for *substitution*; nobody had asked about
deletion. Not hypothetical: Result 116 added a transform to this pipeline that removes sentences.

**Then the fix broke the loop, and the reason is a lesson this repository has already written down.**
A ratio floor at 0.80 looked clean — 445 corpus-length rewrites bottoming out at 0.902 against 0.721
for the mildest deletion, a wide gap. The full suite disagreed:
`test_the_rewrite_actually_did_something` failed, every candidate rejected, the loop returning its
input unchanged. On the 24-word paragraph that test uses, removing *"Moreover,"* and *"it is
important to note that"* — **the actual job** — costs a quarter of the document. Filler is roughly
constant in words; documents are not. The ratio was a property of the corpus I measured it on.

Re-measured in words lost, short probes and corpus documents together:

```
source length     n     max lost   median lost
    0-40 words    18        5           1
  120-400 words  205        9           0
```

against 12, 26 and 36 for the three deletions. The allowance is now the larger of 10 words and 10%
of the document: the fixed part covers short input, the share covers long input where filler scales.

**The margin is one word — 9 lost legitimately, 12 for the mildest deletion — and that is a limit
rather than a number to tune.** A dropped sentence of ten words or fewer is not separable from
aggressive filler removal by length alone, because the two populations genuinely touch there. What
this buys is sentence-scale deletion on the path with no model; anything smaller still needs NLI.

Worth keeping: **the row missing from a comparison table is the one to go looking at** — six gates
had a column and a rejecting case, the seventh had neither and was the only defence for a class the
default install is blind to. And the sharper half: **the full suite caught a corpus-scope error that
445 measurements did not.** The number was real, the population was wrong, and only an input outside
that population could show it.

## Result 140

**The transform shipped in Result 116 has never survived the loop. I verified it against the wrong
gate.**

Result 139 added a deletion guard, so the obvious next question is whether it blocks the
sentence-removing transform added in Result 116. It does — and finding that out showed the transform
had been dead since the day it shipped, for a different reason entirely.

Result 116 verified `_strip_meta_closers` with `passes()` — the **similarity-only** helper — and
recorded "similarity 0.981–0.997, `passes` True, `contradicts` False". The loop does not call
`passes()`. It calls `meaning_preserved`, and measured against *that*:

```
candidate            sim     lost   numbers  polarity  certainty  roles   meaning_preserved
one sign-off       0.994      4       True     True      FALSE    ok           False
two stacked        0.991     13       True     True      FALSE    VETO         False
three stacked      0.989     23       True     True      FALSE    VETO         False
```

**Three gates, three different reasons, every one of them right about the text and wrong about the
meaning.** `certainty` sees "hope" and reads a dropped hedge class. The length guard sees 13 words
gone. `roles` sees the predicates *"I hope …"* and *"Let me know …"* vanish. Seventeen tests passed
and the transform produced correct output that the loop threw away every time.

`certainty_kept`'s docstring justifies its two known false vetoes with **"0 candidates vetoed over 80
runs"** — true when written, and stale the moment a transform existed that removes a sign-off. A
measurement that licenses a trade-off has to be re-run when the thing it measured changes.

**The first two fixes were the wrong shape.** I exempted sign-offs inside `certainty_kept`, then
again inside `words_lost` — two scattered exemptions, and `roles` still vetoed, which would have made
three. Replaced with one normalisation in `meaning_preserved`: strip scaffolding from both sides
once, and every gate sees like for like.

**And then the two halves disagreed about the unit.** `_strip_meta_closers` deletes a whole
*sentence*; the exemption removed only the matched *span*, so the remainder — *"if you need more
detail"* — read as deleted content and the gate still vetoed. `is_pure_scaffolding` and its
remainder bound now live in `tells`, beside the pattern, with the rewriter and the gate both calling
it. Same defect as Result 115's two vocabularies, one layer up: not two patterns this time, but two
*units* for one pattern.

Verified in both directions: the strip passes at one, two and three stacked closers; dropping a real
sentence, negating a claim, and content wearing a sign-off as a prefix are all still rejected.

Worth keeping: **verifying against a helper that is not the one production calls proves nothing, and
it looks exactly like proof.** `passes` and `meaning_preserved` differ by six gates. The Result 116
entry reported real numbers, honestly obtained, from a function the pipeline never invokes.

## Result 141

**A fix that changed nothing, and looked exactly like a fix that worked.**

Result 140 found one transform the gate silently rejected. The general question: how many others fire
and are then thrown away? Every text-in/text-out transform in `structural.py`, over 120 corpus texts,
scored against `meaning_preserved` rather than against `passes`:

```
_parenthesise_asides             fired 18   rejected 0
_flatten_cliches                 fired 22   rejected 4    <- all four from role_swap
_flatten_copula                  fired  4   rejected 0
_flatten_negated_contrast        fired  3   rejected 1    <- a TRUE catch
_flatten_participial_trailers    fired  1   rejected 0
```

No second always-dead transform, which is the honest first half. But `_flatten_cliches` — the one
that fires most on real text — loses 18% of its output to the same shape as the sign-off case:
deleting *"It's important to note that"* removes the predicate **note**, and the role checker reads a
vanished predicate as a changed role. Every other gate passed it: contradiction 0.002, entailment
0.856, numbers, certainty, polarity, length all clear.

**The cost was not a wasted draw. One document in twenty lost its entire structural rewrite to it.**

The other rejection is the gate doing its job and is left alone: `_flatten_negated_contrast` dropped
54 words including a negation, numbers False, polarity False. Real damage.

**Then the fix measured as a perfect no-op.** After exempting the deleted stance frames, the rate was
`fired 22, rejected 4` — *identical*, to the case. The pattern contained a literal **0x08 backspace
byte** where the word-boundary escape was meant, produced by a shell heredoc, so it matched nothing:

```
STANCE_FRAME_RE.pattern[:12]  ->  '\x08(?:[Ii]t('
```

This repository already carries that exact defect in its history — three patterns dead, 2526 tests
blind, and the lesson written down as *assert every pattern against a known positive*. I wrote a new
one anyway, and the only reason it did not ship is that I re-ran the measurement the fix was supposed
to move and found it unmoved. **A broken pattern and a correct no-op produce the same table.**

With a working boundary: `fired 22, rejected 0`, and all four leak directions still shut — plain role
swap, role swap *inside* a stance frame, negation, and real deletion.

The exemption is exactly the nine frames `_CLICHE_FLATTEN` deletes outright, never the whole cliché
catalogue: a genuine role swap could hide inside a broader match, and these nine carry no argument
structure about the subject at all. A count assertion fails the build if that set ever grows without
the gate learning about it — the anti-drift check that Results 115 and 140 both needed and lacked.

Worth keeping: **re-measure the number the fix was supposed to move, not a number near it.** Every
other signal said this change was correct — tests green, review clean, reasoning sound. The one
question that caught it was "did the thing I was trying to change, change?"

## Result 142

**Twice is a class. Every pattern in the package now has to prove it can match.**

The 0x08-backspace-for-`\b` defect has shipped here twice: three dead patterns behind 2526 green
tests the first time, and one more last result, caught only by re-running the number the fix was
supposed to move. Waiting to trip over a third is not a plan.

So: enumerate every module-level compiled pattern in `untell` and require each to match *something*.

**The first sweep was wrong, and its own output said so.** Whole documents as the haystack reported
8 dead patterns — but five of them are `^`-anchored and only ever see a single sentence or line.
Feeding the harness lines and sentences as well dropped it to 5, and every one of those five fired
on a constructed positive. **No dead pattern remained.** The honest answer to the question was "none",
and the value is in what that took: a harness matched to how each pattern is actually called.

What the sweep did find is that **none of those five is named in any test**. If one regressed to the
backspace form tomorrow, all 5066 tests would stay green — the exact conditions of both previous
incidents.

The standing guard: 127 patterns, of which 123 match something in the repository's own prose and
source, and 4 cannot by their nature — internal `⟦HZ…⟧` sentinels, invisible Unicode, trailing
horizontal whitespace. Those four carry an explicit positive, so a break stops matching its own
registry entry and the failure names the pattern.

Verified the only way this kind of test can be verified: **reintroduced the real defect.** With the
backspace byte back in `STANCE_FRAME_RE`, two assertions fail — the behavioural one, and the one that
names the byte:

```
FAILED test_the_pattern_matches_something[scripts.tells.STANCE_FRAME_RE]
FAILED test_no_pattern_contains_a_control_character
```

Both, deliberately. A pattern can be alive and still carry a stray byte, and a non-match with no
explanation is a mystery to whoever hits it next.

Two seconds for 129 assertions, so it costs nothing to keep.

Worth keeping: **a defect that has happened twice deserves a mechanical check, not a third lesson.**
Both earlier instances were found by luck — a passing suite, a clean review and correct-looking
reasoning surrounded them both. The check is cheap; the noticing was not.

## Result 143

**Three loops of gate changes, and I had not once measured the product.** So: run the end-to-end
ceiling. The answer was not about my changes at all.

The first run measured the wrong corpus, and the tool said so on its own output — `corpus=builtin`,
three hand-written paragraphs the docstring already calls "measurably easier than real AI text". Rerun
against HC3:

```
pre  flagged rate 1.0   mean max P(AI) 0.9997
post flagged rate 1.0   mean max P(AI) 0.9994   (rewrote 18/18)
stdev 0.0001            mean similarity 0.9844
```

A tool that achieves nothing. Except the per-detector rows say something else entirely:

```
hc3_roberta              0.9992 -> 0.9992      moved by nothing
roberta_openai           0.9986 -> 0.6228      moved by 0.376
fast_detectgpt           0.6563 -> 0.4782
perplexity_burstiness    0.6059 -> 0.5679
```

**Three of four detectors improved substantially and the headline could not show it, because the
headline is a `max` and the highest member never budged.**

`hc3_roberta` is fine-tuned **on HC3**, so against HC3 it is in-distribution — human mean 0.0796, AI
mean 0.9992, and the entire spread across 15 AI documents is **1.2e-05**. It discriminates perfectly
and has no dynamic range left to give. On RAID, which it never trained on, the same detector runs
0.0018 human against 0.6953 AI and moves freely. Nothing is broken; the detector and the corpus are
the same distribution.

**And my first reading of it was wrong in a way worth recording.** At four decimals every AI document
scored exactly 0.9992 — `min == median == mean` across 25 — and I wrote "that is not confidence, that
is a constant". Full precision: 14 distinct values in 15, spread 1.2e-05. *Effectively pinned* and
*returns a constant* are different claims, they imply different bugs, and only one of them is true.
The four-decimal display was the whole basis for the stronger one.

The fix is reporting, not scoring. `hc3_roberta` is right to be certain, and dropping it would be
tuning the ruler. What was wrong is a report that says "0.9997 -> 0.9994, still flagged" and leaves
the reader to derive from a table underneath it that one member is holding the number still. The
ceiling now names the pinning detector, the count that moved, and the largest mover with its delta —
and stays silent when everything moved, when nothing moved, and on baseline-only runs.

Worth keeping: **the corpus and the detector can be the same distribution, and then the metric stops
being about the tool.** The number was not measuring untell's ceiling on HC3; it was measuring how
well an HC3-trained classifier knows HC3. Both of the session's earlier corpus lessons said to vary
the corpus. This one says to check what the *detector* was trained on before quoting what it reports.

## Result 144

**A headline README number that no longer reproduces, and the obvious culprit was mine and was
innocent.**

Result 143 left a number I noticed and did not chase: the README publishes composite at mean max
**0.778 ± 0.020**, flagged **0.94**, `hc3_roberta` **0.710**. I had just measured 0.9994 on the same
corpus. Two numbers for one claim is a defect whichever is right.

Reproduced with the documented command and no environment overrides —
`--dataset hc3 --n 6 --rewriter composite --best-of 3 --repeats 3 --tier full`:

```
                       published        measured 2026-08-12
mean max P(AI)         0.778 ± 0.020    0.9994
flagged rate           0.94             1.00
hc3_roberta            0.710            0.9992 -> 0.9992  (unmoved)
meaning similarity     0.978            0.9843
```

`pre` matches exactly, so it is the same corpus and the same detectors. **The composite column does
not reproduce.**

**Two hypotheses, both mine, both wrong.**

*The environment.* `UNTELL_LITE_NO_TORCH=1` was set on my first run and could have swapped the
similarity backend under the meaning gate. Checked: `method()` returns `embedding` either way, and
`--max-iters` already defaults to the documented 5.

*My own deletion guard*, added three results earlier — a plausible story, since a stricter gate
rejects the aggressive candidates that move a detector furthest. Tested by running the ceiling with
`deletion_allowance` patched to infinity:

```
guard ON (shipped)    post mean max 0.9995   flagged 1.0   hc3_roberta 0.9992   sim 0.982
guard OFF             post mean max 0.9995   flagged 1.0   hc3_roberta 0.9992   sim 0.982
```

Byte for byte identical. **Refuted**, and consistent with Result 139's own numbers: real rewrites lose
at most 9 words against an allowance of 10, so the guard almost never binds.

What remains is dated rather than proven. The claim was published 2026-08-11; on 2026-08-12
`structural.py`'s draws were seeded, and *that commit's own message* records output depending on what
the process had rewritten before it. The published figures came from an unseeded stream that no
longer exists — the strongest remaining explanation, and I am recording it as such rather than as a
conclusion.

The README now carries the re-measurement beside the table, with the command, the date, and the
refuted alternative. **Not deleted**: a number that was true of a build is a record, and erasing it
would destroy the evidence that the seeding fix changed results.

Worth keeping: **the suspect you already have your hands on is the one to test first and the one
most likely to be innocent.** I had changed the meaning gate three results running, so a gate
explanation felt obvious. It cost one experiment to refute and would have cost a wrong entry in this
log to assume.

## Result 146

**A stub that is never called, in a test named for the thing it stubs.**

The previous loop fixed a monkeypatch whose signature had stopped matching the function it replaced.
That one failed loudly — `TypeError: takes 1 positional argument but 2 were given`. The dangerous
version is the stub that keeps passing, so: instrument `monkeypatch.setattr` to count invocations and
run the suite.

```
404 stubs installed, 52 never called
```

Most are correct and one is exemplary: `test_importance_accepts_a_precomputed_base` installs a stub
that **raises** — *"importance recomputed the baseline despite being given one"* — so never-called IS
the assertion, and a regression names itself. `test_empty_text_is_neutral` and
`test_veto_can_be_disabled` are the same idea more quietly: their stubs return values that would fail
the assertion if the call happened.

One is not.

```python
def test_sim_floor_adapts_to_the_active_similarity_metric(monkeypatch):
    monkeypatch.setattr(q, "method", lambda: "token_overlap")
    monkeypatch.setattr(r, "recommended_bar", lambda: q.TOKEN_BAR)   # <- short-circuits the chain
```

`recommended_bar()` reads `method()` — that is the adaptation, and it is the entire subject of the
test's name and docstring. Pinning `recommended_bar` as well bypasses it, which is exactly why the
`method` stub was never called: **the test asserted the reward given a bar, not that the bar adapts
to the backend.** The dead stub was the evidence, and nothing else would have shown it: the test
passed, its assertion was true, and its name was wrong.

Removing the redundant stub makes the chain real. Verified by breaking the adaptation —
`recommended_bar` returning `DEFAULT_BAR` unconditionally:

```
before the fix    would pass  (recommended_bar was pinned, so the broken function never ran)
after the fix     FAILED tests/test_reward.py::test_sim_floor_adapts_to_the_active_similarity_metric
```

The stakes are in the docstring the test already carried: with token overlap active, a 0.76 bar
hard-gated faithful paraphrases to −1.0, the same reward as an off-topic rewrite, and GRPO learned to
make trivially small edits while the loss curve looked plausible. The test written to stop that
recurring could not have seen it recur.

Worth keeping: **an unused stub is a question, not a defect — and the question is what the test is
actually asserting.** Fifty-two of them, and fifty-one were fine. The one that mattered had a name
describing a behaviour that a second stub had switched off.

## Result 147

**Both published ceiling columns are unreproduced, so the useful question is what this repository
can honestly publish today.**

Results 143–146 left the headline table with neither column reproducing and a clear reason for the
HC3 half: `hc3_roberta` is fine-tuned on HC3, the max is pinned at 0.9992, and the loop's real effect
is invisible behind it. That diagnosis has a testable consequence — on a corpus no detector was
trained on, the max should move.

RAID paper abstracts, same rewriter, same settings, commit stamped:

```
RAID, n=6, --repeats 3, composite, tier full, commit 9545d62

  flagged rate      0.83  ->  0.28
  mean max P(AI)    0.629 ->  0.287       per-run [0.2838, 0.2862, 0.2911]   stdev 0.003
  roberta_openai    0.333 ->  0.0005
  hc3_roberta       0.350 ->  0.105
  fast_detectgpt    0.491 ->  0.196
  perplexity        0.455 ->  0.274
  similarity        0.979 mean / 0.939 worst
```

**Every detector moves, the three runs agree to ±0.003, and 72% of documents end unflagged.** The
same `hc3_roberta` that would not shift by 0.0001 on HC3 drops by two thirds here. That is the
prediction the diagnosis made, and it held.

**And quoting this number alone would be the same error this repository already documents about its
built-in sample.** RAID starts easier: 0.83 flagged at mean max 0.629, against HC3's 1.00 at 0.9997.
The loop is not "doing better" on RAID; it is starting from a different place. Both belong in the
README, with their starting points, or neither is honest — the temptation to publish the flattering
corpus is exactly what produced the stale numbers being replaced.

Worth keeping: **a diagnosis is worth more than a measurement, because it predicts.** "The max is
pinned because one detector is in-distribution" is not a description of HC3; it says what a different
corpus must show. Checking that turned a broken headline into a reproducible one, and would have
falsified the diagnosis if RAID had been pinned too.

## Result 148

**The comment explaining a constant named the wrong detector, and the explanation was the point.**

Result 147's diagnosis — the max is pinned because one detector is in-distribution — should apply to
the user-facing report too, not just the eval tool. It already does: `rich_output` warns that a flat
P(AI) delta proves nothing once the max is saturated. **No gap.** That is the honest first half.

The comment justifying its bar is another matter:

> *"...because `roberta_openai` returns 0.9992 on nearly every sentence of that genre."*

Re-measured on 60 HC3 AI sentences and the 12 documents they came from:

```
detector           sentences >=0.99   sentence mean   documents >=0.99   document mean
hc3_roberta            58 / 60           0.9977          12 / 12            0.9992
roberta_openai          2 / 60           0.7405          11 / 12            0.9962
fast_detectgpt          0 / 60           0.6451           0 / 12            0.6183
```

**2 of 60, not "nearly every".** 0.9992 is `hc3_roberta`'s number, attributed to its neighbour.

Not pedantry, because the comment is *reasoning*, not decoration. Under rewriting `roberta_openai`
drops **0.9986 → 0.6228** while `hc3_roberta` does not move at all — it is fine-tuned on HC3, so the
corpus is in-distribution for it. Anyone acting on the old attribution would hunt the pin in the one
detector that demonstrably yields.

**A second question, asked and answered against my own hypothesis.** The bar is a LEVEL test
(`max ≥ 0.99` on both sides) where the eval tool's equivalent is a MOVEMENT test. A detector stuck at
0.85 pins the delta just as hard and sits below the bar, so the level test could in principle miss
one. Over 30 real composite rewrites of HC3 and RAID text: 16 fired the note, and **0** had a max
moving less than 0.01 while the mean moved more than 0.05. The simpler criterion loses nothing that
has been observed, and that measurement now sits beside the constant instead of the wrong sentence.

**The guard for the correction failed on the correction.** The test forbade the old wording outright,
and the new comment quotes that wording in order to refute it. Identical to the earlier guard that
forbade `50.0` inside a function whose comment warns against comparing to `50.0` — twice in one
session, so: **a check that cannot tell the mistake from the text describing it fires on the fix.**
It now asserts the attribution (`because \`roberta_openai\` returns`) rather than the phrase.

Worth keeping: **a wrong explanation is worse than no explanation, because it gets acted on.** The
constant was right, the note it gates was right, the behaviour was right — and the one sentence
telling a maintainer *why* pointed at the wrong component.

## Result 149

**The wrong attribution was in five places. I fixed one and wrote the result as though that were the
class.**

Result 148 corrected a comment crediting `roberta_openai` with pinning the ensemble max. The obvious
follow-up: sweep every comment in `untell/` that names a detector alongside a number — 36 lines
across 5 detectors. The very first scan found the same sentence in `rewriter/targeted.py`, and its
own test file carried it too.

So a grep-once fix is not a fix. The guard was written to make the phrase impossible, and **the guard
found two more nobody had grepped for**:

```
untell/scripts/audit.py               check_selection_does_not_read_a_bare_max
tests/test_a_pinned_max_says_so.py    the docstring justifying the whole file
```

Five sites. Every one of them explains a *different* correct mechanism — a saturating member pins
`max`, so a selector reading it alone cannot rank candidates — and every one names the wrong member
as the cause. `roberta_openai` clears 0.99 on **2 of 60** HC3 sentences (mean 0.7405) and drops
0.9986 → 0.6228 under rewriting. `hc3_roberta` clears it on **58 of 60** and does not move at all.
The five findings survive the correction untouched; only their explanation changes hands.

**The guard reported itself, and that is now three times in two loops.** Written literally, the marker
string appears in the file doing the scanning, so the first run listed its own path. Same shape as
the guard that forbade `50.0` inside a function whose comment warns against comparing to `50.0`, and
as the dead-function probe that spelled its subject into the haystack it searched. The fix is the one
already established here: assemble the marker at runtime and skip the scanning file.

Verified by putting the phrase back into `targeted.py` — the guard fails; removed — it passes.

Worth keeping: **a fix that does not come with a search is a fix for one occurrence.** I found three
sites by grepping a phrase I happened to remember, and the mechanical guard immediately found two
more. The difference between those two numbers is the whole argument for writing the check instead of
the patch.

## Result 150

**A check I wrote, ran, and deleted — because it examined nothing.**

Result 149's lesson was that a number copied into five files can go stale in four of them. The
obvious next question: which *constants* are quoted in prose, and do the copies agree?

The first sweep found 9 apparent mismatches across all documents. Every one is a historical value in
a dated entry — `free-ceiling-measured.md` states `_CAL_MID = 1.0` and `_CAL_MID = -0.03` in the
entries recording why each was replaced, which is a record, not drift. Scoped to the documents that
describe the current build: **0 mismatches.**

So I wrote the audit check anyway, to hold the line. It passed, and its detail line read:

```
PASS  every constant a live document quotes matches the code  (0 quoted value(s) agree (58 scanned))
```

**Zero.** No live document names a single one of the 58 module-level constants — they are documented
in code comments beside themselves, which is the right place. The check had no subjects and could
never fail. Shipping it would have added a nineteenth green line meaning nothing, to an audit whose
other eighteen were given demonstrated failure paths twelve results ago. Reverted.

**The version with real subjects turned up one hit, and the hit was my harness.**

```
detectors/binoculars.py says _CAL_MID = 0.9, but detectors/fast_detectgpt.py has 0.2
```

`binoculars.py` defines its *own* `_CAL_MID = 0.9`. The scan keyed constants by name alone, so two
modules legitimately sharing a name collided and one overwrote the other. 5 cross-file quotes
checked, **0 real disagreements** — and this repository's own `check_no_shadowed_definitions` already
draws exactly the distinction I dropped: a name defined twice *in one module* is a defect, the same
name in two modules is not.

Fourth time this session that a probe's own flaw produced a false finding, after the harness that
swallowed a traceback, the dead-function name written into its own haystack, and the marker string
the scanner found in itself.

Worth keeping: **declining to ship a green check is a result.** The pressure runs the other way —
the check was written, it worked, it passed, and adding it would have looked like progress on the
audit's coverage. A check with no subjects is worse than no check, because the next person reads the
PASS as evidence.

## Result 151

**Four bad probes in one session, and the permanent ones had never been asked the same question.**

Every one of those four was a throwaway script — a harness that swallowed a traceback, a
dead-function scan that wrote its subject into its own haystack, a marker scanner that matched
itself, a constant sweep that ignored module scope. `eval/tells_auroc.py` is not throwaway. Its
output is quoted throughout the catalogue as the evidence that a tell separates the classes, and
nothing had ever checked that it *can* be wrong.

Three known-answers, run against the real tool on 30 HC3 pairs:

```
real pairs         AUROC 0.8906
identical halves   AUROC 0.5000     <- must be chance; there is nothing to find
swapped labels     AUROC 0.1094     <- inverts to four decimals
precision_table on identical halves: 8 rows, 0 claiming a direction
```

**All three hold.** No defect — that is the honest answer, and the middle row is why it was worth
asking: a tool reporting separation on identical inputs is not measuring the corpus, and every number
it has published would be an artefact of its own plumbing.

Made permanent, on synthetic text so it needs no download and runs in 0.4s. Verified the only way
this kind of test can be — by breaking the tool. Swapping the argument order inside `measure()`,
which is exactly the defect that would publish inverted numbers:

```
FAILED test_the_probe_finds_a_difference_that_is_there
```

**Only one of the five caught it, and that one is the premise test.** A symmetric swap still inverts
symmetrically, so the invert check passes and the identical-halves check passes — 0.5 is 0.5 either
way. The assertion that the tool finds a difference that genuinely exists is the only one that sees a
global inversion. Written as a premise, doing the real work.

Worth keeping: **a measurement tool needs the same known-positive discipline as the code it
measures.** The audit's eighteen checks got demonstrated failure paths thirteen results ago; the
tools producing the repository's headline numbers had none, and one of them has already published two
figures that no longer reproduce.

## Result 152

**Separation is not headroom, and that is why a clean detector audit never surfaced the pinning.**

Result 151 gave one eval tool a known-positive and named the rest as uncovered — which is the "fix for
one occurrence" defect from two results earlier, so: the same treatment for `detector_audit`, driven
with synthetic detectors whose correct verdict is known and no models to download.

```
perfect    (1.0 on AI, 0.0 on human)   OK_SEPARATED   auroc 1.0
inverted   (0.0 on AI, 1.0 on human)   INVERTED       auroc 0.0    <- not mistaken for good
constant   (0.5 always)                DEAD           range 0.0
saturated  (1.0 always)                DEAD           range 0.0
no available()                         AVAIL_ERR      — not guessed at
```

All correct. The middle two are the failure modes this repository has actually shipped — a detector
returning exactly 1.0 disabled candidate selection in the default rewriter — and the tool names both.
**No defect.**

**The fifth shape is the finding.** A detector fine-tuned on the corpus it scores separates perfectly
and has nothing left to give: `hc3_roberta` on HC3 runs human 0.08 against AI 0.9992, the whole AI
spread across 15 documents measuring 1.2e-05. Audited:

```
verdict OK_SEPARATED   auroc 1.0   gap 0.9192   range 0.9192
```

Healthy, and rightly so. **Separation and improvement headroom are different quantities.** This tool
measures the first; the loop needs the second; a detector can be flawless at one while offering none
of the other. That is the whole reason four results went by with a green detector audit while the
headline number was pinned — nothing was broken, and nothing was measuring the thing that mattered.

Verified by breaking the tool: collapsing `INVERTED` into `OK_SEPARATED` — perfect separation in the
wrong direction, which an audit reading only `|AUROC − 0.5|` would call excellent — fails exactly the
one assertion written for it.

Worth keeping: **a green check is only evidence about the question it asks.** The detector audit was
right every time it ran. Reading it as "the detectors are fine, so the loop should be making
progress" was the error, and it was mine, not the tool's.

## Result 153

**The comparison harness already had the control it needed, and nothing checked that the control was
controlling.**

Third and last of the eval tools that publish numbers. `baselines.noop` and the `none (raw AI)` row
in `compare_humanizers` exist to show what an untouched document scores; every other row is read as a
delta against them.

```
noop        text unchanged True, iterations 0, pre max == post max (0.8667), similarity 1.0

compare(), 2 texts, lite tier:
    none (raw AI)          ai_max 0.5703   tells/100w 28.68   sim 1.000   flagged 0.5
    synonym_swap           ai_max 0.5198   tells/100w 23.55   sim 0.947   flagged 0.5
    back_translation       ai_max 0.4434   tells/100w 19.16   sim 0.807   flagged 0.5
    ours_loop (surgical)   ai_max 0.5023   tells/100w 16.94   sim 0.815   flagged 0.5
    ours_loop (composite)  ai_max 0.2619   tells/100w 15.21   sim 0.833   flagged 0.0
```

Both behave. **No defect** — the third eval tool in a row where the honest answer is that it works,
and the third where nothing had ever demonstrated it could fail.

The control's **sim 1.000** is the load-bearing number. Against 0.807–0.947 for the strategies, it is
the only row proving the harness reports an untouched document as untouched. `noop`'s own docstring
records what happens when a control drifts from its strategies: `tier` used to be swallowed by
`**_kw` and hardcoded to lite, so at `--tier full` the control row and the strategy rows came from
different detectors — noop pre_max 0.5323 against single_pass pre_max 1.0000 on the same text. A
comparison between two different measurements.

Verified by making `noop` delegate to a real strategy — a control arm that quietly rewrites, which
would make every delta in the published table meaningless. Three of the five assertions fail. The
first attempt at that mutation was malformed and died at import with a `NameError`, which is not a
demonstration of anything; a collection error and a caught defect look equally red and mean opposite
things.

`compare` itself is asserted structurally rather than run: `back_translation` pulls a Marian model,
and a test that downloads 300MB to confirm a table has a header is a test nobody keeps. The
behavioural evidence was taken once by hand and lives in the file's docstring.

Worth keeping: **a control is a claim, and an unchecked claim is decoration.** Three eval tools, three
clean answers, three demonstrated failure paths that did not exist before — and the reason to write
them is that two of this repository's published figures had already stopped reproducing without
anything noticing.

## Result 154

**Genuine human writing, reported as 99.2% AI, with `warning: None`.**

A question about the product rather than the machinery: what does the loop do to text that is already
human? Mostly the right thing. Of 8 real HC3 answers at `tier=full`, **6 came back byte-identical**,
similarity 1.000 — the loop only rewrites what the detectors flag, so text nobody flags is text
nobody touches.

The other two were rewritten, and the loop was not at fault: they were flagged at **0.9922** and
**0.9862**. The detectors were wrong, and the loop did exactly what it is told to do with a flagged
document.

So: how often, and is anyone told? MEASURED on 30 genuine human texts per corpus at `tier=full`:

```
corpus   flagged (>=0.45)   above the loop bar (>=0.30)   mean max   carrying a warning
HC3        5 / 30  (17%)          5 / 30                    0.259           0
RAID       0 / 30  ( 0%)          0 / 30                    0.141           0
```

**Nobody is told.** The lite path already carries a loud false-positive caveat — *"64% of HUMAN text
scores above the 0.30 loop threshold"* — and the FULL path, the one the README tells people to
install, said nothing at all. `ai_percent` 99.2 on prose a person wrote themselves, arriving bare.

**The corpus split is the substance, not a footnote.** HC3 human answers are casual forum Q&A, which
is the register someone actually pastes when checking their own writing; RAID's are paper abstracts.
A single pooled rate would understate exactly the case that matters, so the note quotes both.

The wording had to survive being read by someone whose text really is AI, so it makes a claim about
what a flag *proves* rather than about which way this verdict went — and it appears only when
`flagged` is true, because a caveat on every call is a caveat nobody reads.

Worth keeping: **the honest-limits discipline was applied to the weak path and skipped on the strong
one.** The lite tier gets a paragraph about its false positives because it is obviously weak. The
full tier is the one people trust, flags 17% of conversational human writing, and had no note at all
— the caveat is needed most exactly where the number looks most authoritative.

## Result 155

**Eight sentences, one distinct score, and the tool named "the worst third" of them.**

Result 154 found an honest-limits caveat applied to the weak path and skipped on the strong one, so:
which others are conditioned on the tier rather than on the risk? Sweeping for it left two sites. One
was 154's. The other is `_targeting_is_uninformative`, which suppresses the near-chance warning as
soon as any model-backed detector is present.

That function asks whether the DETECTOR is any good. The question a caller needs answered is whether
**this document's** sentences can be ordered at all — and the two come apart completely. MEASURED at
`tier=full`, spread of per-sentence `max` within one AI document, 10 documents per corpus:

```
corpus   mean spread   median   below 0.05   distinct values / sentences
HC3        0.0088      0.0022      9 / 10            0.36
RAID       0.6595      0.6855      0 / 10            0.99
```

Same tier, same detectors, opposite answers. **Two HC3 documents in eight returned one distinct value
across eight sentences** — every sentence exactly 0.9992, so "the worst third to rewrite first" was
whichever order the sort produced. On RAID the ranking is almost perfect.

The cause is the one Result 143 named: `hc3_roberta` is fine-tuned on HC3 and sits at its ceiling on
every sentence of it. Which makes **tier the wrong condition in both directions** — silent where the
ranking is arbitrary, and it would be noisy on RAID where the same tier ranks well.

So the caveat now reads the document's own spread. Corpus-independent, needing no knowledge of what
any detector was trained on, and firing exactly when the order cannot be trusted. 0.05 sits in the
empty gap: HC3's worst document reaches 0.0610, every RAID document exceeds 0.5. Verified after
wiring — fires on **7/8 HC3** documents and **0/8 RAID**, which is the measurement, reproduced through
the shipped path.

Worth keeping: **a proxy for a property is not the property, and the gap shows up as silence.** "Is
the detector weak" was a serviceable stand-in for "can these scores be ranked" right up until a
strong detector met text it was trained on. The fix was not a better proxy; it was measuring the
thing itself, which turned out to be one subtraction.

## Result 156

**The two-directional check was there. It was starved of inputs.**

The key added one result ago reaches `/sentences` — and the published schema does not mention it:

```
returned:   flagged, note, sentences, threshold, tier, unrankable, warning
documented: flagged, note, sentences, threshold, tier, warning
```

The adjacent-surface defect again, on my own change, one loop later. But the interesting part is why
nothing caught it. `test_no_returned_field_is_undocumented` exists and runs payload → schema. It was
written precisely because the check used to run one way only, and its docstring says so:

> *A one-directional check on a two-directional invariant is the same shape as an allowlist that only
> fails on additions: it holds while the drift runs the way it happens to be looking.*

It passed anyway. Its `/sentences` body is two sentences, and `unrankable` needs at least three to
have a spread worth judging. **A directional check is only as good as the payloads it exercises**, and
a key that appears only under a particular input shape is invisible to one that never produces that
shape. Same hole, reached from the other side.

**My first fix for that was itself starved, and the guard-the-guard caught it.** I added a third
sentence, on the theory that three was the minimum. Measured through the endpoint, that body spreads
**0.7577** — genuinely rankable, correctly no key. Deleting the schema entry to check the test would
notice: it still passed. The payload that works scores every sentence identically, spread **0.0**,
and is now the one in the table.

Also: `git checkout --` on an uncommitted fix threw the fix away mid-verification, so the "restored"
run was measuring a file with no fix in it. Backed up to a temp copy instead. Two mistakes in one
verification, both of the same kind — checking that a guard fires without checking what it was
looking at.

`unrankable` is now documented, and listed as conditional in the staleness check with the proof that
set demands: it fires on 7 of 8 HC3 documents and 0 of 8 RAID, so both branches are reachable and
neither is the default.

Worth keeping: **"we check both directions" is a weaker claim than it sounds.** Direction was the
last gap in this test and it was fixed. Coverage of the conditional branches is a second gap in the
same test, invisible from the first, and a green two-directional check gave no hint of it.

## Result 157

**The schema check verified two of eleven conditional fields, and its busiest endpoint was not in the
table at all.**

Result 156 found `unrankable` shipping undocumented past a payload → schema check that ran the right
direction and never saw the key. The obvious next question: how many of the API's conditional fields
does that check ever actually observe? Replaying its own `CALLS` table and collecting every response
key:

```
conditional fields produced   2 / 11
never produced                detector_errors, error, failed_detectors, matches,
                              out_of_range_detectors, out_of_range_raw, rewriter_warning,
                              suggestion, voice_warning
```

Two — and both only because last result added the payload for one of them. Nine documented fields
could each be typo'd, mistyped, or unreachable, and the check that exists to catch exactly that would
pass.

**`/humanize` was absent from the table entirely.** Nineteen response keys, the endpoint the whole
project is for, never inspected by the check that verifies its documentation.

Two payloads reachable without failure injection now cover two more: `/tells` with
`include_matches` (false by default, so `matches` had never appeared in a response this check read)
and `/humanize` with a two-word voice sample, under the 20-word floor, which produces
`voice_warning`. **2 of 11 → 4 of 11.**

**Adding `/humanize` immediately failed the other direction**, and the reason is a defect rather than
a nuisance: `rewriter_warning` is documented, conditional, and correctly absent — but this file kept
its own conditional list, which had drifted from the one in
`test_the_openapi_schema_matches_the_response.py`. Six fields in that set, none in this one. Two
vocabularies for one API, now imported from one definition, at the **fourth** layer this session where
the same shape appeared — detector and remedy vocabularies, sign-off pattern and unit, the pinned
detector's name in five files, and now two conditional-key sets.

The seven still uncovered need a broken detector, an out-of-range score or a missing rewriter, which a
static table of request bodies cannot express. They are exercised by monkeypatching tests elsewhere
and **not** by this check, and that number is now written into the class docstring rather than left
for the next person to rediscover.

Worth keeping: **a check's coverage is a measurement, not a property of its name.** "The schema
matches the response" sounds total. It was two elevenths, and nothing in a green run said so.

## Result 158

**Eight caveats nothing had ever seen appear.**

Result 157 measured how much of the API's conditional surface its schema check observes: 2 of 11. The
same question one layer over — this repository's honesty argument is carried by its *caveats*, the
sentence beside a number saying what the number is worth. Listing every function whose name says it
produces one:

```
17 caveat-producing functions, 8 never named in any test
    humanness    _warn_too_short, _warn_band_unreliable, _warn_unsupported_language,
                 _warn_about_the_weak_path
    preserve     _warn_no_ner
    run          _warn_voice_sample_too_short
    sentences    _warn_if_targeting_is_uninformative
    voice        _warn_if_sample_is_thin
```

Named-in-a-test is a weak proxy, so each was driven with an input that should trigger it. **All eight
fire.** No dead caveat — the honest answer, and worth having rather than assuming, because a caveat is
exactly the code the happy path never touches and whose absence nobody notices. The half of the
repository that says "this number is weak evidence" had less coverage than the half that produces the
number.

**The one that needed two attempts is the lesson.** `voice._warn_if_sample_is_thin` first reported
`AttributeError` — my probe called a function that does not exist. A probe failing and the subject
failing look identical from outside, and only reading the error told them apart. Fifth time this
session.

Now a permanent battery, one known-positive per caveat, each resetting the warn-once flag first —
without that, the second test to touch a module finds the flag already spent and reads silence as a
defect. Plus one known-negative: a 200-word voice sample must produce nothing, because a caveat that
fires on everything says nothing.

Verified by silencing one — the classic warn-once defect, an early `return` before the flag check —
which fails exactly the assertion written for it.

Worth keeping: **the code that admits a limit is the least-exercised code in any honest project.** It
runs only when something is wrong, so the tests that would catch it broken are the ones nobody writes
— and this repository's entire argument rests on those sentences arriving.

## Result 159

**A caveat on a result is not a caveat a person reads, so I traced one to every surface — and my
test asserted a contract the design does not make.**

Result 154 put a false-positive note on `score_text`: what a flagged verdict is worth, measured at 5
of 30 genuine human answers flagged at `tier=full`. Result 158's lesson was that caveat code is the
least-exercised code there is. So: does it arrive? Traced on a flagged human answer at `tier=full`:

```
score_text result          carries it
untell_text result         carries it
untell-score terminal      prints it
untell humanize terminal   prints it   (in a Warning panel)
REST /score                carries it
REST /humanize             carries it, and on `pre` as well
```

All six. **No defect** — the merge chain was built correctly before this note existed, so a fix to one
function propagated everywhere without anyone arranging it.

**Then the test failed at the lite tier, and it was right to.** Three assertions went red. Not a
propagation bug: on that run `pre` was flagged at **0.7429** and `post` came back **0.3772** —
cleared. The loop merges the caveat from the score it *reports*, which is `post`, and a document with
no flagged verdict has nothing to qualify. The note had survived at `tier=full` only because the text
stayed flagged there.

So the contract is narrower than the six green rows suggested: **the caveat follows the verdict, not
the input.** `pre` keeps its own copy, so a caller showing the before-number still has the
qualification beside it. Nothing is lost; it is attached to the right thing.

The tests now say that — present exactly when `post` is flagged, and on `pre` whenever `pre` is —
rather than the stronger claim that happened to hold on one tier. **A test written from a single
tier's observation is a test that encodes a coincidence**, and this one would have failed the moment
the loop got better at clearing text.

Worth keeping: **a passing trace across six surfaces told me less than one failure did.** The green
rows confirmed plumbing I already believed in; the red one taught me what the plumbing actually
promises.

## Result 160

**The transform that deletes sign-offs was deleting citations, against a promise on the front page.**

A product question rather than a machinery one: the README says untell keeps *"your meaning,
citations, and facts intact."* Six citation forms through the loop — numeric `[1]`, author-year,
DOI, URL, bracket range, footnote marker — all survive, and the text genuinely changed in five of
six, so it is preservation rather than inaction.

Five adversarial placements — a citation inside a deleted stance frame, inside `In conclusion,`,
inside a stripped sign-off, inside a parenthesised aside, at a merge boundary — also all survive.
**But two of those five did not change at all**, and an unchanged document proves nothing. Isolating
the transform instead of the loop:

```
REMOVED   I hope this helps!
REMOVED   I hope this helps [3]!
REMOVED   I hope this helps, see [3] for the derivation.
REMOVED   Let me know if you need the data (Smith 2020).
REMOVED   I hope this helps https://example.org/paper.
```

**Every reference deleted.** A numeric marker, a citation with context, an author-year form and a URL,
each short enough to pass the six-word remainder test that decides what counts as pure scaffolding.

The rule counts WORDS, and a citation is worth more than its length. That is my own transform and my
own remainder constant, and the loop-level test missed it precisely because the runs that would have
shown it were the ones where nothing changed.

The fix defers to `preserve._collect_spans` rather than adding a citation pattern beside the
scaffolding test. That layer already covers both citation forms, URLs, DOIs, emails, identifiers,
dates and quantities — and a private copy of any of it would be the two-vocabularies defect this
session has now found at five layers. Pure sign-offs still go; anything carrying a reference stays.

Worth keeping: **an unchanged output is not evidence of preservation.** Five of five adversarial
placements passed at the loop level, two of them because the loop did nothing at all — and the
transform underneath was destroying references in every case I then tested directly. The end-to-end
test looked like the stronger evidence and was the weaker one.

## Result 161

**Eight transforms delete text and keep citations. Two delete whole sentences, and only one had the
guard.**

Result 160 fixed a sign-off stripper that was deleting references. The sibling question: does anything
else do it? Every phrase-deleting transform, with a citation adjacent to the deleted span:

```
_flatten_cliches (stance frame / in conclusion / bottom line)   kept
_strip_filler_openers                                           kept
_flatten_vague_attribution                                      kept
_semicolons_to_periods                                          kept
_parenthesise_asides                                            kept
_flatten_participial_trailers                                   kept
```

All safe, and the reason is structural rather than lucky: they delete a **phrase**, and a citation
beside a deleted phrase is not inside it. Sentence-level deletion is the dangerous class, and the
codebase has exactly two.

The other one, `_drop_restatements`, was **already** correct — and by design. Its docstring: *"never a
sentence carrying a preserve-lock sentinel, which by definition holds a citation."* So the guard I
added last result was not a new idea; it was bringing an outlier into line with a precedent sitting
one function away in the same file.

**And that precedent showed the fix was verified against the wrong text.** It keys on the *sentinel*,
because the loop locks preserved spans into `⟦HZ…⟧` before any transform runs — the production path
never sees a raw `[3]`. A fix tested only on raw citations could have deleted every reference in real
use. Measured on the locked form: all three kept. Correct on both paths, now asserted on both.

**Establishing the premise took three corrections.** `_drop_restatements` returned early under four
sentences, then dropped nothing at all, then needed the restatement out of the excluded first and last
positions. Each intermediate run "passed" and proved nothing — the same shape as Result 160's
unchanged-output-is-not-preservation, met twice in two results, in my own probes both times.

Worth keeping: **before adding a guard, look for the one already there.** The transform written five
results ago lacked a check that a neighbouring function documents in its own docstring. Nothing
pointed from one to the other, and the sentinel detail — the thing that makes the guard work in
production rather than only in a test — lived only in the prose of the function that got it right.

## Result 162

**A constructed pair said the meaning gate was reading garbled text. Real text said otherwise.**

Result 161 established that production runs on *locked* text — every citation replaced by a `⟦HZ…⟧`
sentinel before any transform sees it. So: what do the meaning gates see? The loop calls
`similarity(masked, candidate)` and `meaning_preserved(masked, candidate, …)`. An embedding model
comparing opaque tokens is not comparing the document.

Constructed evidence looked damning — three locked spans across two sentences moved similarity
**0.8974 → 0.9304**, inflated, the direction that admits a bad rewrite. And the asymmetry was real:
the *targeting* path one screen above carries a careful masked-vs-restored analysis with its own
measurement, while the gate's comment discussed similarity-versus-NLI at length and never mentioned
which text it reads.

Measured on real rewrites — 38 of 50 corpus texts lock a span, so this is the ordinary case:

```
similarity masked - restored   mean -0.0014   max +0.0091   min -0.0218
verdict disagreements          1 of 38, and it runs the SAFE way:
                               masked rejected what restored would have admitted
```

**No defect.** My probe generalised from a citation density real documents do not have — three locked
spans in two sentences against a corpus mean nearer one span per paragraph.

And masking turns out to be principled rather than merely harmless: the sentinel-integrity check
immediately above the gate has already rejected any candidate whose sentinels differ, so the locked
spans are provably identical on both sides. Comparing them again adds no information; what is left is
exactly the prose the rewriter changed.

The measurement now sits at the gate, and a test pins the **direction** rather than the number — if
masking ever starts admitting what the restored comparison rejects, the trade stops holding.

Worth keeping: **a hypothesis built from a constructed example inherits the example's shape.** Density
was the hidden variable. The number I measured was real, the pair was legitimate, and it described a
document this corpus never produces.

## Result 163

**Every evasion figure in this document was scored by the objective the loop optimises. Held out, the
number stops moving.**

158 results of tuning, and the arm nobody had run: the loop minimises `max` over the full tier and
then reports `max` over the full tier. `best_of` — named throughout as the single biggest lever — is
precisely the mechanism that exploits a scorer rather than the property it stands for.

The control was already in the package. RADAR is adversarially trained against a paraphraser and
gated behind `UNTELL_ENABLE_RADAR=1`, so it has never been in a selection set or in a published
figure. That gate is what makes it a holdout; `eval/benchmark.py --enable-radar` puts it *inside* the
tier, which asks the opposite question. Premise checked first — on RAID it separates AI 0.7978 from
human 0.0909, paired 8/8.

RAID, n=10, shipped configuration (`composite`, `best_of=3`, `max_iters=5`), three seeds, RADAR
scored afterwards on frozen outputs:

```
in sample   0.9162 -> 0.4268 / 0.4063 / 0.4301    flagged 10/10 -> 4 / 2 / 3
held out    0.7222 -> 0.4981-0.5035 / 0.4391      flagged  7/10 -> 4 / 4 / 4
```

**The in-sample flagged count varies and the held-out one does not.** Seed 1 drove the local ensemble
to 2 of 10 — its best run by a wide margin — and finished at the same 4 of 10 out of sample as the
seed that only reached 4. Per document, the two documents that never clear:

```
doc | RADAR pre | held out post s0/s1/s2 | tier post s0/s1/s2
  0 |   0.9514  | 0.973 0.940 0.980      | 0.630 0.666 0.606
  6 |   0.9996  | 1.000 1.000 1.000      | 0.345 0.382 0.607
```

Doc 6 is the result in one row: the loop reports **0.9928 -> 0.345**, a clean in-sample success, and
the held-out detector reads **1.000 on all three seeds**. Rank correlation between the two post
scores is **+0.394 / +0.782 / +0.333** — the local `max` does not order documents the way an unseen
detector does, and how much it disagrees is itself unstable.

**The first version of this result was wrong, from one seed, and it was the better story.** Seed 0
split by what the holdout believed beforehand looked decisive: documents it was already confident
about (>=0.90) moved **-0.0129** while their in-sample max moved -0.5262, against **-0.3560** for the
unsure ones — "the entire gain comes from documents the control had no conviction about". The
repeats gave `-0.2321 / -0.2189` and `-0.2745 / -0.2890`. **No split at all.** One document with a
0.9991 prior fell to 0.288 on the second seed. Four documents, one draw of a stochastic rewriter, and
a mechanism that does not exist. This document's own rule — `--repeats >= 3`, written after a config
measured 0.080 and 0.144 on two runs — is the only reason it did not ship.

Two premises were tripped while taking the measurement, both silent:

- **`mage` pins the in-sample column.** The first run reported `1.0000 -> 1.0000` on every document.
  At full precision `mage` scores ordinary AI prose at **0.99998736-0.99998772** — a range of
  **3.6e-06** across ten texts — and it is in the *default* full tier, while every published figure
  here is taken with `UNTELL_DISABLE_MAGE=1`. Nothing cleared, so the transfer question had no
  subject. This is the Result 143 distinction again: *effectively pinned* is not *returns a constant*,
  and only one of them is true.
- **A control inside the tier it is controlling** is not a control. Guarded — the harness raises
  rather than producing a number.

`eval/holdout.py` makes the arm permanent, with the premise check inside the result (`separates`) so
a caller cannot quote a transfer figure computed through a dead detector. Eight tests on fakes, 1.8s,
no download; verified by breaking the pinned threshold, which fails exactly the one assertion written
for it.

What this does **not** say: RADAR is the hardest open detector by construction, so this is a lower
bound on transfer rather than a typical one, and it is one holdout on one corpus at n=10.

Worth keeping: **an objective you also report is not a measurement, and no amount of tuning it will
say so.** Four detectors were recalibrated, a selector was fixed, a beam search was refuted and a
corpus was rescoped — 158 results, all of them read through the quantity being optimised. The one
number that answers "is any of this real" cost one afternoon and a detector that was already on disk.

## Result 163b

*(Renumbered. This heading collided with Result 163 above; the number is suffixed rather than reassigned because Result 163 is cited by name elsewhere in the repository and those citations mean the earlier one.)*

**A defect I read out of a diff did not exist, and chasing it found a real gap in how the pipeline
can be tested.**

Reading real rewriter output — the discipline this log records as "metrics cannot see grammar" — a
diff showed `"It's important to note that the"` becoming `"Additionally, the"`. `Additionally,` is a
catalogued `formulaic_transition`, so this looked like a cliché traded for a tell: the
fourteen-times defect this repository already carries a name for.

**It was not.** `Additionally` was in the SOURCE and the rewriter removed it — `formulaic_transition`
went **3 → 0** across those six documents. difflib had aligned a deletion in one place against
unrelated text elsewhere. Reading a diff without the source beside it manufactured a defect, exactly
as at Result 114.

Measured properly instead — every category, 60 corpus texts, 60 real rewrites:

```
DECREASES   repeated_phrasing -134   ai_vocab -55   formulaic_transition -31
            repeated_sentence_openers -28   cliche -11   hedge_stacking -4
            participial_trailer -2   negated_contrast -1
INCREASES   repeated_sentence_openers +13   repeated_phrasing +2
```

Net-negative on every category. Only `_vary_openers` emits at all — 13 against 28 removed, its known
budgeted cost.

**Then the guard-the-guard failed, and that was the real finding.** Making `_flatten_cliches`
substitute `"Additionally, "` for every deletion — the precise defect being guarded — makes that
function emit `"Additionally, the method scales well..."`, and the **full pipeline still scores
`formulaic_transition` 0**, because a later transform strips catalogued transitions. Every
output-level assertion stayed green.

That is a property of the pipeline rather than a hole in it: a user gets clean text either way. But
it means **the output contract cannot see a component regression** — a transform can rot while the
end-to-end number stays perfect, and the number is what everyone checks. Each transform is now
asserted directly, and with that in place the same mutation fails exactly one test.

Worth keeping: **a pipeline that repairs its own components hides their decay.** The robustness that
protects the user is the same property that blinds the test, and only a component-level assertion
separates "nothing is broken" from "everything downstream is compensating".

## Result 164

**The other substitution table, asked the question the first one was fixed for.**

Result 163 asserted per-component that no structural transform emits a catalogued tell. The sibling:
this repository once shipped **fourteen replacements whose output was itself in the catalogue** — a
swap that moves a word between flagged columns while the total sits still. That was fixed in one
table. `_SYN` is the other, 226 source words and 615 replacement strings, hand-maintained, never
asked.

```
226 source words, 615 replacement strings
replacements that are themselves catalogued ai_vocab     0
replacements that introduce ANY catalogued category      0
source words that ARE catalogued tells                   121 / 226
```

**No defect** — and the last row is what makes the first two mean anything. The map is pointed the
right way round: it takes `delve`, `leverage`, `utilize`, `robust`, `seamless` and 116 others *out*.
A table that touched no tells at all would score zero emissions too, and be useless.

**Two probe errors, both caught by controls I had written for exactly that.** The first sweep read
`surgical._SCOREABLE` — a tier set, not a substitution table — and reported "0 emissions" from 4
strings that were never replacements at all. And the carrier's positive control failed on `"delved
into"`: the catalogue holds `delve`, matching is whole-word, and an inflection is a different token.
**A positive control built from a near-miss proves nothing**, and that one caught its own author
before the file could ship a vacuous zero.

Verified by adding a replacement that is itself catalogued, which fails both assertions.

Worth keeping: **"zero emissions" and "zero opportunities to emit" print the same number.** Every
clean result this session has needed a second measurement establishing that the thing measured was
capable of being dirty — the wrong table, the untouched document, the near-miss control. The zero is
never the finding; the denominator is.

## Result 165

**Running it twice changes nothing — and the interesting part is how few documents could prove it.**

Users re-run tools. Nothing had checked what the second pass does, and the risk is specific: the
meaning gate compares each candidate against the **current** input, not the original, so a gate that
admits a small drift admits it again from the new baseline. No single step fails, and the document
walks away from its source.

MEASURED at `tier=lite`, `structural`, `max_iters=2`, `best_of=1`, seed fixed, 8 HC3 answers. Every
document ran its full two iterations, so nothing short-circuited:

```
doc  tells0  tells1  tells2  sim(1,2)  changed by 1st  changed by 2nd
 1     23      23      23     1.000        no               no
 3      1       0       0     1.000        yes              no
 4      4       0       0     1.000        yes              no
 5      0       0       0     1.000        yes              no
 6     28      28      28     1.000        yes              no
 7      1       0       0     1.000        yes              no
 8     13      13      13     1.000        no               no
```

**Byte-identical on the second pass, every time.** But three documents adopted no candidate on the
first pass either, and a loop that does nothing is trivially stable — so the real evidence is **5 of
8**, not 8 of 8, and the test says so.

That is the previous result's lesson arriving one loop later in a new costume: *zero drift* and *zero
opportunity to drift* print the same number. Half of this measurement was denominator.

Two probe errors on the way, both mine. A `grep -v '^ +'` written to strip a stderr traceback ate
every indented row of the results table, leaving only the summary line — I nearly wrote up a finding
from a table I had filtered away. And the three unchanged documents looked like a failure to improve
until I checked `stopped` and `changed`: `lite` + `structural` + `best_of=1` is the weakest path the
tool offers, and adopting nothing when no candidate beats the incumbent is correct behaviour, not a
defect.

Worth keeping: **a stability property is only as strong as the instability it was given a chance to
show.** Idempotence measured on documents the tool declines to touch is a measurement of nothing, and
it reads exactly like a clean result.

## Result 166

**A code block was reported as 99% AI-adjacent with nothing said about it being code.**

An input type nobody had tested and everybody pastes: a README section, a config block, a table.
MEASURED at `tier=lite` on a pure 272-word Python fence:

```
flagged: True    stopped: max_iters    changed: False
```

The loop ran every iteration, adopted nothing, returned an AI verdict — and the only caveat attached
was the generic lite-path one. Nothing said the document contains no prose, that the rewriter had
nothing it was permitted to touch, or that the detectors were scoring a kind of text they were never
built for. Every other "this verdict is undefined" case in this repository has a note: text too
short, script the catalogue cannot read, detectors that failed to load. Not this one.

**The discriminator already existed**, which is the part worth remembering. `layout._prose_line_mask`
marks the lines the rewriter is allowed to edit, and it is stdlib-only with no intra-package imports:

```
pure code fence     0 of 62 lines prose
ordinary prose      1 of 1
prose + a fence     1 of 64
```

Zero of 120 corpus texts have no prose line, so the note cannot fire on real writing. The work was a
scan and a sentence; the missing piece was the question.

Coverage is written down rather than implied. It fires on fenced code, tables and YAML front matter,
and **not** on a bullet list or a bare URL list — `_prose_line_mask` counts list items as prose
because the rewriter does rewrite them. Right for bullets, a miss for URLs, and a caveat firing on
every list would be noise on the commonest markdown there is.

The wording claims the verdict is **undefined** for this input rather than that the input is
innocent, so it survives being read by someone whose code really was machine-written.

Worth keeping: **the same question asked of a different input type is a different question.** Nine
results of asking "what does this tool say when it cannot answer" had covered short text, foreign
script and dead detectors. Code was not a harder case — it was an unasked one.

## Result 167

**Ninety percent of a witness statement was locked, and the verdict was reported as if it were the
user's writing.**

Result 166 asked what the tool says when it cannot answer, and found code. The same question of a
different input type: quotation. It lands in the same place by a different mechanism — there the
rewriter had no prose lines, here it has prose it is **forbidden to alter**.

```
locked 321/357 characters (90%), 2 spans
flagged: True    changed: False    stopped: max_iters
```

Every iteration ran, nothing was adopted, and the result said nothing about it. This is the worse of
the two cases, because the detectors scored the quotations as well: **the number describes somebody
else's words**, and the person reading it is being told something about their own writing.

```
120 corpus texts, locked character share
median 0.023    p90 0.072    p99 0.137    max 0.177
quote-heavy probe                          0.899
```

Nothing in the corpus passes 0.30, so a 0.50 bar sits in an enormous empty gap — this is one of the
cleanest separations measured in this log, and it needed no tuning.

Two wording decisions carry the honesty. **"Preserved material" rather than "quotations"**, because
`lock` also holds citations, figures, dates and URLs, and a note naming only quotes would misdescribe
a statistics-dense paragraph. And the claim is that the verdict is *largely about text this tool
cannot change* — not that the text is innocent — so it survives a reader whose quoted matter is
itself machine-written. A single quotation in a paragraph stays silent, or the note fires on every
piece of journalism ever written.

Worth keeping: **two mechanisms, one user-visible failure.** No-prose and mostly-locked have nothing
in common in the code — one reads a line mask, the other a span table — and produce the identical
experience: a confident verdict on a document the tool could not work on. Enumerating *mechanisms*
would have found them separately and late; enumerating what a user might paste found the second one
immediately after the first.

## Result 168

**The free ladder's top rung is a 220M paraphraser. A 1.5B instruct model is better at evading and
worse at rewriting, and the meaning gates are what notice.**

Result 163 established that in-sample gains stop transferring, so the question is what would move the
held-out number. Not search — beam is refuted (Result 48) and width bought nothing. The untried axis
is the proposer: rules plus T5-**base** is the whole free ladder, while
`LocalPolicyRewriter(use_adapter=False)` has existed all along for base-model A/B, is unreachable
from `get_rewriter()`, and had never been measured. Qwen2.5-1.5B-Instruct, CPU, no key.

RAID n=5, `best_of=2`, `max_iters=2`, scored in sample and against the RADAR holdout:

```
doc | tier max pre -> post | RADAR pre -> post | sim
  3 |   0.9591 -> 0.1587   |  0.9991 -> 0.0811 | 0.892
  0 |   0.9998 -> 0.9998   |  0.9514 -> 0.9514 | 1.000
  1 |   0.9983 -> 0.9983   |  0.8323 -> 0.8323 | 1.000
  2 |   0.7555 -> 0.7555   |  0.7835 -> 0.7835 | 1.000
  4 |   0.9998 -> 0.9998   |  0.4467 -> 0.4467 | 1.000
```

**Four of five came back byte-identical, and the fifth is the best held-out result this document has
recorded from any rewriter.** Doc 3 is the document composite leaves RADAR-flagged on two of three
seeds (0.999 / 0.288 / 0.457); here it lands at **0.0811**, against a genuine-human mean of 0.0829.

`sim 1.000, stopped max_iters` is what a silent proposer and a fully-vetoed one both print, and they
have opposite fixes. The proposer is not silent — it returns 92-98% length candidates every time.
Running the seven vetoes individually on its output, in `meaning_preserved`'s own order:

```
doc | sim    | tier max        | numbers certainty polarity  words_lost      contra  entail  roles
  0 | 0.9363 | 0.9998 -> 0.4446|  True    True     False     9 (allow 31)    0.0035  0.2294  False
  1 | 0.8288 | 0.9983 -> 0.2318|  True    False    False    58 (allow 27) X  0.0213  0.0371  False
  2 | 0.7286 | 0.7555 -> 0.9992|  True    False    False   -47 (allow 13)    0.0148  0.0555  False
```

**Every rejection is correct.** Entailment runs 0.037-0.229 against a floor, contradiction is near
zero, and the candidates open *"In their paper titled ...,"* and *"This research introduces
EdgeFlow"* — third-person reframings of an abstract, not rewrites of it. Doc 1 deletes 58 words
against a 27-word allowance. Doc 2 **expands** by 47 and scores 0.7555 -> 0.9992, worse than the
input: the model's own prose reads as AI, which is precisely the T5 finding one model-scale up
(*"one draw crushed roberta 0.973 -> 0.066, another backfired 0.017 -> 0.999"*).

So the blocker is not capability and not the gates. It is the **prompt**. `_TRAIN_PROMPT` —
*"Rewrite the following text so it reads as natural human writing while preserving its exact
meaning"* — is documented as the exact instruction the policy was RL-trained on, and re-using it on
an **untuned** model is out of distribution in the other direction: with nothing holding it to the
source, an instruct model summarises. Low entailment with near-zero contradiction is the signature of
exactly that, and it is not a defect the gates should be relaxed to admit. Doc 1's candidate scores
0.2318, a clean in-sample pass, and drops a fifth of the content to get there.

What this buys, stated at its real size: one document in five, n=5, one seed, `best_of=2`. The
direction is worth the entry only because of what that one document did to a detector nothing else
has moved. The specific next step is a faithfulness-anchored prompt and sentence-at-a-time rewriting,
which makes deletion and reframing structurally unavailable rather than caught afterwards — and then
the only-ever-help selection T5 already has, at an N that CPU can afford (700s per document at 1.5B
with `best_of=2` is the cost being budgeted against).

Worth keeping: **a stronger proposer is not a better rewriter, and the gates are the only thing that
knows the difference.** Every in-sample number in the failing arm looked like progress —
0.9998 -> 0.4446, 0.9983 -> 0.2318 — and three of three candidates changed the meaning. Without the
vetoes this would have published as the biggest jump in the document.

## Result 169

**A line marker is a sentence start, and the capital-restore pass did not know it. 6 of 7 marker
kinds shipped a lower-case sentence start — and the obvious fix would have damaged text.**

Continuing Result 167's question — what does this tool do with what a user actually pastes — five
more input shapes went through `untell_text` at `tier=lite`: a transcript with speaker labels, verse,
one long unterminated sentence, HTML markup, and numbered legal clauses. Every one came back
unchanged, which by this document's own twice-learned lesson proves nothing, so tell-heavy variants
were forced through `structural_rewrite` at seeds 1/7/13. All produced real rewrites with line
structure exact: 2->2, 3->3, speaker labels, clause numbers and `<p>` tags all intact.

The line counts were perfect. The text was not:

    Alice: organizations must tap these smooth solutions.
    1.3 any defect shall be notified without delay.

`_flatten_cliches` deletes "In conclusion, " and then restores the capital it displaced — its
docstring says so. `_AFTER_SENTENCE_START` finds that start at the beginning of the STRING or after
a terminator, and a line opening with a marker is neither, so the restore never fired. The transform
that exists to remove tells was emitting one: broken capitalisation is itself catalogued.

MEASURED, one cliché stripped from the head of each marked line, through shipped output:

    speaker label   Alice: In conclusion, ...  ->  "Alice: organizations must adopt ..."
    dotted clause   1.3 In conclusion, ...     ->  "1.3 any defect shall be notified ..."
    bullet          - In conclusion, ...       ->  "- the team must use a sturdy approach"
    blockquote      > In conclusion, ...       ->  "> the team must use a solid approach"
    heading         ## In conclusion, ...      ->  "## the team must tap into a solid approach"
    paren clause    (a) In conclusion, ...     ->  "(a) the team must tap into a solid approach"
    numbered list   1. In conclusion, ...      ->  "1. The team must use a sturdy approach"   ok

**Six of seven, not the two the output showed** — bullets and headings are the commonest markdown
there is. The one survivor survived by accident rather than by design: the dot in "1. " reads as a
sentence terminator to the existing pattern, so the old repair fired for the wrong reason.

**The obvious fix is wrong twice, which is the result worth keeping.** Running the restore in
multiline mode breaks soft-wrapped prose, whose continuation lines legitimately begin mid-sentence in
lower case. Restricting it to MARKED line starts is still wrong, because many marked lines are
deliberately lower case:

    (a) the Seller shall deliver ...     how legal sub-clauses are drafted
    - apples / - bananas                 list fragments

Either version edits text nothing had touched. So the rule restores a capital that was there and
never invents one: a line is corrected only when the transform changed it AND the word it now begins
with was capitalised before. Same line, same marker, same edit, differing only in the source:

    "- In summary, the plan"  ->  "- The plan"
    "- in summary, the plan"  ->  "- the plan"

All 7 marker kinds now hold; all 5 deliberate-lower-case cases and the wrapped paragraph are
untouched. `_NOT_A_PROSE_WORD` still applies, so `- untell.score` keeps its spelling, and a line-count
change falls back to the uncorrected text rather than guessing an alignment.

Worth keeping: **this was invisible to every metric the loop has.** No word changed, so similarity,
NLI and the role check all pass; line counts were exact; and a lower-case sentence start is clean to
a tell catalogue. It was found by reading the output — the same discipline that found the sentence
fragments, and the second defect of that exact class this document records.

## Result 170

**Two anti-repetition guards were scoped to a paragraph. Splitting the same six sentences into six
blocks took 0 of 60 documents to 53 of 60 — the tool manufacturing the tell it exists to remove.**

Result 169's output had one more thing in it. Three consecutive lines opened `Also,` `Also,` `Also,`
and two opened `And,` `And,`. The rewriter carries a `spent` set precisely to stop that: the
formal->plain map is many-to-one in places — six source words offer "key", six offer "boost", five
offer "so" — and its own comment records that choosing independently "manufactur[es]
`repeated_phrasing` out of text that had none".

The guard was real and the scope was wrong. `structural_rewrite` runs the pipeline through
`apply_per_block`, and both `spent` sets are local to one call, so every paragraph got a fresh one
and the guard only ever saw the block in front of it.

MEASURED on six sentences drawn from one cluster ('pivotal', 'crucial', 'vital', 'paramount',
'essential', 'salient'), 60 seeds, **layout the only variable**:

    one paragraph (control)   mean max-dup 1.00    0 / 60 documents repeat a replacement
    six paragraphs            mean max-dup 2.37   53 / 60
    six lines                 mean max-dup 2.37   53 / 60
    six bullets               mean max-dup 2.37   53 / 60

Same sentences, same seeds. At seed 4:

    one paragraph    key / critical / essential / top / needed / standout
    six paragraphs   key / key / key / key / needed / key

Words introduced two or more times, across the 60: `key` 87, `critical` 50, `central` 20,
`needed` 12 — all of them replacements the map chose, none of them in the source.

The control arm is what makes this readable. The single-block layout was clean on every seed, so the
difference is layout and nothing else; without it the 53 would be a statement about the corpus.

At component level, four blocks through `_plain_register` over 200 seeds:

    four separate sets   140 / 200 documents repeat a replacement
    one shared set         0 / 200

Both sets are now owned by the document and threaded through `apply_per_block`. Called directly,
each transform still owns its own, so every existing caller is unaffected. After the fix all four
layouts sit at mean max-dup 1.00 and 0 / 60, and seed 4 reads key / central / essential / top /
needed / main — the control's variety, restored.

`_vary_openers` carries the same guard and the same defect, and its denominator is reported rather
than borrowed: 18 sentences in 3 paragraphs over 60 seeds gave 9 documents with two or more openers,
of which **3** reused one ("Put simply", "Actually", "Basically"). It inserts about one opener per
document, so the opportunities to collide are rare — the risk is not small, the denominator is. The
first attempt to assert it failed against correct behaviour: `_vary_openers` deliberately clears
`spent` when its nine-item pool is exhausted, and asking for six openers twice exhausts it.

Worth keeping: **a guard is only as wide as the thing that owns it.** The code knew about the
collision, documented it, measured it, and fixed it — inside one call. Nothing in the repository
stated the scope, and the tell catalogue scores `repeated_phrasing` 0 for both the clean and the
duplicated output, so no gate, no detector and no test could see the difference. Both defects in this
pair were found the same way: by reading the output on input that was not one paragraph.

## Result 171

**The transform that offsets duplicate openers was never called on a one-sentence paragraph — and
the first measurement of what that cost was wrong, because the corpus was three copies of itself.**

Continuing the scope question from Results 169 and 170: where else does a per-block scope disagree
with a per-document property? `_rewrite_prose` guards its sentence stages with `len(sents) >= 2`, and
the comment on that guard already names the transforms that need a PAIR — merge, restatement-drop,
burstiness. Prepending a marker to one sentence is not one of them. `_strip_transitions` had been
moved out of that guard for exactly this reason, and `_vary_openers` was left inside, so the two
halves of one job disagreed.

Instrumented, on three sentences:

    1 block of 3     _vary_openers called 1x
    3 blocks of 1    _vary_openers called 0x

A transcript, a bullet list or a changelog had "Moreover," / "Furthermore," / "Additionally," deleted
from every paragraph, and nothing ever ran to vary what the deletion exposed.

**The first number was an artifact, and catching it is the result.** A synthetic 18-sentence document
gave repeated openers 12 in -> 14.00 out — the tool adding the tell it exists to remove, which read
as a serious finding. That document was three verbatim copies of six sentences. It was repetitive by
construction, and the 14 was a property of the corpus. The same trap this log records at Result 162
and the reason "a number is a property of its corpus" is written down at all.

MEASURED again on 12 real HC3 documents, 5 seeds, the same documents in both arms and layout the only
other variable:

    arm      layout              n    dups in   dups out    delta
    before   as written         60      2.08      2.23      +0.15
    before   one sentence/para  55      2.09      2.18      +0.09
    after    as written         60      2.08      2.15      +0.07
    after    one sentence/para  58      2.09      2.00      -0.09

**The sign flips.** On one-sentence paragraphs the rewriter went from adding duplicate openers to
removing them. The as-written case improves as well, because the fix also gives the transform a
document-scoped `seen` counter: a block of one has no duplicate to find inside itself, so the counts
have to come from the document. It accumulates as blocks are processed, so the earliest paragraphs
are still blind — a duplicate is only a duplicate once it has occurred twice — and that limit is
stated in the code rather than papered over.

The effect is small in absolute terms, about a fifth of a duplicate per document, and the as-written
arm remains slightly positive: the known budgeted cost of this transform, +13 openers created against
28 removed over 60 texts. What changed is the direction on the layout where it was backwards.

Dose is unchanged where it matters. Reaching MORE sentences could have undone the calibration that
exists because output once sat at 36.54% against a human 3.13% — 12x. MEASURED across four layouts:
4.08% to 5.28%, or 1.30x to 1.69x human, with no drift as blocks shrink.

Worth keeping: **the previous fix's own comment contained the argument for this one.** It had already
established that per-sentence transforms do not belong behind a pair guard, listed which transforms
were the exception, and moved one of them out. The other half sat one screen further down and was
never revisited. A fix that states its reasoning makes the next defect findable — and the corpus
check is what kept the write-up honest once it was found.

## Result 172

**The same text, laid out one sentence per paragraph, got 2.7x less out of the loop — and one
document crossed back over the verdict threshold on the strength of the layout alone.**

Results 169–171 each found a per-block scope that should have been per-document, and each was
fixable. This is the case where it is not. Merge, split, restatement-drop and burstiness targeting
need a PAIR of adjacent sentences, and a paragraph of one has none. Merging across a paragraph
boundary would weld two paragraphs together and destroy a transcript, a bullet list or a changelog —
the line structure Result 169 confirmed the tool otherwise preserves exactly. The gating is right.

What was missing is that nobody told the user. MEASURED on 8 HC3 documents at `tier=lite`,
`structural`, `max_iters=2`, seed fixed, layout the only difference:

    as written              0.5501 -> 0.5097   (-0.0404)    flagged 6/8    changed 4/8
    one sentence per para   0.5501 -> 0.5349   (-0.0152)    flagged 7/8    changed 4/8

The `pre` scores are identical to four decimals, because detectors do not read paragraph breaks. The
entire difference is what the rewriter was able to do. One document:

    as written    0.558 -> 0.434    clear
    per line      0.558 -> 0.539    flagged

Same words, same seed, same detectors. Sentence-length variance agrees — document CV against a
measured human 0.484:

    as written        0.304 -> 0.343
    3 sentences/para  0.306 -> 0.374
    1 sentence/para   0.328 -> 0.319      <- moves AWAY from human

The last row is the transform being unavailable rather than unhelpful: with no pair in any block,
burstiness targeting never runs, and what small movement remains comes from other transforms.

**The bar was placed from the corpus rather than chosen.** Over 120 HC3 and RAID texts, both halves,
the share of prose blocks holding exactly one sentence is median 0.000, p90 0.500, p99 0.667, max
0.667. Restricted to the 61 texts with three or more prose blocks the max is the same 0.667 and
**none** exceed 0.80, while six real documents re-laid out one sentence per line score 1.00 across 7
to 10 blocks. The three-block floor keeps the note off short input, where a single lone block is 1.00
by arithmetic and `_short_text_warning` is the note that actually applies.

Worth keeping: **not every scope mismatch is a defect, and the honest response to the ones that are
not is to say so.** The three preceding results moved code. This one moved nothing in the rewriter,
because the alternative — merging sentences across a paragraph boundary — would damage the document
to improve a number. The user gets the measurement instead: the score is real, the rewriter simply
reached less of the text than it would have on the same words in ordinary paragraphs.

A note on the audit: `untell-audit` currently reports one FAIL, `UNTELL_POLICY_WHOLE_DOC`
undocumented. That variable belongs to another session's in-flight `local_policy.py` work, is absent
from HEAD, and is not part of this change.

## Result 173

**The code was consistent. Two documents were not — including the reference document about
thresholds, which still told the reader to drive the loop on `flagged`.**

The question was whether the two bars are compared the same way everywhere: `threshold` (0.30) is
what the rewrite loop optimises toward, `verdict_threshold` (0.45 on the stdlib perplexity path) is
what decides `flagged`. A `>` in one surface and a `>=` in another, or the wrong bar in one place,
would give a document sitting between them two different verdicts depending on which entry point the
caller used.

MEASURED on 10 HC3 documents scoring inside the band, every user-visible surface:

    score_text flagged        False
    untell_text top level     False
    untell_text pre.flagged   False   (verdict_threshold 0.45)
    untell_text post.flagged  False   (verdict_threshold 0.45)

**Refuted.** The code agrees with itself. `run.py`'s in-loop `_score` does compute `flagged` against
the loop threshold, but its dict never reaches the caller — `iterations` and `rewrites` come back as
integers, not score objects — so nothing user-facing is affected.

The drift was in the writing. `flagged` used to mean `max >= threshold`; the CHANGELOG records the
day it stopped, `SKILL.md` warns at length that the two are "two different questions now",
`result-shapes.md` and the OpenAPI field description were both updated. Two surfaces were missed:

    untell/references/thresholds.md:116   "`flagged` — `true` when `max >= threshold` (keep
                                           rewriting)."
    untell/scripts/score.py:12            '"flagged": true   # max >= threshold => still looks AI,
                                           keep rewriting'

Both state the rule `SKILL.md` exists to correct, and both instruct the reader to drive the loop on
it. An agent following either stops rewriting at `max = 0.35` — inside the band where the loop should
continue — or tells a user their text is flagged when the calibrated verdict says it is not. That is
the false accusation `verdict_threshold` was introduced to prevent, and the document specifically
about thresholds was the one recommending it.

The machine check that was missing now exists, and it was verified the only way that means anything:
run against `git show HEAD:` of both files it names **line 116 of thresholds.md and line 12 of
score.py** — the real text that shipped, not an invented example.

Its first version had a false positive worth recording. `SKILL.md` line 190 says "**and note this is
no longer the same as `flagged: false`**" — which IS the correction — but names `verdict_threshold`
eight lines further down, outside the window. Requiring the identifier nearby would have pushed the
documents toward the jargon and away from the explanation, so the check accepts either: naming the
field, or drawing the distinction in words.

Worth keeping: **a semantic change propagates to the places that argue about it and misses the places
that merely state it.** Every surface that DISCUSSED the distinction was updated, because whoever
made the change was thinking about it there. The two that were missed were a one-line field glossary
and a module docstring — the surfaces most likely to be read by someone who has never heard of the
distinction at all.

## Result 174

**Every top-level key is documented. Two fields one level down, inside `post`, appear in no document
in the repository.**

Result 173's lesson stated generally: a change reaches the places that argue about it and misses the
places that merely state it. That is a mechanical question — does every key the code returns appear
in the document that lists them? — so it was asked mechanically, against the "Full key lists" block
of `docs/result-shapes.md` on real payloads:

    score_text        emitted-not-listed  []
    score_tells       emitted-not-listed  []
    score_sentences   emitted-not-listed  []
    untell_text       emitted-not-listed  []

Nothing at the top level. The four entries that are listed-but-not-emitted — `unrankable`,
`warning`, `failed_detectors`, `detector_errors` — are all documented as conditional, so their
absence on ordinary input is the contract working rather than drift.

The gap was one level down. `untell_text` returns `pre` and `post`, and a reader has every reason to
take both for `score_text` payloads:

    extra in pre :  []
    extra in post:  ['flagged_sentences', 'style']

`run.py` merges them in when it settles on the winning draft. `flagged_sentences` is the per-sentence
flag list for the text actually returned — the most useful thing in the payload for deciding what to
edit next — and `style` records which profile ran, without which the rest cannot be interpreted.
Neither appeared in `result-shapes.md`, `SKILL.md` or any reference document. This repository has
shipped exactly this before, with `unrankable`.

The guard was verified against `git show HEAD:` of the real document: it names `flagged_sentences`
and `style` in `post`, and nothing in `pre` or at the top level.

**Three probe errors on the way, and they are the reason this result is worth reading.** Reading the
document for backticked names reported **19 of 28** fields undocumented — the key lists are a fenced
block of comma-separated names carrying no backticks at all. Adding a JSON-key pattern found zero,
because there is no JSON in the file either. Then the parser's prose-filter list contained `final`,
put there to absorb the phrase "for the FINAL text" in the sentence being added — and `final` is the
key holding the rewritten document, so the check reported the payload's single most important field
as undocumented.

Each of those would have been published as a finding by a run that stopped at the first number. The
first would have claimed two thirds of the schema was undocumented; the third would have "fixed" a
field that was never broken. The real answer — two fields, both nested, both genuinely absent — only
appeared after the third correction.

Worth keeping: **a documentation check is a parser, and a parser is a place to be wrong.** The fix
was to stop parsing prose: the fenced block now holds key lists only, and the explanation sits
outside it where no extractor has to guess which words are field names.

## Result 175

**The untuned rewriter clears the two documents nothing else could, and its in-sample score calls
that a failure.**

Result 168 left the base-model path measured and unusable — 4 of 5 documents byte-identical, and the
fifth the best held-out number in this log. Making it work took four fixes, and **the first three
each shipped, were individually justified, and changed nothing observable.** Every one of these
failures prints `sim 1.000, stopped max_iters`.

1. **The prompt.** `_TRAIN_PROMPT` is what the policy was RL-trained on; an untuned model given it
   summarises. Anchored replacement on the base path — and *not enough on its own*: with six explicit
   rules Qwen2.5-1.5B still opened *"In the paper titled ..."*, ran to 108% on one document and
   compressed another to **29%**. Instruction-following at 1.5B does not carry a constraint.
2. **Granularity.** A model that cannot see the document cannot summarise it. Per sentence, entailment
   went **0.037-0.229 → 0.967 / 0.989 / 0.973 / 0.960 / 0.287**.
3. **Sentinels.** The loop rewrites LOCKED text. Doc 0 carries 12 locked spans across **all 9** of its
   sentences, so nearly every unit handed to the model contained a `⟦HZ⟧` token it paraphrases away;
   every sentence failed integrity and the rewriter returned its input. Shielded as `[REF0]` and
   restored after.
4. **The budget.** The per-sentence band and the document's deletion allowance were different
   constraints, and satisfying only the first *guarantees* rejection: a 310-word document may lose 31
   words, and a 0.6 sentence floor sheds about 112. One running budget now. The band then **loosened**
   to 0.7 — traced over 9 sentences it was rejecting three at ratios 0.74-0.77 scoring entailment
   0.935 and 0.951, faithful compressions thrown away by a band standing in for a budget that did not
   yet exist.

RAID n=5, `best_of=2`, `max_iters=2`, held-out RADAR scored on frozen output:

```
doc | tier max pre -> post | RADAR pre -> post | sim     | composite's RADAR, 3 seeds
  0 |   0.9998 -> 0.9746   |  0.9514 -> 0.2564 | 0.969   | 0.973 / 0.940 / 0.980
  1 |   0.9983 -> 0.9983   |  0.8323 -> 0.8323 | 1.000   | 0.243 / 0.291 / 0.094
  2 |   0.7555 -> 0.7555   |  0.7835 -> 0.7835 | 1.000   | 0.163 / 0.123 / 0.319
  3 |   0.9591 -> 0.1925   |  0.9991 -> 0.0994 | 0.977   | 0.999 / 0.288 / 0.457
  4 |   0.9998 -> 0.3651   |  0.4467 -> 0.0269 | 0.953   | 0.096 / 0.996 / 0.102
```

**Doc 0 is the finding.** Result 163 named it one of the two documents composite never clears — 0.940,
0.973, 0.980 on the holdout across three seeds — and here it reads **0.2564**. Doc 3, stuck at
0.999 / 0.288 / 0.457, reads **0.0994**.

**And doc 0 restates Result 163 in a single row: in sample 0.9746, held out 0.2564.** Judged by the
objective the loop optimises, the rewrite that finally cracked an immovable document is its worst
result of the five. Nothing in the shipped pipeline can see that.

The two arms are **complementary, not ranked**. Where this one no-ops (docs 1, 2) composite reaches
0.09-0.32; where composite is stuck (0.9, 3) this reaches 0.10-0.26. That is an argument for the
per-input `ensemble` selector rather than for replacing a default — and the selector cannot currently
make that choice, because it would rank these candidates on the in-sample score that calls doc 0 a
failure.

`_strip_preamble` was narrowed because its own known-negative caught it deleting a real first
sentence: *"The committee reached the following conclusions after reviewing every dataset at
length:"* is twelve words and ends in a colon.

Scope: n=5, one seed, 2 of 5 still no-ops, one holdout, and roughly 700s per document on CPU. The
in-sample mean is **worse** than composite's (0.6572 against ~0.43). Nothing here says this should be
the default.

Worth keeping: **three correct fixes in a row can each change nothing, and the aggregate cannot tell
you which one you are still missing.** The prompt, the granularity and the sentinels were all real
defects with real evidence; the thing actually holding the output back was arithmetic between two
guards that never referred to each other. Tracing one document's nine sentences answered in one run
what three re-runs could not.

## Result 176

**The per-sentence flags handed to the caller described neither the output nor, usually, anything at
all — the loop computed five and the caller received none.**

Result 174 found `flagged_sentences` documented nowhere. The obvious follow-up is whether the field
is *correct*: does `post.flagged_sentences` describe `final`? Two independent defects, and the second
is the one that matters.

**It named sentences that are not in the output.** The list is computed on MASKED text — the form the
rewriter works in — so any sentence containing a locked span came back carrying a sentinel:

    'Overall, the controversy surrounding unions in ⟦HZ0001⟧ is complex and multifaceted, ...'

MEASURED on the 7 HC3 documents (of 60) whose per-sentence pass flags anything, each run plain and
with a citation and URL welded in — 12 runs, 6 with a non-empty list: **4 sentences carried a
sentinel and 4 were absent from `final`**. It fires on plain input too, because `lock` masks
entities, numbers and dates rather than only citations, so this is the ordinary case.

**And usually it was not there at all.** `best_score` is replaced wholesale when a candidate is
adopted, when the result is rescored, and when it is polished, while the key is set at the TOP of
each iteration. It therefore survived only when none of those three happened afterwards. Instrumented
with the per-sentence pass forced to flag every sentence:

    patched scorer calls: 2, returning 5 flagged sentences each
    post flagged_sentences: 0

The loop computed the list twice and the caller received an empty one. When it did arrive populated,
it described the text as it stood at the start of some earlier iteration — never `final`.

The fix scores `final` rather than translating what the loop carried out. The loop keeps its masked
list, which is right for `rewriter/prompts.py` and the targeted rewriter: they are editing masked text
and showing them a restored citation invites the model to rewrite the one span that must survive
byte-for-byte. MEASURED after, same documents:

    forced arm   n=4   sentinels 0   absent from final 0     (was: caller got 0 of 5 computed)
    real arm     6 runs, 5 non-empty, sentinels 0, absent 0  (was: 6 non-empty, 4 and 4)

One extra lite per-sentence pass per call; a full run measures 0.56s.

**Three false starts, recorded because each looked like an answer.** The first probe ran four short
documents and got four empty lists — no denominator, nothing proved. The second ran sixteen corpus
documents and got sixteen empty lists, which looked like a strong negative result and was simply the
base rate: at `tier=lite` only 7 of 60 documents flag any sentence, because that path is AUROC 0.493
and says so in its own caveat. The third suspected a type mismatch — `s in scored` comparing strings
against indices — and the elements turned out to be strings. The defect only appeared once the list
was forced to be non-empty.

The end-to-end assertion inherited that lesson: it patches the per-sentence pass instead of hoping a
fixed document trips it, because the document it was written against flags zero sentences and the
first version of the test passed over an empty list.

**A note on where this landed.** The code hunk was swept into commit `47599c3`, whose subject is
about the language gate: a concurrent session staged `run.py` while this change was in the working
tree. Nothing was lost and the fix is on main, but the commit that carries it does not describe it.
Recorded here rather than repaired by rewriting shared history.

Worth keeping: **a field can be wrong in a way that no schema check sees.** Result 174 established
that `flagged_sentences` existed and was undocumented; documenting it would have been the whole job
by any structural measure. The value in it was still wrong — stale by construction, and unreadable
when it was not stale.

## Result 177

**Four of five reported numbers describe exactly what the caller received. The fifth was
systematically flattering, and only on the documents that most needed it to be honest.**

Result 176's lesson was that a field can be wrong in a way no schema check sees. Applied to the rest
of the payload: MEASURED on 8 HC3 documents, 4 of which the loop changed, each figure against a fresh
computation on the text it claims to describe:

    post.max      vs score_text(final)["max"]     0/8 disagree
    tells_after   vs score_tells(final)["tells"]  0/8 disagree
    pre.max       vs score_text(input)["max"]     0/8 disagree
    tells_before  vs score_tells(input)["tells"]  0/8 disagree

`similarity` was the exception. Whenever polish had not run — the ordinary path — it compared
`masked` against `best_masked`, masked text on both sides. The code gave its reason: `best_masked`
restores to `final`, so the comparison is exact. **That is true of the text and false of the number.**
A sentinel is a single token standing in for a multi-word span, so both sides get a free exact match
in precisely the places where the real words would have had to be compared.

MEASURED, reported value minus a fresh `similarity(input, final)`, over documents the loop changed:

    plain             6 changed   mean +0.0013   worst +0.0040   reported higher 3/6
    citation-dense    7 changed   mean +0.0040   worst +0.0155   reported higher 5/7

Two things make this worth fixing rather than noting. It is **one-directional** — the reported figure
was never below the real one — so it is a bias, not noise. And it **grows with how much of the
document is locked**, which means the meaning number is least trustworthy on citation-heavy academic
text: exactly the population the preserve layer exists to serve.

After the change both arms report the caller's own figure exactly — mean and worst gap 0.000000, on
the same 6 and 7 documents. `polished_applied` went with it; the branch this replaces was its only
reader.

The gate's own masked comparison is a separate decision, measured earlier and deliberately kept
(mean −0.0014, and the single disagreement ran safe). The distinction matters: a gate may be
conservative on purpose, but a reported number has one job, which is to be the number.

Worth keeping: **the justification was correct and the conclusion did not follow.** "`best_masked`
restores to `final`, so the similarity is exact" is a true sentence about text identity sitting on
top of a false claim about a token-level metric. A comment that states its reasoning made this
findable — the same property that made Result 171 findable — because the reasoning could be checked
independently of the code.

## Result 178

**One report, two bars, and only the summary row said which one answered.**

Result 173 asked whether the loop threshold and the verdict threshold are used consistently, and
found the code agreed with itself across `score_text`, `untell_text`, `pre` and `post`. It did not
cover `verify` — the command that exits non-zero, and the one that disagreed with itself.

The history is already in the file. An earlier fix moved `verify`'s LOCAL rows off the loop threshold
and onto the published `verdict_threshold`, recording the measurement that justified it:

    raw max >= 0.30          21/40  (52%)
    score_text "flagged"      7/40  (18%)   <- calibrated
    verify "not passing"     21/40  (52%)   <- this surface, uncalibrated

Two things survived that fix. Commercial and browser rows still judge at the loop threshold, so a
report containing both kinds applies 0.45 to some rows and 0.30 to others. And the per-detector local
rows moved onto the calibrated cut **without** gaining the field that says so, leaving the summary
row as the only one in the report that explained its own bar.

**The unification that looks obvious is wrong.** `verdict_threshold` is swept for the local stdlib
ensemble and published by `score_text` for it. A commercial detector returns its own probability on
its own scale, and applying a calibration derived from a different scorer to it would be a guess
wearing a measurement's clothes. So the two kinds keep their own bars, and every row states which one
judged it — which is precisely the reason the `local:max` row already carried the field, in a comment
that reads "a pass at 0.38 is not read as a pass at 0.30".

MEASURED after, over 6 in-band HC3 documents, 12 rows: **0** scored rows with no stated cut, **0**
rows whose `passes` disagrees with its own stated cut, and an explicit `--threshold` still reported
verbatim rather than silently replaced.

**The first pass at this question saw nothing, and the reason is the denominator.** Running `verify`
on in-band documents produced only `local:` rows — the half that was already fixed — because
commercial and browser checkers are unavailable in this configuration. The disagreement is
unreachable without one, so the battery injects a stub detector rather than reporting a clean sweep
over the rows that were never at risk.

Worth keeping: **a partial fix leaves the surface looking consistent from wherever the fixer stood.**
The earlier change was correct, measured, and stopped at the rows its author could see running. What
remained was invisible in the default configuration and would have shipped a contradictory report to
exactly the users who pay for a commercial checker.

## Result 179

**No defect, and the trace is the result: an adapter missing one attribute would break `score_text`,
not the command that reads it.**

Result 178 ended on the observation that paths unreachable in the default configuration are the ones
that ship broken. The stub commercial detector written for it raised

    AttributeError: '_StubDetector' object has no attribute 'tier'

which is the kind of thing that gets patched around in ten seconds. Tracing it instead:

    verify.py:66   ->   score.py:314 (score_text)   ->   base.py:300 (load_detectors)

`verify` never reads `tier`. `commercial_detectors()` feeds the ordinary detector registry, so an
adapter missing that attribute breaks **`score_text`** — the main scoring entry point, used by every
surface — and only for users who have configured an API key. Everyone else would see a clean test
suite.

MEASURED, all six adapters against the protocol `load_detectors` requires:

    OriginalityDetector  WinstonDetector  GPTZeroDetector
    SaplingDetector      ZeroGPTDetector  CopyleaksDetector       6/6 conform, tier='commercial'

**No defect.** The interface is satisfied today and was held in place by nothing but habit. The guard
now also pins that a declared tier is one the registry actually filters on, because a typo there does
not raise — it removes the detector from every tier silently, which is the worse failure.

**One probe error, and it is the same shape as the one in Result 174.** The first sweep measured the
browser checkers against the detector protocol and reported three missing attributes each. They are a
different interface: `verify` drives them with `available()` and `check()` and keys the row by the
site string it was handed, never reading `name`, `tier` or `score`. A conformance check is only as
good as its knowledge of which contract applies, and a confident list of missing members is exactly
what a wrong contract produces.

Worth keeping: **a stub that fails to satisfy an interface is evidence about the interface.** The
fast move was to add `tier` to the stub and carry on — the test would have gone green and the fact
that the main scoring path depends on an attribute no visible caller reads would have stayed
unwritten.

## Result 180

**Three user-supplied names, probed for how they fail. Two are loud. The third silently bought a
neutral rewrite and reported nothing — including when it worked.**

Result 179 ended on a tier typo that would remove a detector without a word. The general question is
which user-supplied names fail loudly:

    tier      'lyte'      -> warns "unknown tier 'lyte' — no tier matched"        loud
    rewriter  'structual' -> returns {"error": ..., "final": text}                loud
    style     'acadmic'   -> silently neutral, nothing said                       SILENT

MEASURED at seed 5 on the same text, `style="academic"` produced different output from `style=None`
— the academic profile keeps the transitions the neutral one strips — so the parameter works. And
`post["style"]` came back `None` for `academic`, for `casual`, and for `None` alike.

Two defects in one place.

**The report never named the style.** `best_score` is replaced wholesale when a candidate is adopted,
rescored or polished, and `style` is set at the TOP of an iteration: the identical construction that
lost `flagged_sentences` in Result 176. That fix recomputed one field and left its neighbour sitting
in the same expression. Recorded rather than quietly tidied, because the interesting part is that a
correct fix to a named field did not prompt anyone — including me — to look at the field beside it.

**An unrecognised style was silently ignored.** `style_profile` maps an unknown name to the neutral
default by design, which is reasonable for a lookup and wrong for a report. `api_server.py` already
records this exact failure for REST and fixed it there by constraining the field to `STYLE_NAMES`: an
unrecognised name "received a rewrite with no style applied and nothing saying so". The CLI has
`choices=STYLE_NAMES`. **The library entry point — the one the MCP server and every embedding caller
use — had neither guard.** The same shape as Result 178: a fix applied where the fixer stood.

A warning rather than an exception, because the fallback is documented behaviour and a caller may be
passing a name from a newer version. The message carries the valid names, since the whole failure is
that the caller believed they had used one. Reporting agrees with the lookup on case and padding, so
` ACADEMIC ` runs the academic profile and is reported as `academic` rather than as unrecognised.

**One probe error.** The rewriter typo appeared to raise `KeyError: 'post'`, which read as a raw
crash on a user mistake. It is not: `untell_text` returns `{"error": ..., "final": text}` for an
unavailable rewriter, deliberately and with a comment saying why. The KeyError was my probe indexing
`r['post']` on an error result. The honest table above has two loud cases, not one.

Worth keeping: **the surfaces that guard a value are the ones whose author had to type it.** The CLI
takes `choices=STYLE_NAMES` because argparse makes that easy; REST took it after a measured failure.
The library path is the one nobody types by hand, and it was the one that let a typo through to a
rewrite that silently did something else.

## Result 181

**A threshold of 45 passes everything on every surface, including the one that exits 0 in CI.**

Result 180 ended on the observation that the library path is the one nobody types by hand. Sweeping
it for values the CLI and REST would reject: `max_iters=0` returns the input untouched, `best_of=0`
still draws a candidate, and both are defensible. The threshold is not.

Detector scores are probabilities — every checker in the registry clamps to [0, 1] — so a threshold
outside that range is not a strict setting, it is an unreachable one. MEASURED on the same AI
paragraph:

    threshold   score.flagged   untell.flagged   verify.passes_all
        0.30          True             True            False
        0.45          True             True            False
        1.50          False            False           True
       45.00          False            False           True
       -1.00          True             True            False

A caller who types `45` meaning 45 per cent gets a clean verdict from every surface, and `verify`
exits 0. **Nothing said a word.** The only warning present was the generic lite caveat — byte-
identical at 0.30 and at 45.00 — and it quotes "the 0.30 loop threshold", a number the caller did not
use. So the surface was not merely silent about the mistake, it was confidently describing a
different setting.

This is the false-negative direction, and the one the rest of this document spends less time on. The
`verdict_threshold` work exists to stop the tool calling human writing AI; this is the tool calling
AI writing clean, in CI, with a green exit code.

`verify` needed its own wiring: it already had a `caveats` list and emitted `warning` conditionally —
undocumented in `result-shapes.md`, the same class as Result 174 — and the note now joins it there.
Both endpoints stay silent, because a score can equal 0.0 or 1.0: those are extreme settings rather
than impossible ones.

**A probe error, and the second of this kind in three loops.** The first pass tested "does any
warning mention the threshold" with a keyword match, got `True` for every value including 45.0, and
would have reported the caveat as already present. The match was on the generic prose. Reading the
warning text rather than searching it is what turned a clean bill into a finding — the same
correction Result 179 required after measuring browser checkers against the wrong protocol.

Worth keeping: **a warning that names a number the caller did not pass is worse than no warning.** It
reads as confirmation. Whatever else this fix does, it stops the tool from quoting `0.30` back at
someone who asked for `45`.

## Result 182

**Every run carries a warning, so the note that mattered was arriving 500 characters in.**

The caveats added across this session needed checking for interference: does one mask another? They
compose — up to three fire together on one document and none is dropped. The useful measurement was
the one taken alongside it, over 120 corpus texts (HC3 and RAID, both halves) at `tier=lite`:

    texts with an EMPTY warning        0 / 120
    warning length                     median 503, p90 882, max 882
    tier caveat                      120 / 120
    human-false-positive note         46 / 120
    every other caveat                 0 / 120

Two things in that table. The four caveats added this session fire on **none** of the corpus, which
is exactly what their bars were calibrated for — the noise budget was spent honestly. And the tier
caveat fires on **every single run**, which makes it wallpaper.

It was also first. A reader who stops after the first sentence — which is what people do with a note
they have seen a hundred times — never reached the one specific to their input. The worst case was
Result 181's threshold caveat: it says the caller's setting passes everything, and it was arriving
behind "Also:", five hundred characters in, underneath a paragraph the reader had already learned to
skip.

**The first attempt fixed nothing and would have shipped a comment saying it had.** Reordering the
merge tuple changed no output at all, because the tier notes were assigned straight to
`result["warning"]` in an if/elif chain BEFORE the loop ran — so they held first place whatever the
tuple said. The reorder was written, the comment explaining it was written, and only re-running the
measurement showed the leading text had not moved a character. That chain is now a value that takes
its turn in the order like every other note.

Ordering is the whole change. Nothing is dropped, shortened or conditioned, and all three branches of
the tier chain stay reachable.

Worth keeping: **a caveat's position is part of its content.** This document has spent a lot of
effort on whether each note is true, correctly bounded, and reachable — and none, until now, on
whether anyone gets to it. A true warning nobody reads scores the same as a missing one, and the
measurement that revealed it was not about correctness at all: it was counting how often the tool
says something.

## Result 183

**The cost of my own fix, measured three times, wrong twice — and the two wrong answers were both
first-call warm-up.**

Result 176 added a per-call lite per-sentence pass so `flagged_sentences` describes the text the
caller received. This repository has reverted two scoring changes on cost grounds, so shipping a new
scoring pass without measuring it was an open debt.

**First measurement: +25.1% median, and a 4x difference in totals.** Six documents, the instrumented
arm first, the patched-out arm second.

**Second measurement, per document:** doc 0 at **23.5x** — 19.25 s against 0.82 s — with the rest
between 1.55x and 2.79x. A 23x regression on a reporting field would be a straightforward revert.

Both were artifacts. The first document measured in a fresh process pays detector warm-up, and in
both runs that document sat in the arm being blamed. With warm-up performed before any timing and
the two arms alternated document by document:

    doc  sents     with  without      x
      0      7    1.055    0.919   1.15
      1      8    1.093    1.484   0.74
      2      7    1.830    0.723   2.53
      3      7    0.811    1.197   0.68
      4      9    1.735    1.010   1.72
      5     10    1.201    1.583   0.76

    median 0.95x

Ratios scatter in **both** directions — three of six below 1.0 — which is what noise larger than the
effect looks like. End to end, the change is not separable from run-to-run variance.

The component measurement is the one that means anything, and it is low-variance:

    per-sentence pass              0.076 - 0.120 s
    one whole-document score_text  0.038 - 0.056 s
    ratio                          2.30x  (median, 8 documents, 3 runs each)

About 9% of a ~1.1 s run. That reconciles the two: 9% sits well under the ±30% scatter above, which
is exactly why the end-to-end arm could not see it, and why the end-to-end arm was never the right
instrument.

No behaviour change. Making the field opt-in would break a documented always-present key and hand
Result 176's defect back to anyone who did not opt in.

Worth keeping: **timing a whole pipeline to measure one component inside it is a losing instrument.**
The end-to-end arm produced a 25% regression, a 23x regression, and a 5% improvement from the same
code on the same corpus, depending on ordering. The component took a tenth of the effort and gave a
number that held still.

## Result 184

**A correct claim, correctly scoped, that does not apply to the path a clean install runs.**

Result 183 established that pipeline timing is a losing instrument. The obvious follow-up is whether
any wall-clock claim already in the tree was measured that way. `prefer_tells=True` "costs 2.3x less
wall-clock" is the most re-measurable of them, and `api_server.py` already records the warm-up
phenomenon elsewhere (9.34s then 0.0026s — 3,636x), so the repository knows the effect in one place
and not others.

MEASURED on the stdlib lite path, warm-up controlled, median of 3 runs over 4 HC3 documents:

    the ranking pass alone   importance() / _tell_ranks()   8.2x   (5.8x - 9.0x)
    the whole call           prefer_tells True vs False     0.92x, 0.95x

**The claim is right and the code says so** — "the 2.3x speed-up at full tier". The mechanism is real
and large: skipping the leave-one-out ranking is an order of magnitude cheaper. What no reader could
work out is that the tells objective hands the saving straight back downstream, evaluating more
candidates and recounting tells per adoption, so **on the default path the two modes cost the same**.
`prefer_tells=True` earns its place on the tells it removes — 0.571 -> 0.233 against 0.571 -> 0.458 —
not on speed a lite user will never see.

**Two probe errors, both watching the wrong function, both on the same question.** Counting
`score_text` calls gave 1 versus 1, which read as "the expensive pass does not exist". Counting
`batch_score_texts` gave 3 versus 4 texts, which read the same way. The leave-one-out pass lives in
`importance()` and routes through neither. Timing the two ranking functions directly — the component,
not the pipeline — is what produced a number that held still, which is Result 183's lesson arriving
one loop later than it should have.

Worth keeping: **a scoped claim is only as useful as the reader's ability to tell whether they are in
scope.** "2.3x less wall-clock at full tier" is a true sentence. The person most likely to read it is
running the zero-dependency install, where the figure is 1.0x, and nothing in the sentence told them
which side of it they were on.

## Result 185

**"Furthermore" went in and "but" came out. 36% of merges asserted a relation the source
contradicted, and no gate in the system can see it.**

Found by running the documented quickstart through the CLI and reading the output — the first loop in
a while to use the product the way a user does rather than the API. It returned:

    "Furthermore, it is important to note that this underscores the pivotal integration"
      ->  "..., but this highlights the critical integration"

`Furthermore` says the second sentence ADDS to the first. `but` says it opposes it.

`_MERGE_CONNECTORS` is `(", and ", ", but ", ", so ", ", while ", ", though ")`, chosen by weighted
random. Three assert CONTRAST, one asserts CONSEQUENCE, and only `and` is relation-neutral. The same
file's `_vary_openers` screens "so", "then", "meanwhile" and "recently" out of its pool on precisely
this ground — each "asserts something about the sentence it is prepended to and the meaning gates do
not check discourse relations" — while the merger inserted those relations at random between two
sentences.

MEASURED over 1000 merges of pairs whose second sentence opens with an explicit additive marker:

    , and 645    , but 224    , so 84    , while 40    , though 7

**355 of 1000 — 36%.** And it is invisible to every gate: no fact changed, so the numeral and role
checks pass; the words are nearly all the same, so similarity is high; and NLI reads two clauses that
both still hold, because each half is true — it is the *relation between them* that was invented.

**The fix needed two mechanisms, and the first left an exact residual.** `_strip_transitions` deletes
the marker before `_merge_sentences` ever runs, so the relation must be captured at strip time. That
took the stripped markers to 0/120 and left "In addition", "Also" and "Besides" at 37/120 each,
because `_TRANSITIONS_RE` does not strip those. Widening the stripper would have been the obvious
move and is wrong: "Also," is an opener `_vary_openers` deliberately ADDS, on measured human
frequency. Reading a surviving marker in place closes the gap:

    after both mechanisms     0 / 720 wrong-relation, across seven markers

Where the source states no relation there is nothing to honour, and the measured connector
distribution stands — `, and ` 135, `, but ` 42, `, so ` 18 over 200 seeds. Coverage is partial by
construction: transforms between the strip and the merge can rewrite a sentence enough that its key
stops matching, and a missed sentence falls back to where it was.

Worth keeping: **the argument for this fix was already written in the same file, for a different
transform.** `_vary_openers` had the reasoning, the vocabulary, and the measured decision to exclude
relation-asserting words. Nothing carried it thirty lines down to the transform that joins two
sentences with "but". A principle recorded next to one transform is not a principle the file
follows — and the way it surfaced was reading four lines of ordinary output.

## Result 186

**The mirror of Result 185 does not exist, and it took four wrong probes to establish that.**

If merging can invent a discourse relation, splitting can delete one: break "A, but B" into "A. B."
and the contrast is gone, invisibly, for the same reason — each half stays true on its own. That is a
one-line hypothesis and it is wrong.

The probes, in order, and what each actually measured:

1. Five connective sentences through `_split_long_sentences` at `rate=1.0`: "never split". They were
   22-25 words against a `max_words=28` gate. **Zero denominator.**
2. Rebuilt at 30-39 words: "never split" again. Still nothing, and by now the natural reading was
   that the splitter refuses connectives.
3. A control with a comma and no conjunction, to check the splitter splits anything at all: also
   nothing. That should have been the moment the instrument came under suspicion.
4. Reading the function end to end instead: when a split would strand a fragment, it does not
   decline — it **rejoins the halves with a comma** and emits ONE sentence:

       out.append(_terminated(f"{first}, {second}"))

My detection was `len(out) > 1`. Every case where the transform ran, considered the split, judged it
unsafe and preserved the sentence was recorded by that test as "never split" — the transform working
exactly as designed, counted as the transform never running.

**No defect.** The connective survives because the split is declined, and the guard that declines it
carries its own provenance:

    "FOUND by reading actual rewriter output on RAID and HC3 rather than by any metric,
     because a fragment is perfect English to a tell catalogue"

Which is the same method that produced Result 185 one loop earlier, applied to this transform by
whoever wrote it — and the reason there was nothing here to find.

Worth keeping: **"the transform did not fire" and "the transform fired and chose not to act" are
different facts, and a boolean on the output length cannot tell them apart.** Three probes in a row
returned the same clean-looking zero, and the zero meant something different each time. The cost of
the confusion was four measurements; the cost of publishing it would have been a fix to a guard that
was already correct.

## Result 187

**All eight structural transforms are covered — a fact nobody could state without running the sweep,
and which the first sweep got wrong.**

Result 186 ended on a test that could not tell "the transform did not fire" from "the transform fired
and declined". The same question turned on the suite: how many tests would still pass if a transform
were replaced by identity? This repository has shipped that defect — a saturating detector made
`cand < best` unreachable and the DEFAULT rewriter went out as a no-op on 10 of 10 HC3 documents.

MEASURED by stubbing each transform to identity. First sweep, over six test files:

    _merge_sentences        7 failed      _strip_transitions   1 failed
    _vary_openers           3 failed      _flatten_cliches     2 failed
    _plain_register         2 failed
    _split_long_sentences   79 passed     <- survives
    _target_burstiness      79 passed     <- survives
    _flatten_copula         79 passed     <- survives

Three transforms apparently untested, including burstiness targeting — which the code calls "the
single most reliable stylometric differentiator". A real finding, if the six files had been the
coverage. They were not. Against the wider structural suites:

    _split_long_sentences   5 failed      _target_burstiness   4 failed
    _flatten_copula         3 failed

**No gap.** The coverage is spread across 27 files and 670 tests, which is why the narrow sweep found
nothing and why the property was worth making local.

**The new guard's own fixture was wrong twice, in the same shape.** At 15-20 words a sentence with
nothing restated, it reported `_split_long_sentences` and `_drop_restatements` dead — both had
nothing to act on, the splitter needing a sentence over its 28-word gate. Adding one fixed the
splitter and left burstiness, restatement-drop and the copula flattener still reporting no effect,
because each is conditional on input this fixture does not supply. So the file asserts what a fixture
can settle — six transforms shown CHANGING the output, three shown REACHED — rather than a claim it
cannot support.

Worth keeping: **"is this tested?" is a question about the test selection at least as much as about
the code.** The same eight transforms, the same stubs, the same machine: three dead with one file
list, zero dead with another. The number that mattered was not in either sweep — it was the count of
files each one ran.

## Result 188

**Nothing is excluded, and the suite already encodes the discipline the last fifteen results have
been applying by hand.**

Result 187 ended on "is this tested?" being a question about test selection. The sharpest version is
whether the project's own invocation runs everything. It does:

    CI job 1 (lite)   pip install -e ".[dev,mcp]"                            pytest -q
    CI job 2 (full)   torch CPU + .[full,eval,quality,docs,rich,dev] + spaCy pytest -q

No `--ignore`, no `-k`, no deselection, no marker filter. So a test that never runs would have to
skip itself.

**69 of 282 test files contain a skip** — a quarter of the suite. The conditions cluster on NLI,
torch, spaCy, BERTScore, HC3 pairs and git checkout, and every one of those is satisfied by CI job 2,
which installs the eval and quality extras and downloads the spaCy model. The candidate class that
would clear in NEITHER job — commercial detectors gated on an API key — turned out not to exist here:
the `not available()` gates are spaCy and NLI, not paid services.

MEASURED over 14 skip-bearing files: **501 passed, 7 skipped**. Three of the seven are the finding:

    t5_paraphrase left the text unchanged on every draw; nothing to compare
    mt_pivot left the text unchanged on every draw; nothing to compare
    local_policy reports itself unavailable; a no-op looks deterministic

Those skips fire **because the denominator is zero**. They are the same reasoning this document has
spent fifteen results applying by hand — a comparison against an unchanged text proves nothing, so
decline to make the claim — already written into the suite as a runtime condition rather than a note.

The two rewriter skips were worth chasing, because "left the text unchanged on every draw" is exactly
how the no-op default rewriter presented. Called directly with a score result, all three change the
text:

    T5ParaphraseRewriter   available=True  changed=True
    MTPivotRewriter        available=True  changed=True
    StructuralRewriter     available=True  changed=True

**No defect.** The skips describe those tests' own draws, not an inert rewriter.

**Four probe errors in one loop**, all from guessing an API rather than reading it: a lookup function
that does not exist, a package listing to find it, then `rewrite()` called without the score argument
— which made all three rewriters, including the one I had just watched work, look broken with a
`TypeError`. The fourth attempt was the first to call the real signature.

Worth keeping: **a null result on a whole line of questioning is worth the loop when the line was
plausible.** Every step here could have found something — a deselected file, a skip that never
clears, an inert rewriter — and the reason none did is that someone had already thought about it. The
suite declining to compare against unchanged text is the strongest evidence in this document that the
discipline is in the code and not only in the log.

## Result 189

**Double quotes are safe, curly quotes are safe, single quotes were rewritten — and main was red on
a different rule while I looked.**

Reading real output on an input type not yet tried: does the rewriter alter words inside quotation
marks? That is not a style question. Changing what a source is reported as having said is a factual
error, and the preserve layer exists precisely to stop it.

MEASURED through the shipped loop, same sentence in three punctuations, 3 seeds each:

    "double quotes"   2 of 2 quotations preserved
    “curly quotes”    2 of 2 preserved
    'single quotes'   0 of 2 preserved      <- 'we utilize a seamless methodology' came back rewritten

British and academic house styles quote this way as a matter of course, so this is not an exotic
input. The reason it was left out is the apostrophe: a naive `'...'` locks from "team's" to "didn't"
and swallows the prose in between. Four guards make it safe — opening quote at a word boundary,
closing quote followed by space or punctuation, no whitespace before the close, six characters
minimum — and the hazard was measured rather than assumed:

    80 HC3 texts, both halves       0 spurious matches
    apostrophe-dense probe          0 matches   ("team's ... didn't ... Jones' ... councils' ...")
    genuine single quotation        matches

Corpus locked share is unmoved — median 0.020, p90 0.063, max 0.177 — so the 0.80 bar in
`_mostly_locked_warning` still sits in the same empty gap it was measured into. Curly single quotes
are deliberately excluded: U+2019 is the typographic apostrophe, so `‘...’` cannot be told from
"don’t" by shape.

**The first arm of this measurement was wrong in the usual way.** Calling `structural_rewrite`
directly reported double and curly quotes being altered too — 3 of 4 documents damaged. `preserve.lock`
runs in the loop, not inside the rewriter, so that arm was measuring an unmasked path no user takes.
The real answer is the narrower one, and it only appeared through `untell_text`.

**And a red main, found sideways.** Running the preserve suite for regression surfaced a failure that
had nothing to do with this change: `tests/test_preserve.py` enforces "import `SENTINEL_RE` from
`untell.scripts.preserve` instead of re-declaring it", and `tells.py` declared its own copy, on main,
committed. Its justification was written into the code — "`preserve` imports from this module, and
the pattern is four characters of regex" — and the first half is false: `preserve` imports from
`untell.scripts.latex` and from nothing else in this package.

Worth keeping: **a duplicated constant that explains why it is duplicated is still a duplicated
constant, and the explanation is the part most likely to be wrong.** Nobody re-checks a reason once
it is written down. The rule had a test, the test was failing, and the comment was the reason it had
survived long enough to fail.

## Result 190

**"The ONLY place the list is written down" — and the vocabulary is in two files.**

Result 189 found a comment whose factual claim about the codebase was false, and which had kept a
failing test alive because nobody re-checks a reason once it is written. That is a searchable class:
comments asserting "the only caller", "nothing else uses this", "imports from this module". Sweeping
them turned up `prompts.py` on `STYLE_NAMES`:

    # The voices `--style` accepts, and the ONLY place the list is written down.

`"storytelling"` appears in exactly two files. `structural._STYLE_PROFILES` is keyed by the same
fourteen names and is an independent literal.

MEASURED: both sets are 14 and identical, and `run.py` builds its argparse choices from `STYLE_NAMES`
rather than restating them. **No live drift** — the claim is wrong about the code, not about the
state.

What made it worth a loop is that only one direction was guarded, and the two directions fail
differently:

    a name with no profile   accepted by every surface, silently rewrites with the neutral one
    a profile with no name   a style nobody can select

The first is exactly the defect Result 180 was opened for. And the vocabulary has drifted here
before: the comment's own history records the MCP docstring carrying **six of the fourteen**, so
eight styles were invisible to every MCP caller. The consolidation that followed removed the argparse
and MCP copies and left the profile table, which is the copy nobody thinks of as a copy — it is a
settings dict, and its keys happen to be the vocabulary.

Worth keeping: **a comment claiming uniqueness is a claim about every other file, which is the
hardest kind to keep true and the easiest kind to check.** "This is the only place X is written" was
true of the two copies its author had just deleted and false of the one they had not looked at. The
sweep that finds these costs one grep.

## Result 191

**Half the uniqueness claims were false, and the mechanical version of the question found the copy
that matters.**

Results 189 and 190 each found a comment asserting a fact about the codebase that was wrong. Finishing
that sweep, the remaining checkable claims came out TRUE:

    hedges.py:159   "Neither sentence locks anything in preserve.py"
                    -> 0 locked spans on all four sentences quoted there
    word_importance "floor ... Only used by the prefer_tells path"
                    -> its read and its update both sit inside that branch

So the class runs about half. Worth sweeping, not worth assuming — in either direction.

Both false ones were about a **duplicated definition**, which has a mechanical form: which constants
are declared with an identical literal in more than one module? Over the package, five:

    _FREE_REWRITERS   api_server.py, mcp_server.py     nine rewriter names
    _LATIN            languages.py, score.py           re.compile('[A-Za-z]')
    _NUM              llm_judge.py, local_judge.py     digits
    _WORD             tells.py, voice.py               word regex
    _WORD_RE          humanness.py, structural.py      word regex

Four are two-character regexes whose drift would be obvious. The fifth is a **vocabulary**,
duplicated across the two surfaces a caller reaches without ever touching the CLI. MEASURED:
byte-identical today, nine names each. No defect — and the failure it guards against is one this
repository has already shipped, when the MCP docstring carried six of the fourteen style names and
eight styles were invisible to every MCP caller.

It is deliberately not consolidated into a shared import. CI installs the MCP path as `.[dev,mcp]`
with no FastAPI, so reaching into the REST module for its constant would put a web framework on the
MCP server's import path to save nine strings. The test reads both constants out of the source
instead, which is also what lets it answer the question without either module being importable.

Worth keeping: **the prose version of a question finds one instance; the mechanical version finds the
class.** Reading comments turned up two false uniqueness claims in two loops, which is a good rate
and does not scale. One `ast` walk over the package answered the same question for every constant in
it, and the one that mattered was in neither comment.

## Result 192

**The audit skipped, in silence, any source file that would not parse — and the guard I wrote for it
crashed the first time a test handed it an unusual path.**

Result 191's lesson was that the mechanical form of a question finds the class. Applied to failure
handling: which handlers swallow their exception? Sixteen do so with no comment nearby. Most are
fine — narrow, typed, skipping something genuinely optional. Three are in `untell-audit` itself:

    duplicate top-level definitions   except (SyntaxError, UnicodeDecodeError): continue
    bare-max comparisons              except (SyntaxError, UnicodeDecodeError): continue
    the decorator registry            except (SyntaxError, OSError): continue

A file that stops parsing leaves those checks examining fewer files and still printing PASS. That is
the failure this tool exists to catch everywhere except in itself, and it is precisely the defect
`audited_doc` was written for one level up, where a missing document used to be `continue`d past
without a word. The same hole, in the same file, at a different granularity — and the fix for the
first did not prompt anyone to look for the second.

VERIFIED by writing one unparseable file into the package:

    FAIL  untell/_mutant_probe.py: parses, so the AST checks can read it
          (SyntaxError: invalid syntax — every AST check skipped this file)

It cannot fire on the repository as it stands. Every file parses, which is why the skip has been
free — free exactly until it is not, and then silent.

**The guard was itself broken, and its own test found it.** `path.relative_to(REPO)` raises for
anything outside the repository, so reporting a failure about a `tmp_path` replaced the named finding
with a `ValueError` traceback: the failure mode the helper exists to remove, reintroduced inside the
helper. Then the reachability assertion — "no AST walk parses a path directly" — failed on
`audited_tree`, which necessarily does exactly that. Two corrections before a guard about silence was
itself quiet.

The run also surfaced two standing FAILs, now fixed: the test-module count was stale by six after
this session's new files, and `UNTELL_POLICY_WHOLE_DOC` was undocumented. **`untell-audit` is green —
0 failures across 40 checks** — for the first time in many loops.

Worth keeping: **`except: continue` inside a verifier is a different animal from `except: continue`
anywhere else.** Sixteen silent handlers, thirteen of them defensible, and the three that mattered
were the three inside the thing whose entire job is to notice.

## Result 193

**A 406-word document came back untouched with 41 tells, after the rewriter produced a version with
34 — and the loop was right to refuse it.**

Every measurement in this document uses corpus texts of about 120 words. The flagship use case is an
essay. Run at four lengths, `tier=lite`, `structural`, `best_of=1`, seed fixed:

    words   secs    pre      post     delta     tells      changed
      207  20.81  0.6239   0.6239   +0.0000   23 -> 23     False
      406   2.61  0.5987   0.5987   +0.0000   41 -> 41     False
      697   8.08  0.5335   0.4713   -0.0622   60 -> 49     True
     1136  20.53  0.4847   0.4351   -0.0496   98 -> 85     True

The 207-word row's 20.81s is first-call warm-up, not length — the trap Result 183 records, and this
table would have shown "short documents are slowest" to anyone reading the column without it.

The 406-word row is the finding. `rewrites=2, adopted=0`: candidates were drawn and both refused.
Scoring one directly says why:

    tells          41 -> 34          better by this tool's own catalogue
    detector max   0.5987 -> 0.6203     WORSE, so correctly not adopted
    meaning gate   passed

**The two objectives disagreed, and the loop follows the one it optimises.** Removing seven
catalogued tells made the stdlib detector score go up. That is the same direction-of-travel problem
this log records for `tells/100w` on real text, arriving in the place where it actually costs the
user something: a document that is measurably less AI-tell-ridden was thrown away because the number
the loop drives went the wrong way.

Nothing said so. `changed: false` on its own reads as "the tool did nothing", which is
indistinguishable from "the tool tried and every draft was worse". The two fields that separate them
— `rewrites` and `adopted` — were already in the payload and are the ones nobody reads.

The note now names what happened and the three remedies that exist (`--best-of`, a different
`--rewriter`, `--tier full`, where the score has more to respond to), and says outright that this is
the loop refusing to make the score worse rather than a failure to run, so it does not invite a bug
report against correct behaviour.

Worth keeping: **the most useful thing in the payload was the absence of an event, and the tool had
no vocabulary for it.** Every caveat added this session describes something the input IS. This one
describes something the loop DID and then undid, which is invisible in the output by construction —
the whole evidence for it is two integers that agree with each other.

## Result 194

**The caveat added one loop earlier stated a reason the code could not have known, and I wrote it.**

Result 193 added a note for the state where the loop draws candidates and keeps none. It said:

    "every draft scored worse than your text"

Checking that sentence against the code it describes: the meaning gate `continue`s **before** the
score is computed.

    if veto_contradictions:
        if not meaning_preserved(masked, candidate, sim, sim_bar):
            continue          <- never reaches score(candidate)

So a draft refused by the gate is never compared on score at all. On any run where the gate did the
refusing, the note asserted the outcome of a comparison that did not happen — and it would have said
so with the same confidence as when it was true, because it took the same branch either way.

Nothing in the loop recorded WHY a draft was dropped. `rewrites` and `adopted` were the only counters,
and their difference is silent about cause. Both veto sites now increment one, and the note has three
branches:

    all drafts vetoed   the gate refused every one; none was scored; try a different rewriter
    mixed               N changed the meaning and M scored worse
    none vetoed         the original wording, now true whenever it appears

**The remedies diverge, which is the whole point of naming the cause.** A score refusal means the
drafts were safe and unhelpful: more draws might find a better one. A gate refusal means the drafts
changed what the text said: more draws of the same rewriter will keep failing, and the honest advice
is to change rewriter. The test asserts `--best-of` does not appear in the gate wording, because
suggesting it there would be advice that cannot work.

Worth keeping: **a caveat is a claim, and it inherits the burden of every other claim in this
document.** The previous result checked that the note fired in the right state, that it was
actionable, and that it did not read as a malfunction. It did not check whether the sentence was
true, and it was the only new sentence in the change.

## Result 195

**The caveat was true, and true for the wrong reason. Splitting had been sitting behind a guard for
transforms that need a pair, and splitting needs one sentence.**

Result 194 established that a caveat is a claim carrying the same burden as any other. Applied to the
one this session added for per-line documents, which says the transforms needing two adjacent
sentences "could not run". MEASURED by instrumenting a four-sentence document in two layouts,
3 seeds each:

                                 1 sentence/para   one block
        _merge_sentences               0               3
        _target_burstiness             0               3
        _drop_restatements             0               3
        _split_long_sentences          0               3

The claim checks out. Then the fourth row stops looking like confirmation and starts looking like a
defect: **splitting takes one long sentence and makes two.** It does not need a pair. The guard's own
comment names the ones that do — merge, restatement-drop, burstiness — and splitting is not among
them. It sat inside anyway, so a paragraph holding a single 40-word sentence could never be split,
which is precisely the case splitting exists for: a transcript line, a bullet, a lone abstract
sentence.

`_strip_transitions` and `_vary_openers` were both moved out of this guard before, each time citing
that same comment. This is the third, and the comment has now outlasted three of the transforms it
was misapplied to.

After: split runs **12** times on the per-line document against 0, still after the guarded block, so
a multi-sentence block sees merge then split in the order it always did. The caveat is updated with
it — it names merging, restatement removal and sentence-length variation now, and the test asserts
those three are 0 while splitting is not.

**Two things found while verifying, neither mine.** The wider structural run surfaced two stable
failures in `test_sentence_targeting_is_weaker_than_the_docstring_claimed.py` — deterministic across
two runs, in a file that makes zero reference to the rewriter, and whose own assertion messages say
the docstring should be re-measured because separation IMPROVED. And `git push` has been rejected
three times with a GitHub `Internal Server Error`; the commit is local and intact.

Worth keeping: **verifying a claim is a different activity from trusting it, and it finds different
things.** Checking whether the note was true produced a table where three rows confirmed it and the
fourth, which also confirmed it, was the bug. A test that only asked "does the note fire in the right
state" — which is what the previous loop wrote — would have passed on all four.

## Result 196

**I reported a red test on main last loop. It was my environment, and the correction is worth more
than the report was.**

`test_sentence_targeting_is_weaker_than_the_docstring_claimed.py` failed twice, deterministically,
across two runs, in a file that makes no reference to the rewriter I had just changed. I checked that
it was not mine, checked it was not flaky, and said so. What I did not check was the one variable I
set on every command in this session.

MEASURED, same file, same machine, the only difference being an environment variable the README's own
reproduce command sets:

    with mage        AUROC <= 0.886, 12+ of 40 human sentences at the ceiling      5 passed
    without mage     AUROC 0.935,    11 of 40 at the ceiling                       2 failed

Every number in that file is a property of the FULL ensemble, and it scores at `tier="full"` with no
guard on what that ensemble contains. Removing a detector can only lower `max`, and here it lowers
the HUMAN side further than the AI side, so separation IMPROVES and the two assertions pinning the
file's finding both fire.

**Their messages then name the wrong cause with complete confidence:**

    "if that improved, the docstring's re-measurement is stale and should be redone"
    "sentence-level separation now clears the documented floor — good news, and the docstring
     re-measurement should be updated"

Nothing about the measurement was stale. The ensemble was smaller. I read those two sentences and
concluded that a concurrent session had committed broken work — which I then wrote down.

`test_detectors_full.py` already carries this exact guard, and its comment records the identical
lesson: "following the documentation and then running the suite produced two failures that were not
bugs". The newer file did not inherit it. The same shape as Results 178 and 180 — a guard applied
where its author stood.

Worth keeping: **an assertion message is a hypothesis, and a confident one is worth less than a
hedged one.** These two named a specific cause, and a reader with no reason to doubt them — me —
adopted it and attributed a fault to someone else's work. A message reading "this file requires the
complete full ensemble; check UNTELL_DISABLE_MAGE" would have cost the same characters and ended the
investigation in one line.

## Result 197

**One test in fourteen was ensemble-sensitive. Finding that out cost two full runs and the answer is
still partial — which is the honest shape of it.**

Result 196 found a file whose verdict flipped on `UNTELL_DISABLE_MAGE=1`. The mechanical follow-up:
how many others? Over the test suite:

    files scoring at tier full or heavy                     26
      of those, asserting a NUMERIC score threshold         14
      of those, guarding on ensemble completeness            2   (one of them added last loop)

The twelve that assert only shapes, keys and exit codes cannot be sensitive to a missing detector,
which is most of the surface and worth knowing.

MEASURED, the same files run twice, the only difference being the variable:

    six numeric files, both ways      41 passed / 41 passed     identical
    three more, MAGE off              67 passed
    three more, MAGE on               did not finish inside ten minutes

So of the fourteen: **one sensitive and now guarded, six verified insensitive both ways, seven not
yet verified.** The seven are named by the sweep rather than assumed away, and the reason they are
unverified is cost — loading the full ensemble for the heavier files runs past the time budget, which
is also why nobody had run this comparison before.

Worth keeping: **the cheap half of this question answered itself and the expensive half did not.**
Twelve files were ruled out by reading what they assert, not by running them — a grep for a numeric
threshold in an assertion separated "cannot be affected" from "might be" in seconds, and left a
fourteen-file problem instead of a twenty-six-file one. The remaining seven need the slow answer, and
the useful thing to record is which seven.

## Result 198

**The variable that produced a wrong conclusion was set in every command and printed in none of the
output.**

Result 196 records reading two deterministic failures, checking they were not mine, checking they
were not flaky, and concluding that someone else's committed work was broken. The cause was
`UNTELL_DISABLE_MAGE=1`. Result 197 then found that 14 test files assert a numeric full-tier figure
and only one guarded on the ensemble being complete — and left seven unverified because running them
both ways costs more than the time budget allows.

Guarding all fourteen is the expensive answer. The cheap one is to stop the fact being invisible:
`pytest` now prints the ambient scoring settings at session start and again in the terminal summary.

**Both, because the header alone would have been useless here.** `pytest_report_header` is suppressed
by `-q`, which is what CI runs and what every command in this repository's documentation uses — a
guard placed where the reader is not, which is Result 182's finding arriving in the tooling. The
summary line prints after the failures, where someone reading them is already looking:

    untell scoring env: UNTELL_DISABLE_MAGE=1, UNTELL_LITE_NO_TORCH=1
      a reduced ensemble moves every numeric full-tier figure — check this before concluding a
      measurement is stale

Silent when nothing is set, so a clean run gains no noise, and the header still says "none set
(complete ensemble)" under normal verbosity.

The conftest already documented this exact class for the other variable: three tests were "reading
that path out of the ambient environment instead of asking for it", fixed with an opt-in fixture that
lets a test REQUEST the stdlib path. This is the other half — making the ambient state visible for
the tests that read it anyway.

Worth keeping: **the fix for a wrong conclusion is not always a better test.** Fourteen files could
each gain a guard, and seven of them cannot be verified inside the time budget. One line of output
that was missing costs nothing, applies to every file including the ones nobody has audited yet, and
would have ended the original investigation before it produced a false accusation.

## Result 199

**One environment variable turned 1.0 into 0.17 and the verdict from AI into clear, and the payload
said nothing about it.**

Result 198 made the ambient scoring settings visible in the TEST output. The product form of the same
question: does a user see which detectors ran? MEASURED on one paragraph at `--tier full`, the only
difference being a variable the README's own reproduce command sets:

    complete ensemble        5 detectors    max 1.0000    flagged True
    UNTELL_DISABLE_MAGE=1    4 detectors    max 0.1722    flagged False

Same text, same command. `flagged` is the headline and nothing qualified it — the `detectors` dict
does list what ran, so a careful reader could notice the absence, but noticing requires already
suspecting.

**Three ways for a detector to be absent, and only two were covered.** `failed_detectors` names the
ones that loaded and raised. The abstention note covers the ones that loaded and returned None, and
says outright that the error runs toward NOT flagged. A detector that was never selected — no model
file, no key, or a documented opt-out — took neither path, because `available()` returning False is
not an error anywhere in the system. The tier-mismatch branch stayed quiet too: with four of five
members the effective tier is still `full`, so nothing was downgraded and nothing was said.

**The first version had a false positive that made the point twice.** It reported "ran without radar"
on a COMPLETE ensemble. `radar` arrives only via `UNTELL_ENABLE_RADAR`, so its absence is the shipped
configuration rather than a loss; `mage` is the other kind, enabled by default and removed by an env
var. Opt-in and opt-out look identical from the registry, and only one of them is news.

**Then it collided with an existing test**, which asserts that a healthy ensemble carries no "errs
toward NOT flagged" phrasing. My note used the same words for a different situation, so the two
caveats became indistinguishable to anything keying on that string — and the collision is the
evidence: the wording is now distinct, and each caveat is testable on its own terms.

Worth keeping: **the direction of an error decides how much it matters.** Every absence here lowers
`max`, and a lower `max` means "reads as human". The whole failure runs toward telling someone their
AI text is clean — which is the direction this repository spends most of its guards on, arriving
through a door nobody had put a guard on: not a detector that broke, but one that was never asked.

## Result 200

**The caveat landed on two surfaces out of three, and the one it missed is the one with an exit
code.**

Result 199 added a note for a full ensemble running a member short. It went into `score_text`.
MEASURED immediately afterwards, one paragraph at `--tier full` with `UNTELL_DISABLE_MAGE=1`:

    score_text    roster note present
    untell_text   roster note present
    verify        roster note ABSENT, passes_all True

`untell_text` inherits it because it forwards `best_score["warning"]`. `verify` builds its own caveat
list, so nothing arrived — and `verify` is the command CI runs and the one that turns a verdict into
an exit status. A reduced ensemble can only lower `max`, which can only turn a fail into a pass, so
the single surface where that matters most was the single surface not saying it.

This is the third time in this session the same shape has appeared: a correct fix reaching the places
its author was looking at. Result 178 found an earlier calibration fix that reached `verify`'s local
rows and not its commercial ones. Result 180 found a style guard on the CLI and REST but not the
library. Now a caveat on `score_text` and the loop but not on `verify`.

After: the note appears next to `passes_all: True` on a reduced ensemble and stays absent on a
complete one.

Worth keeping: **"which surfaces did this reach?" is worth asking every time, and it takes one
measurement.** Three calls, three booleans. The answer has been wrong three times out of three when
somebody thought to ask, which is a better hit rate than most questions in this document — and each
time the missing surface was the one furthest from where the change was made.

## Result 201

**Three of four caveats never reached `verify`, and the two that did were the two somebody had
remembered by hand.**

Result 200 ended on "which surfaces did this reach?" being worth asking every time. Asked
mechanically of every caveat added this session, rather than one per loop:

    caveat             score_text   untell_text   verify
    no prose              yes          yes         NO
    mostly locked         yes          yes         NO
    one sentence/para     yes          yes         NO
    threshold range       yes          yes         yes

The single passing row is the one wired into `verify` by hand two loops earlier, and the roster note
from one loop earlier was the same. **That is the structural cause, not a coincidence:** `verify`
hand-picked a handful of caveat functions, so every caveat added to `score_text` had to be remembered
separately here — and three in a row were not.

`untell_text` never had the problem, because it forwards `best_score["warning"]` and inherits
whatever the score decided to say. `verify` now does the same, which retires both hand-wired caveats:
they travel inside the forwarded string, and the threshold note appears exactly once. Commercial-only
mode keeps the text-shape caveats, since no local score runs there and there is nothing to forward.

**The fix broke my own test from the previous loop**, which stubbed a score result with no `warning`
key. That was realistic against the hand-picked implementation and is not against this one — the
stub now carries a warning and the assertion is about forwarding, which is the property that keeps
the next caveat from going missing.

Worth keeping: **fixing an instance three times is the signal that the instance was never the
problem.** Results 178, 200 and this one are the same defect at increasing resolution: a caveat wired
where its author stood, then a second, then the realisation that the surface re-derives what it could
inherit. The mechanical sweep cost one measurement and answered for all four at once, where three
loops of asking one at a time had answered for two.

## Result 202

**All five surfaces now carry every caveat — and the one that looked like a gap turned out to be the
strongest surface of the five.**

Result 201 fixed `verify` and swept three surfaces. REST and MCP had never been checked. Completing
it:

    caveat             score_text  untell_text  verify  REST  MCP
    no prose              yes         yes        yes    yes   yes
    mostly locked         yes         yes        yes    yes   yes
    one sentence/para     yes         yes        yes    yes   yes
    threshold range       yes         yes        yes    422   yes

REST forwards all three input-shape caveats. The MCP `score` tool does too: its only transformation
is `split_detector_errors`, which preserves every key.

**The threshold row is the finding, and it is good news.** REST does not warn about a threshold of
45 — it REFUSES it, with a 422 and a message naming the field and the bound:

    {"loc": ["body","threshold"], "msg": "Input should be less than or equal to 1"}

That is stronger than any caveat, because the caller cannot read past it. The library and CLI accept
the value and warn instead, on the ground that the fallback is documented behaviour. Both are honest;
they are different answers to the same question and the schema is the better one where a schema
exists.

My first version of the matrix asserted 200-and-a-warning on every surface and failed on that row.
**The assertion was wrong, not the surface** — which is the third time this session a test I wrote
one loop earlier had to be corrected against the code it describes (Results 194 and 201 are the
others).

So the matrix asserts what actually matters: **no surface may accept a bad input in silence.** Either
the caveat arrives, or the request is refused. It is the guard that would have caught all three
`verify` gaps, and it fails in CI now rather than in someone's terminal.

Worth keeping: **a cross-surface matrix finds the surfaces that are BETTER than the others, not only
the ones that are worse.** Every previous result in this thread was about something missing. The same
sweep, run once more, turned up a surface doing something the others do not — and the useful output
was not a fix but a corrected expectation.

## Result 203

**`best_of=0` drew a draft anyway. The caller asked for zero and got a rewrite that looked like every
other rewrite.**

Result 202 found REST refusing an out-of-range threshold rather than warning about it. Read in
reverse, that is a list: **every constraint REST enforces is a claim about valid input that the
library does not make.**

    max_iters   Ge1, Le100        best_of   Ge1, Le32
    threshold   Ge0.0, Le1.0      margin    Ge0.0, Le1.0
    text        MaxLen 50000      tier      Literal

MEASURED against the library, one paragraph at `tier=lite`:

    max_iters=1  best_of=1    changed=True   rewrites=1  adopted=1
    max_iters=0               changed=False  rewrites=0  adopted=0   nothing said
    max_iters=-3              changed=False  rewrites=0  adopted=0   nothing said
    best_of=0                 changed=True   rewrites=1  adopted=1   value ignored
    best_of=-2                changed=True   rewrites=1  adopted=1   value ignored

**Two different failures, and the quieter one is worse.** A non-positive `max_iters` returns the
input untouched and says nothing — Result 193's adoption caveat cannot cover it, because no draft was
ever drawn to refuse. A non-positive `best_of` is not respected at all: one draft is drawn regardless,
the text changes, every field reads normally, and nothing anywhere indicates that the setting was
discarded. A silent no-op at least leaves the text as evidence; a silently ignored setting leaves
nothing.

Both now warn, matching how the library already treats an unknown tier, an unknown style and an
unreachable threshold. REST keeps its 422 and a test pins that the two surfaces have not silently
converged, because Result 202 established that both answers are honest and they are answers to
different questions.

**I swept these exact values in Result 181 and called them defensible.** The sweep was the right one
and the conclusion was wrong: `max_iters=0` returning the input looked like a reasonable reading of a
zero budget, and `best_of=0` drawing anyway looked like harmless clamping. What was missing was the
comparison — REST's schema had already been a shipped claim that both are invalid, and I had looked
at only one surface.

Worth keeping: **a second implementation of the same contract is a free review of the first.** Two
surfaces, one of them written by someone thinking about validation, and the disagreement between them
is a list of defects that needs no judgement call to produce — only the discipline to read both.

## Result 204

**Two more pairs read as reviews of each other. One found nothing, and the nothing is worth having.**

Result 203's lesson was that a second implementation of a contract reviews the first for free. Two
more pairs exist in this repository.

**`score_text` against `batch_score_texts`**, over 12 corpus texts: worst `|max|` difference
**0.000000**, identical key sets. A clean null — and not a trivial one, because per-sentence
targeting runs through the batch path while the loop runs through the single-text path, so a drift
between them would put the sentences the rewriter is told to fix on a different scale from the
document verdict it is judged by.

**CLI against REST against the library**, on the values Result 203 fixed:

    value            CLI       REST      library
    max_iters=0      refuses   422       warns
    best_of=0        refuses   422       warns
    threshold=45     refuses   422       warns

The CLI refuses all three, through custom argparse `type=` callables rather than plain `int` — which
is why the earlier sweep of `choices` found nothing to report on those flags.

**The split is coherent and it is one session old.** The two surfaces a human types into refuse,
because a typo there is a typo. The programmatic surface warns and proceeds, because an embedding
caller may be passing a value from a newer version and refusing the whole run would be harsher than
the mistake deserves. Before Results 181 and 203 the library was not the lenient member of a
deliberate design — it was simply silent, which is the same behaviour with none of the intent.

Pinned in both directions now: a later change making the library raise would break embedding callers,
and one relaxing the CLI would admit a typo where it is most likely to be made.

Worth keeping: **a null from a comparison is cheaper than a null from a sweep and says more.** Twelve
texts through two functions answered a question that no amount of reading either function would have
settled, and the answer — exact agreement — is the kind of fact that is only ever noticed when it
stops being true.

## Result 205

**Three "ideal" burstiness values in one codebase. The one shown to users was the only one nothing
supports.**

`humanness` names 0.70, the rewriter's default profile targets 0.45, and Result 172 measured human
prose near 0.48. At most two of those can be right.

MEASURED, sentence-length coefficient of variation over 40 human texts per corpus, >=90 words:

    corpus   human mean   human median   AI mean   texts reaching 0.70
    HC3        0.514        0.491         0.278       6 / 40
    RAID       0.350        0.326         0.262       1 / 40

**7 of 80 human documents reach the figure the advice named.** The tool was telling users that human
prose sits at a value 91% of human prose does not reach.

**The score was never wrong, and that is the part worth reading.** `_BURSTY_IDEAL` has never appeared
in the penalty arithmetic. The penalty applies below 0.50 and above 1.0, and 0.50 sits almost exactly
on the measured HC3 human median — a well-calibrated cut, arrived at independently of the constant
sitting twenty lines above it. `_BURSTY_IDEAL` is used in a shape label, where every value inside the
unpenalised band behaves identically, and in the sentence shown to the user. The defect was one
sentence attached to correct arithmetic.

**The replacement is two numbers.** The corpora differ by more than either differs from the old
constant — forum answers vary their sentence length far more than paper abstracts — so a single
figure would put the same error in a new place. The advice names both and says which register each
belongs to.

A test pins that the penalty still does not reference the constant, so wiring it in later would be a
scoring change rather than a quiet one, and another checks the quoted medians against the corpus
rather than trusting them.

Worth keeping: **a constant that is never used in the arithmetic is not harmless — it is the part a
user reads.** Every guard in this repository points at the code path; this one lived entirely in the
explanation, was never wrong in any test of behaviour, and was the only number in the file a reader
was ever asked to act on.

## Result 206

**Two of the three numbers users are shown reproduce exactly. The third does not, and it is left
standing.**

Result 205 found a figure in advice text that no corpus supported, so the class is worth sweeping:
which runtime messages quote a number, and does the corpus still agree?

    lite-tier caveat   "64% of HUMAN text above 0.30, and 30% is FLAGGED"
                       -> 64/100 and 30/100, exactly, on 100 HC3 human texts
    false-positive     "5 of 30 HC3 forum answers were flagged (17%)"
                       -> 6/30 (20%), one document apart at n=30

The lite caveat is the message this tool shows most — Result 182 measured it firing on 120 of 120
corpus texts — and both of its figures land on the nose.

The short-text bands did not. Re-running the TRUNCATED arm on 40 HC3 human texts of mean 332 words,
counting `max >= 0.30`, on **both** lite paths:

    band   shipped      stdlib path   gpt2 path
      5    ~100%             0%           0%
     10    ~85%             10%           8%
     20    71-85%           35%          10%
     40    86-100%          62%          22%

Every band lower, on both paths, by a factor of two to infinity. The 5-word row is not abstention: a
five-word text returns a real `0.0` rather than declining to score.

**The figures are left standing, and that is the result.** The comment above them says, of the
numbers it replaced: "replacing measured numbers with differently-measured numbers would swap one
unstated method for another." That rule binds whoever re-measures next, including me. Two variables
are known to differ — sample length 332 against 212 words — and one is unknown: the settled run does
not record which lite path it used, and the tier silently uses GPT-2 when torch is importable. A
disagreement with two known differences and one unknown is a failed reproduction, not a refutation.

So the conditions are recorded next to the numbers rather than the conclusion, and the note says what
would settle it: re-run with the path pinned.

Worth keeping: **the discipline that produced a number has to survive the person disagreeing with
it.** Everything in this session pushed toward replacing the table — I had four measurements, two
paths, and a clean story about the direction inverting for short inputs. What stopped it was a
sentence written by whoever measured it last, warning against exactly the move I was about to make.

## Result 207

**The path was the unknown, and pinning it settled the shape while refuting the level.**

Result 206 left the short-text bands standing as a failed reproduction with one variable unresolved:
the settled run does not record which lite scoring path it used, and the tier silently uses GPT-2
when torch is importable. Matching its stated sample and pinning the path:

    band   shipped     stdlib path   gpt2 path      40 HC3 human texts, 120-320 words
      5    ~100%            0%          5%          (mean 188; the settled run used mean 212)
     10    ~85%            18%          5%
     20    71-85%          50%          8%
     40    86-100%         65%         10%

**The stdlib path is unambiguously the one that was measured.** It rises with length exactly as the
shipped table does, while GPT-2 is flat and three to six times lower. So the shape was right and the
level was not: every band 20 to 35 points low, except the 5-word row at 100 points low, which no
sampling difference explains.

That closes the objection Result 206 raised against itself. The rule in the note was against swapping
one **unstated** method for another; the method here is stated in full, and the bands are now the
range across both lite paths, because either can run and nothing in the result says which did.

**Replacing the numbers alone would have reintroduced the exact defect that note was written about.**
It says the string "exists to tell a caller their verdict is unreliable, and it was reassuring them
instead" — and "0-5% of HUMAN text this length also flags" reads as reassurance. The rendered message
proved it: at four words the caveat came out sounding like a clean bill. So the sentence changed with
the numbers, and now says what the measurement actually shows — the score collapses toward its floor
as text gets shorter, so a CLEAR verdict carries as little information as a flagged one.

The naturally-short arm is still unmeasured and marked as such, because a truncated fragment and a
complete short reply are different objects — which is the distinction the previous note was built
around.

Worth keeping: **a number and the sentence around it are one claim, and changing half of it is how
you get a caveat that reassures.** Two loops ago the figures were wrong and the sentence was right.
Correcting the figures alone would have left the sentence wrong in the more dangerous direction, and
the only reason that was caught is that the message was rendered and read rather than reasoned about.

## Result 208

**Eleven caveats rendered side by side. Ten read correctly and the eleventh contradicted itself.**

Result 207's lesson was that a number and its sentence are one claim, caught only because the message
was rendered and read. The obvious next step is to do that for all of them at once — this session
added seven caveats and each was inspected alone, at the moment it was written.

Printed together, the budget note from Result 203 read, at `max_iters=0, best_of=0`:

    "max_iters=0 means no rewriting was attempted at all, so your text came back exactly as you
     sent it. Pass 1 or more to run the loop. best_of=0 is not a number of drafts, so it was
     ignored and one draft was drawn."

**No draft was drawn.** `rewrites=0` at `max_iters=0`, measured in the same result that introduced
the note. The second sentence was false exactly when the first was true.

Neither half is wrong on its own, and that is why nothing caught it. The two conditions are
independent in the code and not in the world: a non-positive `max_iters` stops the loop before
`best_of` can mean anything. **The test covering this case asserted that both phrases were present**
— it was written to check the composition and pinned the bug instead.

The other ten hold up, including the ones this session rewrote after finding them wrong: the
short-text bands now say the score collapses toward its floor rather than reassuring, and the roster
note says a short ensemble makes text look more human rather than borrowing the abstention note's
wording.

Worth keeping: **a caveat is written once and read in combination.** Every one of these was correct
in the situation it was written for. The one that failed did so only in the presence of another,
which is a state no author is thinking about while writing either — and which costs one command to
check for all of them at once.

## Result 209

**No caveat repeats another, and the clean null is the interesting part.**

Result 208 found a defect that existed only in the composition of two caveats. Two more composition
properties follow from that, and neither had been checked.

**Redundancy.** MEASURED on the three inputs that fire the most caveats at once — code with a bad
threshold, quotations with a bad threshold, and code alone: 12 to 14 sentences each, and **0**
near-duplicate pairs, counting a pair as near-duplicate when it shares six consecutive words.

That null is not an accident, and tracing why is worth more than the result. The roster note and the
abstention note both describe a short ensemble, and both were at risk of saying it in the same words —
Result 199 records that the first draft of the roster note reused the abstention note's phrase
verbatim, which collided with a test keying on that string. Rewording it to avoid the collision is
what makes this sweep come back empty. The guard against duplication was installed by accident,
three results before anyone looked for duplication.

**Length.** Nothing caps how many caveats can stack, and this session added seven. Corpus warnings
run to a median of 503 characters and a maximum of 882 (Result 182, 120 texts); the worst pathological
input measured here is **1794 across 14 sentences**. The bound is now set above that and below twice
it — a regression guard rather than a target. Result 182's ordering fix means a reader meets the
specific caveat first, so length is a cost rather than a defect; this exists so the cost cannot grow
without someone deciding it should.

Worth keeping: **a property that holds by accident is worth pinning precisely because nobody chose
it.** The distinct wording that makes these eleven caveats non-redundant was the side effect of a
test collision, and nothing recorded it as a requirement. It would have survived exactly until the
next person wrote a caveat about a short ensemble.

## Result 210

**A measurement without a test is a fact about one afternoon.**

Result 204 measured `score_text` and `batch_score_texts` agreeing to 0.000000 and moved on. Result
209 then established why that is not finished work: the non-redundancy of eleven caveats turned out
to rest on a wording change made three results earlier for an unrelated reason, recorded nowhere as
a requirement, and it would have survived exactly until the next person wrote a caveat about a short
ensemble. The same is true here, and the stakes are higher.

`score_sentences` reaches the detectors through `batch_score_texts`. `untell_text` and every verdict
surface reach them through `score_text`. **Nothing required the two to agree.** A drift between them
puts the sentences the rewriter is told to fix on a different scale from the verdict it is judged by
— targeting pointing at a document nobody is scoring — and it would be invisible, because each path
is internally consistent and neither reports the other's numbers.

Pinned as four properties rather than one, because `max` agreeing is the weakest of them:

    the same keys              a field on one path and not the other is a KeyError a caller
                               cannot predict from the documented shape
    the same per-detector      `max` can match while the members behind it differ, which is a
      values                   reordering nothing above would catch
    a batch of several         the batch path exists to load detectors once for many texts, so
      matching one at a time   state leaking between items is the risk it carries
    the texts not all          three texts scoring identically would satisfy every assertion
      scoring alike            above while proving nothing — the shape of the saturating
                               detector this repository has shipped

No specific value is asserted anywhere in it. The claim is that the two paths answer alike, whatever
they answer, so it survives detector changes, threshold changes and corpus changes — which is the
difference between a pin and a snapshot.

Worth keeping: **the gap between measuring a property and pinning it is where the property goes to
die.** Six results in this session measured something true and moved on; this one went back for the
one where the consequence was worst. The measurement cost nothing to repeat, and the version that
survives a year is the one with a test attached.

## Result 211

**The most-shown sentence in the tool quotes two percentages. Nothing checked them, and pinning them
took three corrections — all to the test.**

Result 210 ended on a list: six results this session measured something true and moved on. This is
the one with the widest reach. The lite-tier caveat fires on **120 of 120** corpus texts, so every
run on a default install carries it, and it says "64% of HUMAN text scores above the 0.30 loop
threshold, and 30% is FLAGGED".

MEASURED at n=100, HC3 human halves, stdlib path: **64/100 and 30/100**, exactly. Pinned rather than
corrected — which is the outcome this session has not often had for a number in prose. Result 205
found `humanness` naming a burstiness 7 of 80 human documents reach; Result 207 found the short-text
bands overstating by 20 to 100 points. Both were correct when written and unguarded afterwards.

**Three corrections while writing the test, and all three were the test's fault.**

The premise assertion did not pin the scoring path, so torch upgraded lite to GPT-2 and the stdlib
caveat correctly did not fire — Result 196's mistake, repeated by the person who wrote Result 196.

The module fixture then flipped the environment variable without clearing the score caches, serving
results from the path it had just left: 52.5% and 17.5% against a claimed 64% and 30%. The repo's own
`conftest.stdlib_lite` clears them and says why.

And a cheaper n=40 run gave those same 52.5% and 17.5% honestly — **a twelve-point swing from sample
size alone.** The claim is about 100 pairs, so pinning it at 40 would pin a different claim. The
tolerance covers detector jitter, not a change of denominator.

The inventory assertion is read off the sentence rather than written from memory, which is how it
caught its own first version missing `1.000` and the two `n=30` denominators.

Worth keeping: **a test that pins a measurement has to reproduce the measurement, and that is harder
than making an assertion pass.** Every one of the three wrong versions produced a green-looking
number. The one that made the test pass at n=40 was the most dangerous, because nothing about it
looked like an error — it was simply a different experiment wearing the same assertion.

## Result 212

**Result 175 scaled from n=5 to n=10 x 3 seeds. The arm is worse than composite on every aggregate,
one of its two headline documents does not replicate, and the other one does.**

Same ten RAID documents `eval/holdout.py` measured composite on, three seeds each, 30 loop runs,
held-out RADAR scored last on frozen text. Composite ran at `best_of=3, max_iters=5` and this arm at
`2, 2` — a confound that favours composite, so it cannot manufacture a win here.

```
single-seed held-out mean (what a user gets)
  composite    0.5035 (4/10)   0.4981 (4/10)   0.4391 (4/10)
  base-model   0.5974 (6/10)   0.5434 (5/10)   0.6026 (6/10)

in sample     composite 0.4268 / 0.4063 / 0.4301    base-model 0.8376 / 0.7722 / 0.7810
base-model no-ops: 21 of 30 runs byte-identical
```

**Worse in sample, worse held out, worse flagged rate, and inert on 70% of runs.** Result 175 called
this a lever; at n=5 and one draw it looked like one.

Per document, held-out post by seed:

```
doc | RADAR pre | composite            | base-model           | better
  0 |  0.9514   | 0.973 0.940 0.980    | 0.423 0.443 0.752    | base
  1 |  0.8323   | 0.243 0.291 0.094    | 0.832 0.832 0.832    | composite
  2 |  0.7835   | 0.163 0.123 0.319    | 0.784 0.784 0.784    | composite
  3 |  0.9991   | 0.999 0.288 0.457    | 0.999 0.131 0.999    | base
  4 |  0.4467   | 0.096 0.996 0.102    | 0.039 0.035 0.073    | base
  5 |  0.4311   | 0.358 0.342 0.764    | 0.119 0.431 0.431    | base
  6 |  0.9996   | 1.000 1.000 1.000    | 1.000 1.000 1.000    | tie
  7 |  0.9387   | 0.865 0.733 0.355    | 0.939 0.939 0.939    | composite
  8 |  0.1371   | 0.019 0.019 0.023    | 0.137 0.137 0.137    | composite
  9 |  0.7029   | 0.320 0.250 0.299    | 0.703 0.703 0.080    | base
```

**Doc 0 replicates and is the one claim from 175 that survives.** Composite never takes it below
0.940 in three seeds; the base model moves it in all three and clears the 0.45 bar in two. Result 163
named doc 0 one of two documents composite cannot move, and it is movable — by a different proposer,
not by more of the same one.

**Doc 3 does not replicate.** 175 reported 0.0994 from a single draw; across three it reads
0.999 / 0.131 / 0.999, and composite reaches 0.288 on a seed of its own. One draw in three, quoted as
a result. Doc 6 remains immovable for both arms in all six runs.

**The complementarity is real, and it is worth exactly one number.** Five documents favour the base
model, four favour composite, one ties. Taking the better arm per document:

```
best-of-3-seeds, mean held-out          flagged
  composite only     0.3504              2/10
  base-model only    0.4479              4/10
  either             0.2377              1/10
```

**But that selector cannot be built from anything the loop can see.** It picks using the holdout. The
in-sample score would choose the opposite: doc 0's best base-model run reads **0.7604 in sample** —
by the loop's own objective its worst kind of failure — while the holdout says 0.423. `ensemble`
already exists and already selects per input; it ranks candidates on the quantity that misreads
precisely these cases. That is Result 163 again, now costing something concrete rather than
describing something.

Worth keeping: **n=5 and one draw of a stochastic rewriter is enough to produce a table, a mechanism
and a conclusion, and not enough for any of them to be true.** 175 had a real finding in it — doc 0 —
sitting beside an artefact of the same size and shape, and nothing in that run distinguished them.
Third time this session: the conviction split, doc 3, and the seeding defect that made even the same
seed unreproducible.

## Result 212b

*(Renumbered. This heading collided with Result 212 above; the number is suffixed rather than reassigned because Result 212 is cited by name elsewhere in the repository and those citations mean the earlier one.)*

**The suite's exposure to the scoring path is one file, and it is already guarded.**

Result 211 recorded three ways a test can fail to reproduce the measurement it pins, one of them
being an unpinned scoring path. The suite deserves the same question, because `conftest.stdlib_lite`
exists for exactly this: "three tests assert numbers that are only true of the pure-Python lite
scorer, and they were reading that path out of the ambient environment instead of asking for it."

    files scoring at lite tier that pin the path        46
    files asserting a lite number without pinning it    37   <- by a crude heuristic
    narrowed to a real score assertion                   4
    verdict changing when the path is forced             0

The 37 is the interesting number, and it is wrong. The heuristic counted any `assert ... == <int>`,
which catches `assert len(sentences) == 3` and every other structural check in the suite. Narrowing
to assertions that compare a score-like name against a decimal bound leaves **four**, and running
those four with the path forced both ways gives 42 passed either way.

So the lite path exposes nothing. Together with Result 197 — which found one file sensitive to the
FULL-tier ensemble, now guarded — the suite's total exposure to which detectors ran is a single file,
and it announces itself.

**Two loops, two heuristics, the same shape.** Result 197 turned a 26-file question into a 14-file
one by reading what each file asserts rather than running it; this turned a 37-file question into a
4-file one the same way. In both cases the cheap narrowing was worth more than the expensive sweep,
and in both cases the first number would have been publishable and wrong.

Worth keeping: **an over-broad detector makes a small problem look like a policy failure.** Thirty-
seven files asserting unpinned numbers would be a finding about how this suite is written. Four files,
none of them sensitive, is a finding about nothing — and the difference between them was one regex.

## Result 213

**Two characters fell between two classes: too wide for the invisible set, too narrow for the space
set, and score-moving in the direction that reads AI as human.**

This log records that U+00A0 alone took human text from 5 of 10 flagged to 9 of 10, so invisible
characters move scores. The product question is whether `scrub` removes everything that does.
MEASURED, each character inserted after every "e" in a two-sentence paragraph, lite/stdlib path:

    baseline                  0.6735
    U+200B, U+FEFF, U+00AD    0.6735   removed: yes   warned: yes
    U+2028 line separator     0.5545   removed: NO    warned: NO
    U+2029 paragraph sep      0.5545   removed: NO    warned: NO

**The cause is a category boundary.** `_EXOTIC_SPACE` covers Unicode category Zs; `score.py`'s
`_INVISIBLE_RE` covers Cf plus the soft hyphen. U+2028 is Zl and U+2029 is Zp — the only two
whitespace-ish categories neither class names. Every other character of that kind in Unicode is
caught by one or the other, which is why nothing had noticed: the coverage looks complete from either
side.

They are mapped to a newline rather than deleted. They ARE line breaks, and deleting one welds two
lines together — the damage the layout work elsewhere in this repository exists to prevent.

**Three self-inflicted errors on the way, and the third is the one worth recording.**

The first probe replaced spaces with the injected character instead of inserting it, so scrubbing
correctly returned a text with no word boundaries and every class scored 0.0000 — five families
looked broken and none was.

The second was an edit whose `\n` escape collapsed into a real newline and left an unterminated
string; ruff reported 18 errors and the file would not parse.

The third passed. A replacement was supposed to add two characters to a regex and prepend a comment
explaining why; the comment landed, the regex edit silently matched nothing, and the assertion
guarding it — `assert new != line` — was satisfied by the comment alone. The pattern was verified by
compiling it and testing a match, which is the only reason it was caught.

Worth keeping: **an assertion that a change happened is not an assertion that the change you meant
happened.** Two edits in one string, one guard covering both, and the guard reported success for the
half that did not matter.

## Result 214

**Ninety-five characters swept. Seventeen "defects", none of them real, and the one that was real had
already been fixed.**

Result 213 found U+2028 and U+2029 by thinking of two characters. The mechanical version tests every
BMP character whose category can hide one — Zs, Zl, Zp, Cf, Cc — inserted after every "e" in a
two-sentence paragraph, scrubbed, and rescored against a baseline of 0.6735:

    Cf and Cc (76 characters)    restored exactly
    Zl and Zp (2 characters)     not restored, by design
    Zs (17 characters)           not restored, and not a defect

**The first sweep reported all 19 as failures**, which would have been a serious finding about the
scrubber. It is a property of the probe. Inserting a real space into a word splits it, and plain
U+0020 shows the same 0.0000 as every exotic space — the giveaway was in the output and easy to walk
past, because SPACE sitting at the top of a defect list looks like a formatting artifact rather than
the refutation of the whole list. Normalising an EM SPACE to a plain space is correct handling; the
score change survives it because the text now genuinely says something else.

The Zl/Zp rows are the previous loop's fix working. They are line breaks, so `scrub` converts them
rather than deleting them, and the scrubbed text genuinely contains line breaks.

So the coverage is complete: of the 78 non-space characters, **76 round-trip exactly and 2 are
converted on purpose.** That is a stronger statement than Result 213 could make, and it cost one
loop after the fix rather than being available before it.

Worth keeping: **the control case belongs inside the sweep, not beside it.** Plain SPACE was in the
result set the whole time, scoring identically to the characters being accused. A sweep that includes
the ordinary member of each family answers "is this a defect or a property of my method" in the same
table, without a second experiment — and here it converted a list of nineteen findings into two, both
already known.

## Result 215

**The round-trip was never the problem. Coverage was — a span that is never locked cannot fail to
restore.**

The question was whether any transform can damage a preserved span, since a leaked sentinel is
visible garbage and a mangled one silently loses a citation. The obvious probe says no, emphatically:

    18 pipeline runs, citation/URL/quote/entity/code-dense documents, 3 styles
        sentinel leaks          0
        locked spans altered    0
    input already containing a ⟦HZ0⟧ token                    round-trips exactly
    a document with 84 locked spans                           round-trips exactly
    citations adjacent, at sentence end, at string start      round-trip exactly

That is a clean negative result and it would have been the whole loop. The finding came from one odd
row: `(Smith et al., 2019)(Jones, 2020)` locked **one** span for two citations. It round-tripped, so
the probe called it fine — but round-tripping is a property of what was locked, and it says nothing
about what was not. Asking the other question instead:

    (Smith, 2019)                one span
    (Smith 2019; Jones 2020)     TWO spans -- '2019' and '2020', the parenthesis left OPEN
    (see Smith, 2019)            TWO spans -- 'Smith' and '2019'
    (e.g., Smith, 2019)          THREE spans

The parenthetical rule required a capitalised author immediately after `(` and closed at the first
`)`. Anything else fell through to the entity and numeral rules, which lock the pieces and leave the
punctuation between them rewritable. MEASURED through the shipped loop, 8 forms x 2 styles:

    (Smith, 2019; Jones, 2020)   ->  (Smith, 2019. Jones, 2020)     DAMAGED
    (see Smith, 2019)            ->  (see Smith. 2019)              DAMAGED

**8 of 16 damaged.** The semicolon-to-sentence transform was editing inside citations. After the fix,
0 of 16, with 0 of 10 negative controls newly frozen.

Why a suite with 405 passing preservation assertions never saw it: **every citation in every existing
example is a single work.** The forms that break are the ones academic prose uses to cite a
literature rather than a paper — and the academic domain is the most-named gap in the competitor
census. The examples were all drawn from the same shape, and the shape was the bug.

Worth keeping: **a round-trip test cannot find a coverage gap, because it only ever asks about spans
that were locked.** It is a total function on the wrong domain. The two questions look alike and one
of them is much weaker; this repo has now been caught by that asymmetry twice, the other being
Result 214's `restore` sweep, which was similarly incapable of reporting a character it never saw.

## Result 216

**A plausible trigger is not a trigger. The first sweep gave every one of these a clean bill of
health.**

Result 215 found the citation gap by asking which real-world variants fail to lock. Applying the same
question to every other preserve category — url, quote, code, number, path, entity, version, 61
variants in all — 19 failed to lock as one span. Then the end-to-end check said **0 of 20 damaged**,
which would have closed the loop with nothing.

The probe was wrong. It put a **comma** inside each span, because a comma is plausibly what a
sentence-splitting rewriter reaches for. The transform that actually damaged citations in Result 215
splits on a **semicolon**. Re-aimed with the trigger known to fire:

    ‘the scheme paid for itself; the region kept the surplus’   (curly single quotes)
        ->  ‘the scheme paid for itself. The region kept the surplus’      2 of 2 DAMAGED
    <code>run a; then b</code>  ->  <code>run a. Then b</code>            12 of 12 DAMAGED

Two real defects, both invisible one probe earlier.

**Curly single quotes** were excluded from the quote rule deliberately and in writing: U+2019 is the
typographic apostrophe, so `‘...’` cannot be told from "don’t" by shape alone. The reason has a hole
in it — **U+2018 is not an apostrophe**, nothing writes `don‘t`, so the opening delimiter is
unambiguous and anchors the match. Only the close is in doubt, which makes the curly rule *safer*
than the straight-quote rule it was excluded next to, where both ends are ambiguous. The style
British and academic house styles use as a matter of course was the one still rewritable.

**HTML code tags** were a whole notation with no cover. Backticks lock, `<code>` did not, and every
tag in the family failed identically — `<pre>`, `<kbd>`, `<samp>`, `<tt>`, `<var>`, 12 of 12.

The false-positive bar exposed a second vacuity. The straight-quote rule cites 80 HC3 texts for its
0-spurious-matches claim, and **that corpus cannot test the curly rule at all**: 0 of its 160 halves
contain a single U+2018. Run anyway, it returns 0 the way a dead regex does. It is now recorded in
the comment as worthless rather than quoted as evidence, with the apostrophe-dense probe — 11 U+2019
apostrophes, no U+2018, 0 matches — carrying the claim instead.

Worth keeping: **when a probe reports zero, check that the instrument is the one that broke the last
thing.** Ten categories, twenty runs, a clean result, and the only difference between that and two
real defects was one punctuation mark chosen by plausibility rather than by evidence.

## Result 217

**The fix two results ago was the right fix for the wrong reason.**

Result 215 locked multi-work citations because `(Smith, 2019; Jones, 2020)` came back as
`(Smith, 2019. Jones, 2020)`. The diagnosis was "the citation pattern has a coverage gap". The
diagnosis was incomplete, and the evidence was already in the same output — `(--max-iters 3;
--best-of 2)` was damaged too, and that is not a citation by any reading.

The matrix that found it: 12 span types that fail to lock, against 6 carrier sentences. Four came
back damaged — and damaged by **all six carriers**, which is the tell that the carrier is not doing
it. A defect that fires under every condition is not conditional on any of them. The interior
semicolon was the cause, and preservation had nothing to do with it.

On ordinary prose with no citation, no code and nothing to preserve:

    The council approved the plan (the vote was seven to two; two members abstained) at the meeting.
        ->  (the vote was seven to two. Basically, two members abstained)

    5 of 5 documents damaged. 0 of 5 after the fix.

`_semicolons_to_periods` promotes "; " where the right side can stand alone, and had no notion of
brackets — but **no clause inside a bracket can stand alone**, however well-formed, because the
sentence continues after the closing bracket. The opener is the second half of it: once the break
exists the later stages treat the fragment as a sentence and give it one, which is how "Basically,"
ended up inside the parentheses.

So Result 215 fixed citations and left every other parenthetical in the language broken. The lock is
still worth keeping — it protects author names and years from transforms that have nothing to do
with semicolons — but it was a keyhole view of a general defect, and the general defect is three
lines of bracket depth.

Worth keeping: **when a defect fires under every condition you varied, you varied the wrong thing.**
Six carriers, twelve spans, and the uniformity of the damage was the whole message: the cause was in
the part I held constant. This is the third result in a row where the finding was already sitting in
an earlier output — Result 214's plain SPACE, Result 215's adjacent citations, and now this — and
each time it looked like an uninteresting row rather than a refutation.

## Result 218

**The corpus already contained the damage I was about to attribute to the rewriter.**

Result 217 fixed one transform. The obvious next question is whether the others do it too, and the
obvious way to answer it is to run real text through and count. On 40 HC3 halves containing a
bracket, that count says:

    sentence break inside a bracket   3
    unbalanced brackets               2

Both numbers are wrong as a measure of damage. HC3 is forum prose, and it arrives with 1 bracketed
sentence break and 2 unbalanced brackets of its own. Counted against the source instead of against
nothing:

    NEW sentence break inside a bracket   2
    NEW unbalanced bracket                0

**The unbalanced-bracket finding disappears entirely** — every instance was already in the input.
The other two are real, and they are commas rather than semicolons:

    (BSE, also known as "mad cow disease")   ->  (BSE. Also known as "mad cow disease")

So the previous loop's guard was on the wrong transform's punctuation. Both splitters choose the
comma nearest the midpoint, and a comma inside a parenthesis is the commonest comma there is.
`_split_one` already refused to split inside a **quotation** for the identical reason — the sentence
continues after the close — so the island was a concept the code already had and simply had not
extended to brackets. 2 → 0 after; 0 of 40 unbalanced throughout.

The guard is targeted rather than blanket, which is checked rather than asserted: over 1177 long
corpus sentences, 45.3% of bracket-free sentences still split and 36.1% of bracketed ones do, and a
closed bracket early in a sentence does not block a split later in it.

Worth keeping: **on real text, the baseline is not zero.** My own five constructed examples had a
clean baseline by construction, so the count and the damage were the same number and the habit of
subtracting never came up. The corpus is where a measurement gets its realism and also where it
gets its background rate — and here the background rate was 100% of one of the two findings.

Also worth noting what the earlier probe got wrong: two constructed sentences said the long splitter
had no bracket hole. Forty corpus halves said it had two. n=2 on hand-written examples is not a
measurement, and it was reported in Result 217 as though it were.

## Result 219

**Fourteen invariants, two corpora, and the one defect appeared only in the corpus the previous four
results never used.**

The mechanical version of the last three loops: instead of guessing which transform breaks which
construct, define what the output must satisfy and count NEW violations against the source. Fourteen
invariants — bracket balance, quote balance, doubled punctuation, doubled words, lowercase sentence
starts, stranded conjunctions, empty brackets, comma-before-close, and so on:

    HC3    50 documents, 62% changed, 14 invariants   ->  0 new violations
    RAID   50 documents, 64% changed, 14 invariants   ->  2 new violations

Two things make that table worth having. The change rate is in it, because "no new violations" from
a rewriter that did nothing is not a result — 62% of documents changed, so the sweep has something
to be clean about. And the corpora disagree.

The RAID rows:

    "(e.g. small branches or blurred edges)"  ->  "(e.g. Small branches or blurred edges)"

**`lock()` was masking the abbreviation.** The two-component dotted rule exists for `np.float64`,
its `\d*` matches zero digits, and so it claimed any `word.word` — 13 of the 47 abbreviations the
sentence splitter knows about. A sentinel followed by a dot looks exactly like the end of a
sentence, and the list that would say otherwise is one module away, consulted by `split_sentences`
and by nothing that runs on masked text.

The blindness was never confined to the capital pass. **Sentence splitting feeds burstiness,
per-sentence scoring and the targeted rewriter's unit of work, and all of them see the masked text**
— so every one of them was mis-counting a sentence wherever an abbreviation had been locked. That is
why the fix is at the lock rather than in the guard that caught it.

0 of 50 on HC3. Forum prose does not write "e.g.", so the corpus Results 215–218 measured on could
not have shown this defect however hard they looked.

Worth keeping: **an invariant sweep finds what a targeted probe cannot, because it does not need to
know what is broken.** The last three loops each started from a suspicion and found the defect that
suspicion pointed at. This one started from "what must be true of any output" and found a defect in
a different subsystem, of a different kind, in the corpus the others were blind to.

Recorded and not fixed: the dotted rule's own comment names `model.01` as an example it covers, and
it never matched — the second component must contain a letter. It locks "01" alone and leaves
"model." outside, a partial lock. Verified against unmodified `main` so the attribution is honest.
Widening the rule to `word.digits` would claim every "Section 3" in the language, so the example was
wrong rather than the pattern, and the comment now says so.

## Result 220

**The gate catches 8 of 12 deliberate meaning breaks. The 4 it misses cannot be produced by the
rewriters that exist.**

`meaning_preserved` is a conjunction of eight checks and nothing had ever asked whether each detects
the defect it exists for. One candidate per break, against a 26-word clinical sentence, NLI and
spaCy both live:

    vetoed      numeral changed, numeral dropped, percentage changed, polarity flipped,
                negation added, clause deleted, contradiction, count changed          8 of 12
    ADMITTED    certainty raised, certainty hedged, subject swapped, unit changed     4 of 12
    faithful    register change, reordered, de-nominalised, identical           0 of 4 rejected

The interesting part is what to do about the four, and the answer is nothing — decided by a
measurement rather than by taste:

    booster count change, 40 HC3 + 40 RAID documents through the shipped loop:   0
    hedge count change, same documents:                                          0

Not "rare". Exactly zero, both directions, both corpora. The free rewriters substitute words, merge
sentences and split them; none of those introduces "certainly" or "may have". A booster check would
be unfalsifiable on the only path that can be verified here — which is precisely the reasoning
`certainty_kept` already records for the two false vetoes it chose to keep.

Two of the four are different in kind, and worth naming:

* **`certainty_kept` is `not dropped_hedges(...)`** — one-directional by construction. It detects a
  hedge REMOVED; a hedge or booster ADDED is outside what it measures at all. The module's stated
  danger is "ships a strengthened claim", and a dropped hedge is one way to strengthen. This is a
  definition narrower than the claim above it, not a bug in the definition.
* **`role_swap` misses the drug/placebo swap**, and Result 221 records what that turned out to
  mean — the first reading of it, "the check degrades with sentence complexity", was wrong.

Worth keeping: **"we have a check for that" and "the check fires on that" are different claims, and
only the second one is a measurement.** Eight of these had never been demonstrated to fire; four
turned out not to. The gate is a hard veto in the meaning path, the most safety-critical code in the
repository, and its coverage was assumed by everything that referenced it.

The eight vetoes are now asserted; the four gaps are `xfail(strict=False)`, so closing one shows as
an XPASS rather than a failure. A separate assertion fails if any rewriter ever starts adding a
booster — which is what makes recording an unreachable gap better than deleting it from the list.

## Result 221

**Correcting Result 220: length was a confound, and the second variable was sitting one probe away.**

Result 220 recorded that `role_swap` "degrades with sentence complexity", on the evidence that it
caught a subject/object swap in a 7-word sentence and missed one in a 26-word sentence. Two
sentences, two differences, and I attributed the effect to the one I had been thinking about.

The crossed version — the same two swap shapes, each at 5 to 34 words:

    subject <-> direct object    "The council fined the contractor"        detected at 5, 8, 13, 26
    subject <-> noun inside a PP "reduced relapse in the placebo group"    missed at 8, 13, 20, 25, 34

**Length is not the variable at all.** The grammatical position of the swapped noun is. A swap into
a prepositional phrase is invisible to the check at every length tried, and a direct-object swap is
caught at every length tried, including one longer than the sentence the original miss came from.

The check is a gap and not a dead check, which the controls settle: passivisation, a by-phrase, and
a "issued a fine to" paraphrase all return False. It fires on the real thing and not on the
faithful rewrite that most resembles it.

Worth keeping: **two examples that differ in two ways measure neither.** The fix is the crossed
design and it cost one probe — hold each variable while varying the other, and the answer changes
from a plausible story to a fact. The plausible story was already written down as a finding, in a
document whose entire purpose is that its numbers can be trusted.

This is the second correction of its kind in this session. Result 196 accused a concurrent session
of leaving a test red on main; the cause was an environment variable in my own shell. Both were the
same error: an observed difference attributed to the first plausible cause without varying it.

## Result 222

**Three wrong readings in one loop, each caught by the next measurement, none of them committed.**

The loop began somewhere else entirely: does a markdown document survive the rewrite with its
structure intact? Headings, bullets, numbered lists, blockquote, table, code fence — **every count
identical, in and out.** A clean pass, and worthless: the output was byte-identical to the input.
`stopped=passed, iterations=0`. The document scored 0.209 against a 0.30 loop threshold, so the loop
declared it human and never ran. I was measuring the structural fidelity of a no-op. The change-rate
guard built in Result 219 exists for exactly this and I did not apply it to my own probe.

That misfire asked a better question. Text stuffed with the repository's own catalogued tells scores
0.209 — **does the detector respond to the tells the catalogue is built on?** The whole product
assumes so: it removes them to lower a score.

**Reading 1, from the means, was that two detectors are inverted.** Over 10 documents at 0, 2 and 8
injections, `roberta_openai` fell 0.100 → 0.084 → 0.013 and `fast_detectgpt` 0.091 → 0.081 → 0.074,
both monotone. Two of five ensemble members apparently getting *less* suspicious as AI clichés were
stacked in. That is a serious claim about the core assumption, and it is false. Per document:

    detector                  up   down   flat
    max (ensemble)            20      0      0
    perplexity_burstiness     20      0      0
    mage                      18      1      1
    roberta_openai            11      2      7
    fast_detectgpt            11      9      0
    hc3_roberta               10      1      9

Two large drops dragged an average that most documents moved the other way. The premise holds — the
ensemble rises on 20 of 20 — and the real finding is smaller and duller: `fast_detectgpt` is a coin
flip on this manipulation, `hc3_roberta` does not move at all on 9 of 20.

**Reading 2 was that two tells raise the score.** The test asserting it failed on the first run:
one tell lowers the salt text by 0.085, two lower the bridge text. Every document ends higher than it
started; none gets there monotonically. A measurement at a full dose does not license a claim about a
small one.

**Reading 3 was that the lite tier saturates after three tells.** The scores are identical from n=3
to n=8 — because the injector only targets sentences longer than six words, and those texts have
three. n=3 and n=8 are the same document. A fact about the harness wearing the costume of a fact
about the detector.

Worth keeping: **every one of the three was caught by the next thing I ran, and none by re-reading
the previous one.** The aggregate was refuted by the per-document record, the small-dose claim by
writing it down as an assertion, and the saturation claim by printing the dose-response instead of
its endpoints. Writing the claim into a test is not the last step after the measurement — it is
another measurement, and here it was the one that fired.

Also recorded, from the first misfire: a markdown document with three headings, two list types, a
table and a fenced block passes through the loop with every structural count intact. Untested,
because nothing was rewritten — the structural question is still open and now has a harness that
knows to check.

## Result 223

**Three hypotheses about markdown, in descending order of confidence, all wrong.**

Result 222 left a question open: a markdown document passed every structural check while the
rewriter did nothing, so structure-through-a-real-rewrite was untested. Raising the tell count to
force a rewrite did the opposite — the score fell from 0.209 to **0.144**. More AI clichés, less
suspicion, on a document where Result 222 had just measured the ensemble rising on 20 of 20. The
difference was the markdown, and that looked like a serious product finding: the tool never processes
structured documents, which is most of what people paste.

**Hypothesis 1: markdown lowers the score.** Crossed properly — the same 20 HC3 machine halves in
four forms:

    plain prose             0.5632   min 0.3667   20 of 20 over threshold
    + headings              0.5608   min 0.3603   20 of 20
    + bullet list           0.5632   min 0.3667   20 of 20
    + table and code fence  0.4416   min 0.3001   20 of 20

True but small, and it changes no verdict. Headings 0.002, lists 0.000, table and fence 0.122.

**Hypothesis 2: headings are nearly free.** Written into a test as an assertion, it failed on the
first run: on a single 70-word paragraph, headings cost **0.256**. The 0.002 came from long
documents and never licensed a claim about short ones.

**Hypothesis 3: the drop scales with the scaffolding's share.** The obvious repair. Fixed 30-word
scaffold, prose truncated to a target length:

    prose  40 words (43% scaffold)   +0.115
    prose  80 words (27% scaffold)   -0.043     the scaffolding RAISED the score
    prose 150 words (17% scaffold)   +0.031

Non-monotone, and it changes sign. There is no dilution law.

So the honest answer to the question I started with is **no finding** — markdown moves the lite score
by up to 0.25 on individual documents, in both directions, with no structure I could find in three
attempts. My own deployment guide at 0.144 is one document, and one document is what it took to make
each of these hypotheses look obvious.

One claim survived every attempt to break it and is the one now asserted: **no markdown form changed
a verdict.** 20 of 20 stayed above the loop threshold in all four forms, the closest at 0.3001.

Worth keeping: **the confidence ordering was exactly backwards.** The hypothesis I was most sure of
had the largest corpus behind it and was refuted by a single short paragraph; the repair I reached
for immediately was refuted by the next table. What made the difference was that each one was
written down as an assertion before being believed — the same lesson as Result 222, arriving twice
in two loops because the first time did not make me apply it earlier.

## Result 224

**The rewriter refuses German. The two surfaces that report on it did not.**

Non-English handling turned out to be mostly right: paste French, German, Spanish or Japanese and
the loop returns the text unchanged with a caveat explaining that every transform is English. No
mangling — the guard exists because English openers and an English "and" were once welded into
German and French sentences, and it works.

The reporting is where it fails. One paragraph of the same content in five languages:

    language   score   flagged   rewritten   language caveat from score_text
    english    0.7495  True      yes         n/a
    german     0.4788  True      NO          NONE
    spanish    0.2680  False     NO          NONE
    french     0.2364  False     NO          NONE
    japanese   0.0000  False     NO          present (non-Latin script)

**German comes back flagged as AI, from English-only models, with caveats attached about its length
and its tier and nothing about its language.** `untell_text` says the right thing — "any score here
is not a verdict about this text" — but `score_text` is a different public surface, reached by the
CLI's `score`, the MCP tool and the REST endpoint, and it never asked.

The second surface was worse, because the module already contained both answers:

    looks_non_english      German is not English      written for the rewriter
    _language_supported    German is supported        script-based: Korean yes, German no

and `score_tells` reported the second, so German returned `language_supported: true` with
`tells_per_100w: 0.00`. That field exists **precisely** to stop a zero being read as a clean bill of
health; the `languages` module says so in as many words, about Korean. It was doing that job for the
rarer case and failing it for the commoner one.

Worth keeping: **the tool knew. Two functions in one module, one file apart, disagreeing about the
same paragraph, and the output reported the weaker one.** Nothing here needed a new capability — the
detection was written, tested and correct. It just was not consulted by the surface that hands the
user a verdict.

### Lost to a reset

All three source edits were made, verified against the five-language probe, and then **destroyed by
a concurrent session running `git reset` while my test suite was running.** The working tree came
back at HEAD with only my untracked test file surviving. No commits were lost — `reflog` shows
`reset: moving to HEAD`, and the reset target was my own last commit.

The edits were uncommitted for about ten minutes, which is how long the regression run took. That is
the whole lesson: in this repository, a source edit that is not committed is a source edit that may
not exist by the time the tests finish. Commit before the long run, not after it.

## Result 225

**Three surfaces, two loops, one shape: the tool knows, and the thing that answers does not ask.**

Result 224 fixed `score_text` and `score_tells`. The obvious next question is whether that shape
repeats, so I built the matrix — adversarial inputs against every public surface — and the third
instance was in the module that produces the headline number.

    input       humanness   classification   undetermined_reason
    japanese         50.0   mixed            (abstained)
    german          100.0   human            "not in a script this catalogue can read"

**100.0 is the top of the scale**, produced *because* the catalogue found zero tells in text it
cannot read a word of, on the command that advertises "how human does it read". The `languages`
module names this exact failure in as many words — "a score of 0 tells means the patterns did not
apply, NOT that the text reads as human" — and `undetermined_reason` was computing the right answer
the whole time. `humanness` did not consult it.

The check was there. It was nested **inside** the too-short branch, so it could only fire for text
with fewer than five Latin words. Non-Latin scripts satisfy that by accident; Latin-script
non-English never does.

The two functions had also drifted in opposite directions, each right about the case the other got
wrong:

    humanness()            correct reason for Japanese, no abstention at all for German
    undetermined_reason()  correct for German, "shorter than 5 words" for Japanese

The second is why the order changed. `_WORD_RE` is `[A-Za-z']+`, so a Japanese paragraph counts zero
words, the length test claimed it first, and the tool reported "shorter than 5 words" about forty
characters of prose — true of the regex, absurd to the reader, and it points at the wrong fix.

### The test that failed for the wrong reason

Pinning it, I asserted a 20-point humanness gap between an English paragraph and an AI-ish one,
on the strength of a probe that had given 88.1 and 28.9 for a *different* pair I had also written.
The two in the test gave **52.8 and 47.0**. Gap 5.8. It read like the fix having broken
discrimination.

    MEASURED, 20 HC3 pairs, lite tier:
        human mean 81.7    machine mean 58.6    gap 23.1    correctly ordered 19 of 20

The tool discriminates well. My constructed pair did not. Both of my hand-written pairs were
evidence about my writing and nothing else, and the two of them disagreed by 55 points on the same
quantity.

Worth keeping: **a hand-written example is a fixture, not a sample.** It is fine for showing that a
branch fires; it cannot support a claim about how well something works, and the tell is that a
second hand-written pair gives a wildly different number. The corpus assertion that replaced it —
pair ordering rather than absolute gap — survives a change of text, which the original never could.

## Result 226

**A fourth surface, found by a sweep instead of by hand — and a red main I had left behind me.**

Results 224 and 225 fixed three surfaces that issued verdicts on text the tool cannot read, each
found one at a time. The mechanical version is a matrix: five public surfaces against seven inputs
none of them can judge.

    input         score  tells  sentences  humanize  humanness
    non-english     yes    yes       yes*      yes        yes      (* tier caveat only)
    very short      yes     --       yes       yes        yes
    code only       yes     --       yes       yes         --
    invisible       yes     --       yes       yes         --
    per-line        yes     --       yes       yes         --
    punct only      yes    yes       yes       yes        yes
    ordinary        yes     --       yes       yes         --

The first pass read every cell as `yes` or `--` and found nothing new. The finding came from
asserting something stronger than "did it warn": **did it warn about the right thing.**
`score_sentences` on a German paragraph returned per-sentence AI flags with a caveat explaining that
per-sentence targeting is near-chance on the stdlib path — true, and beside the point, since no tier
makes an English-only detector read German. Its cell said `yes` because a standing note happened to
be present.

Two blanks turned out to be correct and are recorded rather than closed:

* **`tells` is silent on short text only when there are no tells**, and that gate is deliberate:
  over 60 HC3 pairs truncated to five words the mean rate is 0.00, so caveating the common case
  would be noise that teaches readers to skip warnings. My first pass called this a gap because the
  probe text I chose happened to contain no tells — the blank was my sample, not the code.
* **`humanness` blanks are abstentions only.** It has caveats for invisibles and the weak path;
  they go to the log, because the function returns a float and has nowhere else to put them.

### The part I should have caught earlier

Running the wider suite afterwards surfaced `test_verify_carries_the_evasion_caveats` failing, and
it fails at `HEAD~1` as well — **it has been red on main since I changed `verify` to forward
`score_text`'s caveats rather than hand-pick two of them.** The test asserted
`verify(_PROSE).get("warning") is None`; `_PROSE` is 37 words and now legitimately earns the
short-text note. The code is right and the assertion was stale.

Worth keeping: **an assertion that nothing was said cannot survive a codebase that is getting better
at saying things.** `is None` was standing in for "no evasion caveat", and it broke on the first
honest improvement to the surface it guards. The same shape as the `>= before - 0.01` bound in
Result 222 — an assertion whose passing condition includes "the feature did nothing".

Also worth noting how nearly I misattributed it: `git status` showed `untell/layout.py` modified, a
concurrent session had been editing that file all session, and the failing case involved list
splitting. The file was byte-identical to HEAD — a line-ending artifact. `rtk` returned empty output
for `git diff` on it, which is the failure mode already recorded for `rtk`'s pytest summaries.
Reading the bytes in Python settled it in one call.
