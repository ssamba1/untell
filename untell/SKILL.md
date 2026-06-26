---
name: untell
description: >-
  Humanize AI-generated text via a closed-loop, detector-feedback rewrite (the "untell" skill).
  Use when the user wants to humanize text, make writing sound more human or less like AI, reduce
  AI-detection scores, bypass or beat an AI detector (GPTZero, Turnitin, Originality, ZeroGPT), or
  lower the "AI probability" of a passage or file. Research/defensive tool — preserves meaning,
  citations, and facts.
---

# untell

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

Run all commands **from the skill directory** (the folder that contains this `SKILL.md`); the
`python scripts/<name>.py` paths below are relative to it. The scripts work with **zero
dependencies** (lite tier) and self-resolve their own package, so no `pip install` or
`PYTHONPATH` is needed. For stronger detector signal, the user may `pip install -e ".[full]"` —
the scripts auto-detect and use it; you don't change anything. (If `pip install`ed, the
`untell-score` / `untell-sentences` / `untell-verify` console commands also work from any cwd.)

**Pick the right Python interpreter.** The full detector tier needs `torch`/`transformers` in the
interpreter you invoke. Commands run from the skill directory, so resolve the interpreter to an
**absolute path** and use it for every `python scripts/*.py` call below. Choose, in order:
1. `$UNTELL_PYTHON` if set — the reliable override; point it at a venv that has `.[full]` installed;
2. a virtualenv in the **user's project directory** (where they invoked `/untell` — *not* the skill
   dir): `<project>/.venv/Scripts/python.exe` (Windows) or `<project>/.venv/bin/python` (macOS/Linux);
   likewise `<project>/venv/...`;
3. otherwise plain `python`.

A bare `python` is often a system/conda base whose ML stack is broken (e.g. a NumPy 2.x ↔ torch
mismatch), which silently drops you to the weak **lite** tier. The scripts report this honestly: if
`score` returns `"tier": "lite"` with a `warning` / `failed_detectors` when you wanted full, that
interpreter lacks a working ML stack — re-run with a venv python that has `.[full]` (README
"Troubleshooting"), and tell the user the detectors were **excluded**, not silently faked at 0.5.

## The loop

Defaults live in `references/thresholds.md` (threshold `0.30`, similarity bar `0.76`, max `5`
iterations). Load `references/prompt-rubric.md` before your first rewrite.

1. **Read the input.** If given a file path, read it. Keep the original text verbatim as `ORIG`.

2. **Preserve-lock.** Protect citations, numbers, quotes, URLs, and named entities so your
   rewrite cannot alter them:
   ```bash
   python scripts/preserve.py "<ORIG>"
   ```
   This returns `{"masked": ..., "mapping": ...}`. Work on `masked`. The sentinels look like
   `⟦HZ0003⟧` — **never modify, translate, split, or drop a sentinel**; carry each one through
   every rewrite exactly as-is.

3. **Score the current text — score the RESTORED text, never the masked one.** The `⟦HZ⟧`
   sentinels are out-of-distribution tokens that *artificially lower* detector scores, so the loop
   would under-read the AI signal and can stop too early on text that is still flagged. Restore the
   sentinels back to real prose first, then score that copy (keep rewriting the masked version):
   ```bash
   python scripts/preserve.py --restore --mapping '<mapping json from step 2>' "<current masked text>" > /tmp/untell_scoring.txt
   python scripts/score.py "$(cat /tmp/untell_scoring.txt)" --threshold 0.30
   ```
   Read the JSON: `detectors` (per-detector P(AI)), `max` (the proxy you must push down),
   `flagged` (true ⇒ keep going), `tier`, and any `warning`/`failed_detectors` (say so honestly).

4. **Check the stop condition.** Score similarity:
   ```bash
   python scripts/quality.py "<ORIG masked>" "<current masked text>"
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

4b. **Target the flagged sentences.** Find which sentences read as AI, so you rewrite *those* the
   hardest instead of re-rolling everything (far fewer iterations, less drift):
   ```bash
   python scripts/sentences.py "<current masked text>" --threshold 0.30
   ```
   Each line shows `[AI 0.xx]` or `[ok 0.xx]` per sentence. Focus your next rewrite on the `AI` ones.

5. **Rewrite with feedback** (if not stopping). Apply `references/prompt-rubric.md`. Use the
   per-detector scores AND the flagged sentences from step 4b to decide *what* to change:
   - High `perplexity_burstiness` ⇒ vary sentence length aggressively (mix very short with long,
     winding sentences); replace predictable phrasing with less expected word choices.
   - High supervised scores (`roberta_openai`, `mage`) ⇒ break uniform structure, vary openings,
     add concrete specifics, remove formulaic transitions ("Moreover", "Furthermore", "Overall").
   Preserve meaning and **every sentinel**. Produce the new masked text. **Before continuing, verify
   every sentinel from step 2 still appears in the new text** — if any `⟦HZxxxx⟧` is missing you dropped
   a locked span (a citation, number, quote, or fact); redo the rewrite to put it back. Then go to step 3.

6. **Restore + report.** Once stopped, restore the protected spans — substitute each sentinel
   back to its original using the `mapping` from step 2:
   ```bash
   python scripts/preserve.py --restore --mapping '<mapping json from step 2>' "<final masked text>"
   ```
   (or `--mapping-file path.json`). This prints the final text with every `⟦HZxxxx⟧` replaced.
   Then present:
   - The final humanized text.
   - A **before/after table**: each detector's P(AI) at iteration 0 vs final, the `max` proxy,
     final similarity, and the number of iterations used.
   - **A loud, honest caveat (do not soften this).** These are *local proxy* detectors and they do
     **not** predict commercial ones. **GPTZero / Originality / Turnitin can still rate this output
     100% AI** even when the local `max` is low — GPTZero ships dedicated anti-humanizer ("AI
     Paraphrasing") detection that flags AI-rewritten text. A low local score means "passed the weak
     local proxies," NOT "undetectable." To actually optimize against a real checker, the user must
     run `--tier commercial` with that detector's API key (e.g. `GPTZERO_API_KEY`) so the real
     detector is in the loop (costs credits). Never claim this output will pass GPTZero/Turnitin
     unless it was verified against the real thing.

> **Restoring sentinels:** the mapping from step 2 is `sentinel -> original`. Replace each
> `⟦HZxxxx⟧` in your final text with its mapped value. (Programmatically:
> `from untell.scripts.preserve import restore; restore(text, mapping)`.)

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

### Critical: do NOT optimize the prose into a "humanizer voice" to chase a low score

The local detectors are flawed proxies that **reward AI tells and penalize plain human writing** —
they are *anti-correlated* with how human the text actually reads. Measured directly: a plain,
natural rewrite scored ~99% AI locally, while an em-dash-laden, theatrically "varied" rewrite of the
same text scored ~27% — yet the em-dash one was the one that read as AI to a person and came back
**100% AI on GPTZero**. The loop, left to chase the number, drives the text *toward* the tells.

So:

- **Follow the rubric and write the way a real person would.** If a *more natural* phrasing scores
  *higher* locally, keep the natural one anyway. Naturalness wins over the local number.
- **Treat the local score as a weak hint, not the objective.** These proxies do not predict
  GPTZero / Turnitin / Originality. Stop when meaning is intact and the text genuinely reads like a
  person wrote it — even if a local detector is still elevated. Don't grind out extra iterations that
  make the prose worse just to lower a number that doesn't mean what it claims.
- **Be honest in the report:** state that local proxies ≠ commercial detectors, and that a low local
  score is not a promise the text passes GPTZero (measured: it often does not).
