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
score_text        agreement, ai_percent, detector_modes, detectors, flagged, max, mean,
                  threshold, tier, tier_requested, verdict_threshold, warning
                  + failed_detectors and detector_errors, only when a detector raised
                  + scored, only when NOTHING could be scored (it is False; the CLI exits 2 on it)
                  + out_of_range_detectors, only when a detector returned a value outside [0, 1]

score_tells       burstiness_cv, by_category, by_evidence, language_supported,
                  low_burstiness, tells, tells_per_100w, words, warning (only when a caveat applies),
                  human_base_rate_note (only when a fired tell is common in human writing),
                  matches (only when called with matches=True)

score_sentences   flagged, note, sentences, threshold, tier,
                  unrankable (only when the per-sentence scores cannot be ranked),
                  warning (only when a caveat applies),
                  evidence_note (only when called with evidence=True)

untell_text       adopted, changed, final, flagged, iterations, meaning_gate, post, pre,
                  quality_metric, rewriter, rewrites, seed, sim_bar, similarity, stopped,
                  tells_after, tells_before, tier, warning (only when a caveat applies),
                  inspect (only when inspect=True / --inspect),
                  timings (only when timings=True / --timings),
                  voice_warning (only when a voice sample was given and is thin),
                  rewriter_warning (only when the requested rewriter was substituted),
                  error (INSTEAD of a rewrite, when no rewriter is available; `final` is the input)

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
- **`agreement` carries the two verdicts `flagged` does not.** `flagged` is the *union* rule: it is
  true when **any** detector clears the threshold. `agreement` reports that alongside `majority` and
  `unanimous`, with `detectors_scoring` and `detectors_flagging` behind them. The rule matters more
  than the detector: scoring abstracts with three tools, [Pratama](https://doi.org/10.7717/peerj-cs.2953)
  measured a false-accusation rate of **44.44%** under the union rule against **4.17%** under
  majority, and [Hyatt et al.](https://doi.org/10.1152/advan.00235.2024) took four detectors from
  1.3% individually to **near 0%** by requiring agreement. `degenerate` is true when only one
  detector scored, where all three rules are the same number and none of them means agreement.
  Absent entirely when nothing scored.

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
