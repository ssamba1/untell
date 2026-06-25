---
name: humanize
description: >-
  Humanize AI-generated text via a closed-loop, detector-feedback rewrite. Use when the user
  wants to humanize text, make writing sound more human, reduce AI-detection scores, bypass or
  beat an AI detector (GPTZero, Turnitin, Originality, ZeroGPT), or lower the "AI probability"
  of a passage or file. Research/defensive tool — preserves meaning, citations, and facts.
---

# humanize

Rewrite text so a local ensemble of AI-text detectors stops flagging it, while semantic meaning
and all citations/numbers/quotes stay intact. The core technique is a **closed loop**: score →
rewrite using the per-detector scores as feedback → re-score, repeating until the hardest
detector is under threshold or the iteration cap is hit. You (Claude) are the rewriter; the
local scripts only score and protect text.

> **Research / defensive use.** Detectors are noisy proxies (non-native writers are falsely
> flagged at high rates); these local detectors are *signals*, not ground truth. Do not present
> output as guaranteed undetectable by any commercial system. State this if the user implies a
> high-stakes deceptive use.

## When to run

Trigger on requests like "humanize this", "make this sound less like AI", "reduce the AI score",
"help this pass an AI detector". Input is either pasted text or a file path.

## Setup (once per session)

All commands run from the skill directory. The scripts work with **zero dependencies** (lite
tier). For stronger detector signal, the user may `pip install -e ".[full]"` — the scripts
auto-detect and use it; you don't change anything.

## The loop

Defaults live in `references/thresholds.md` (threshold `0.30`, similarity bar `0.76`, max `5`
iterations). Load `references/prompt-rubric.md` before your first rewrite.

1. **Read the input.** If given a file path, read it. Keep the original text verbatim as `ORIG`.

2. **Preserve-lock.** Protect citations, numbers, quotes, URLs, and named entities so your
   rewrite cannot alter them:
   ```bash
   python -m humanize.scripts.preserve "<ORIG>"
   ```
   This returns `{"masked": ..., "mapping": ...}`. Work on `masked`. The sentinels look like
   `⟦HZ0003⟧` — **never modify, translate, split, or drop a sentinel**; carry each one through
   every rewrite exactly as-is.

3. **Score the current text** (start with the masked original):
   ```bash
   python -m humanize.scripts.score "<current masked text>" --threshold 0.30
   ```
   Read the JSON: `detectors` (per-detector P(AI)), `max` (the proxy you must push down),
   `flagged` (true ⇒ keep going), and `tier` (which detectors actually ran).

4. **Check the stop condition.** Score similarity:
   ```bash
   python -m humanize.scripts.quality "<ORIG masked>" "<current masked text>"
   ```
   This returns `similarity`, `method`, `confidence`, `bar`, and `passes` (the bar is
   metric-aware — `0.76` for semantic embeddings, `0.50` for the lite token-overlap fallback).
   Stop when **both** hold:
   - `max < threshold` (not flagged), **and**
   - the quality check `passes` is `true`.

   **Confidence matters:** when `confidence` is `high` (full tier, embedding metric), enforce the
   quality gate strictly — never accept a rewrite where `passes` is false. When `confidence` is
   `low` (lite tier, token-overlap), the gate is **advisory only**: token-overlap cannot judge
   meaning, so do not loop endlessly chasing it — rely on your own judgment that meaning is intact,
   report the similarity, and flag in the final note that quality was not reliably gated (full tier
   recommended). Also stop if you have reached the iteration cap (default 5).

5. **Rewrite with feedback** (if not stopping). Apply `references/prompt-rubric.md`. Use the
   per-detector scores to decide *what* to change:
   - High `perplexity_burstiness` ⇒ vary sentence length aggressively (mix very short with long,
     winding sentences); replace predictable phrasing with less expected word choices.
   - High supervised scores (`roberta_openai`, `mage`) ⇒ break uniform structure, vary openings,
     add concrete specifics, remove formulaic transitions ("Moreover", "Furthermore", "Overall").
   Preserve meaning and **every sentinel**. Produce the new masked text, then go to step 3.

6. **Restore + report.** Once stopped, restore the protected spans:
   ```bash
   python -m humanize.scripts.preserve  # (use restore: see note below)
   ```
   Substitute each sentinel back to its original (the `mapping` from step 2) to get the final
   text. Then present:
   - The final humanized text.
   - A **before/after table**: each detector's P(AI) at iteration 0 vs final, the `max` proxy,
     final similarity, and the number of iterations used.
   - A one-line honest caveat (local proxies, not commercial ground truth).

> **Restoring sentinels:** the mapping from step 2 is `sentinel -> original`. Replace each
> `⟦HZxxxx⟧` in your final text with its mapped value. (Programmatically:
> `from humanize.scripts.preserve import restore; restore(text, mapping)`.)

## Stop conditions (summary)

- ✅ `max < threshold` **and** quality `passes` → success, restore and report.
- 🔁 still `flagged` and under the iteration cap → rewrite again with feedback.
- ⚠️ hit the iteration cap while still flagged → report best attempt, its scores, and that the
  cap was reached (do not silently claim success).
- ⚠️ a rewrite drops the quality gate (high confidence) → revert that rewrite and try a gentler
  change. On low-confidence (lite) the gate is advisory — judge meaning yourself, do not loop on it.

## Notes

- The loop targets the **max** across detectors, not the average — a rewrite only wins when the
  *hardest* detector is satisfied (multi-detector evasion).
- If `tier` is `lite`, say so in the report: the lite heuristic is a weak demo signal, not a real
  evasion guarantee. Recommend `pip install -e ".[full]"` for a meaningful score.
