# What each function returns

Every public entry point returns a plain `dict` (or a bare float), and the key that carries *the
answer* is named differently in each one. There is no way to guess them, and guessing wrong does
not raise — it produces a plausible value and a wrong conclusion.

That is not hypothetical. Three of these were misread in a single session of probing this codebase,
each time producing a confident wrong answer:

| read | actual | what it looked like |
|---|---|---|
| `result["text"]` | `result["final"]` | `.get("text") or original` silently scored the **unrewritten input**; an hour of measurement produced numbers for text that had never been rewritten |
| `result["scores"]` | `result["detectors"]` | an empty dict, read as "no detectors ran" |
| `entry["score"]` | `entry["ai"]` | `None` for all 40 sentences → "AUROC=None, matched 0/40", which looks exactly like a broken scorer |

Generated from live calls, not from reading the source.

## The answer key, per function

| function | returns | the key you want |
|---|---|---|
| `untell.scripts.run.untell_text` | `dict` | **`final`** — the rewritten text. There is no `text` key. |
| `untell.scripts.score.score_text` | `dict` | **`max`** — highest P(AI) across detectors. Per-detector values are under **`detectors`**, not `scores`. |
| `untell.scripts.sentences.score_sentences` | `dict` | **`sentences`**, each entry `{text, ai, flagged}`. The probability is **`ai`**, not `score`. `warning` and `unrankable` appear only when the ranking cannot be trusted — `unrankable` when this document's own per-sentence scores span less than 0.05, which happens when a detector is at its ceiling on every sentence. |
| `untell.scripts.tells.score_tells` | `dict` | **`tells_per_100w`**, with the breakdown under `by_category` |
| `untell.scripts.verify.verify` | `dict` | **`passes_all`**, per-detector detail under `results` |
| `untell.humanness.humanness` | `float` | the score itself, 0–100 |
| `untell.scripts.quality.similarity` | `float` | the score itself, 0–1 |

## Full key lists

```
score_text        ai_percent, detector_modes, detectors, flagged, max, mean, threshold,
                  tier, tier_requested, verdict_threshold, warning
                  + failed_detectors and detector_errors, only when a detector raised

score_tells       burstiness_cv, by_category, by_evidence, language_supported,
                  low_burstiness, tells, tells_per_100w, words, warning (only when a caveat applies)

score_sentences   flagged, note, sentences, threshold, tier,
                  unrankable (only when the per-sentence scores cannot be ranked),
                  warning (only when a caveat applies)

untell_text       adopted, changed, final, flagged, iterations, meaning_gate, post, pre,
                  quality_metric, rewriter, rewrites, seed, sim_bar, similarity, stopped,
                  tells_after, tells_before, tier, warning (only when a caveat applies)

                  pre                 the score_text keys above, for the input
                  post                the score_text keys above, plus
                                      flagged_sentences, style

verify            configured, n_configured, n_passing, passes_all, results, threshold,
                  warning (only when a caveat applies)
                  each row of `results` carries ai, passes, verdict_threshold
```

## Three that are easy to misread even with the right key

- **`tier` is not `tier_requested`.** `score_text` reports the tier that actually produced numbers.
  Ask for `full` on a broken ML stack and you get `tier: "lite"` with a `warning` — the honest
  answer, and not the one a caller who only reads `tier_requested` will see.
- **`flagged` is decided by `verdict_threshold`, not `threshold`.** `threshold` is what the rewrite
  loop optimises toward; the verdict bar is calibrated separately, because reusing one number made
  the lite tier flag 60% of genuinely human text.
- **`language_supported: false` means the counts are not evidence.** The catalogue is English-only,
  so on mostly-non-Latin text `tells: 0` means nothing was looked for, not that nothing was found.

## Why these are not simply renamed

Renaming would break every caller — the REST API, the MCP server, the skill, and anyone's script —
to fix a documentation problem. The names are pinned by tests instead
(`tests/test_run.py`, `tests/test_sentences.py`, `tests/test_api_server.py`), each asserting both
that the documented key exists *and* that the confusable alternative does not, so a future rename
that introduces `score` alongside `ai` fails rather than quietly doubling the vocabulary.
