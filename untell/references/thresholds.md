# Thresholds & loop defaults

These are the knobs the `untell` loop uses. Override per-run if the user asks.

| Parameter | Default | Meaning | Rationale |
|---|---|---|---|
| `threshold` | `0.30` | Stop when the **max** detector P(AI) drops below this — and the bar `flagged` reports against. | Measured on 40 labelled HC3 pairs: catches 100% of AI at every value tested, and reports 5% (lite) / 12% (full) of *human* documents as AI. See "What each threshold actually costs" below — 0.40 is the better pure-detection bar; 0.30 is kept because it is also the loop's stop target. |
| `similarity bar` | `0.88` BERTScore / `0.76` embedding / `0.50` token-overlap | A rewrite is only acceptable if similarity to the original stays ≥ this. **Metric-aware** — the three metrics live on different scales. | `0.76` is the P-SP threshold (semantic embeddings). `0.88` is the BERTScore-F1 bar (rescaled with baseline), used when `bert-score` is installed — its recall term catches dropped claims a single cosine averages away. The lite token-overlap fallback scores faithful paraphrases far lower, so it uses `0.50` and is treated as *advisory* (`confidence: low`) — it cannot actually judge meaning. `quality.py` reports the right bar + `passes`; trust those, never a remembered number. |
| `meaning gate` (NLI) | contradiction `< 0.50`, entailment `≥ 0.005` | A rewrite is rejected outright if it contradicts the original or fails to entail it, **regardless of similarity or detector score**. | Similarity cannot separate a faithful reword from a reversal: "runs faster" → "runs slower" scores `0.974` cosine, far above the `0.76` bar, while genuinely faithful register shifts score lower. Entailment separates them — that same inversion scores `0.998` contradiction. Run `scripts/entailment.py` (exit `0` preserved, `1` rejected), then `scripts/roles.py` for the predicate-argument veto — a swap like "the cache invalidated the request" → "the request invalidated the cache" passes similarity (0.994) *and* entailment (0.988) and is caught only there. Unavailable without the `.[full]` extra, in which case both are skipped, not failed. |
| `quantity check` | every numeral must survive | A rewrite is rejected if a number the source stated is gone — as a numeral or its English word. | `preserve.py` deliberately leaves bare single digits unlocked so "5" can become "five", which changes nothing. That also lets a precise quantity slide into vagueness, and NLI does not object: "Only 7 of the 19 tests passed." → "Only a few of the 19..." scores contradiction `0.011`, entailment `0.007` — clearing the floor by `0.002`. Run `scripts/numerals.py` (exit `0` kept, `1` dropped). |
| `certainty check` | no hedge class dropped, no claim added | A rewrite is rejected if it states more firmly than the source: a dropped hedge, an association reported as causation, or an intensifier the source never used. | Seven of ten such strengthenings cleared similarity + NLI + roles, because none *contradicts* the source: "may cause" → "causes", "suggest" → "prove", "usually" → "always", "fell slightly" → "collapsed", "is correlated with" → "causes". Six classes plus `causal_upgrade` and `intensifier_added`. Swapping one hedge for another is fine; adding a *minimizer* is fine too, since a more cautious rewrite is not a fidelity failure. Run `scripts/hedges.py`. |
| `relaxed sim bar` | `0.30`, **only when the meaning gate ran** | When entailment + roles are doing the meaning check, similarity drops to a drift floor. | The strict bar rejects **6 of 8 faithful** rewrites — heavy rewording is what humanizing *is*. Relaxing the floor and adding the two gates admitted 7 of 8 faithful and **0 of 11 bad** rewrites: more permissive *and* strictly safer. Without the gates the strict bar applies, since loosening it exactly when the checks that catch bad rewrites are missing would be pure risk. `meaning_preserved()` implements this; the skill mirrors it. |
| `max iterations` | `5` | Hard cap on rewrite rounds. | The closed-loop evasion literature (arXiv 2506.07001) converges within ~3–5 iterations; more rounds risk meaning drift for little gain. |
| aggregation | `max` | Which detector score the stop condition uses. | Targeting the hardest detector forces genuine multi-detector evasion (report gap #3), not just fooling the weakest one. Correct as a *stop target*; it is the worst choice as a *verdict* — see below. |

## What each threshold actually costs

`threshold` does two jobs: it is the loop's **stop target**, and it is the bar `flagged` reports a
verdict against. Measured on 40 labelled HC3 human/AI pairs, after the detector recalibration:

> ⚠️ **The false-positive columns below are substantially understated — re-measured 2026-08-11.**
> At the default 0.30 this table says 5% (lite) / 12% (full) of human documents flag. Measured
> again:
>
> | | this table | re-measured |
> |---|---|---|
> | lite, stdlib path | 5% | **52%** (21/40 human HC3 texts) |
> | full tier | 12% | **40–42%** at natural document length |
>
> The lite figure depends on which sub-path runs: `perplexity_burstiness` silently upgrades to
> GPT-2 when `torch` is importable, and the two are not close — **5% FPR on the GPT-2 path against
> 52% on the stdlib one**, which is what a clean install gets. One tier name, two calibrations.
>
> The full-tier figure is driven by `mage`, which flags 33% of human text on its own via `max`
> aggregation — and that 33% is itself HC3-specific (0% on RAID, 3.3% on MAGE). Every number in
> this section is an HC3 number.
>
> **Also missing from this document:** the reported verdict does not always use `threshold`. On the
> stdlib lite path it uses a calibrated `verdict_threshold` of **0.45**, while the loop keeps
> optimising against 0.30 so stronger rewriting is not traded for a kinder verdict. `score_text`
> publishes both. That cut takes stdlib human false positives from 52% to 18%, and it is the
> single most important number here for whether a human gets accused.
>
> The original rows are left in place rather than overwritten: they were measured, and replacing
> them silently would repeat the mistake this note exists to flag.


| threshold | lite FPR | lite TPR | full FPR | full TPR |
|---|---|---|---|---|
| 0.15 | 35% | 100% | 45% | 100% |
| 0.20 | 18% | 100% | 30% | 100% |
| 0.25 | 12% | 100% | 20% | 100% |
| **0.30 (default)** | **5%** | **100%** | **12%** | **100%** |
| 0.35 | 0% | 100% | 5% | 100% |
| 0.40 | 0% | 100% | **0%** | **100%** |
| 0.50 | 0% | 95% | 0% | 100% |

FPR is the fraction of **human-written** documents reported as AI. Every value from 0.40 up catches
100% of the AI samples on both tiers, so as a *detection* bar 0.40 is strictly better than the
default: it removes the remaining false positives at no cost in recall on this corpus.

The default stays at 0.30 because it is also the loop's stop target, and a lower target makes the
loop work harder against detectors this corpus does not contain — including whatever a real
commercial checker does. Use `--margin` to push further below the bar rather than lowering the bar
itself, and read `flagged` at 0.30 knowing roughly one human document in ten will trip it on the
full tier.

## `max` is a stop target, not a verdict

Every false positive this project has measured traces to the same place: `max` means one detector
saying "AI" about human writing decides the answer. Measured on 30 labelled HC3 pairs, full tier,
threshold 0.30 — the identical per-detector scores, aggregated five ways:

| aggregation | human mean | FPR | ai mean | TPR | AUROC |
|---|---|---|---|---|---|
| **`max` (shipped)** | 0.166 | **13%** | 0.999 | 100% | 1.000 |
| 2nd-highest | 0.064 | 0% | 0.981 | 100% | 1.000 |
| mean | 0.059 | 0% | 0.819 | 100% | 1.000 |
| median | 0.034 | 0% | 0.842 | 100% | 1.000 |
| at least 2 of N over threshold | 0.000 | 0% | 1.000 | 100% | 1.000 |

`max` is the only one that produces false positives, and it buys no extra recall — every option
catches 100% of the AI samples.

It stays, because for the **loop** it is the right rule: driving `max` under the threshold means
every detector has been beaten, while a mean would let the loop stop with one detector still
flagging. That is the whole point of the multi-detector bar.

The cost lands on the **verdict**. When reading `flagged` or `ai_percent` for a document you did not
generate — deciding whether text *is* AI rather than whether a rewrite is done — read the
`detectors` map, not `max` alone. One high score among four low ones is a disagreeing detector, not
a consensus.

## Tuning guidance

- **Stricter evasion:** lower `threshold` to `0.15–0.20`. Expect more iterations and more pressure
  on similarity — watch the quality gate. Note the table above: at 0.15 the *verdict* becomes
  noisy, flagging 35–45% of genuinely human text, so treat `flagged` as a rewrite trigger at these
  settings and not as an opinion about authorship.
- **Tighter meaning preservation:** install the `.[full]` extra so the NLI meaning gate runs —
  that is the lever that actually catches reversals, and it costs no evasion strength because it
  rejects only rewrites that changed the claim. Raising the `similarity bar` to `0.80+` is the
  blunter knob: it also rejects faithful rewrites that merely reword heavily, so fewer aggressive
  rewrites pass and the loop may stop while still mildly flagged.
- **Quick demo:** raise `threshold` to `0.50` and cap iterations at `3`.

## Reading the score JSON

`untell-score` / `score.py` emit:

- `tier` — `lite` (heuristic, weak), `full` (RoBERTa-OpenAI + HC3-RoBERTa + Fast-DetectGPT + GPT-2
  perplexity; MAGE when its config loads — real CPU signal), or `heavy` (adds Binoculars, GPU).
  Always report which tier ran.
- `detectors` — per-detector P(AI); use these to decide *what* to change in the rewrite.
- `max` / `mean` — aggregate proxies; the loop drives `max`.
- `flagged` — `true` when `max >= threshold` (keep rewriting).
