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
iterations). Load `references/prompt-rubric.md` **and** `references/ai-tells.md` before your first
rewrite — `ai-tells.md` is the full catalog of patterns the output must never contain.

1. **Read the input.** If given a file path, read it.

1b. **Scrub hidden characters — do this BEFORE locking, not after.** AI text can carry zero-width,
   tag, bidi and homoglyph characters that identify its origin regardless of how well it reads:
   ```bash
   python scripts/scrub.py --json "<raw input>"
   ```
   Reports `hidden_before`, `hidden_after`, `changed`, and the cleaned `text`. **Use that cleaned
   text as `ORIG` from here on** — everything downstream works from it.

   These characters carry no meaning, so nothing in a rewrite has any reason to remove them: they
   survive every paraphrase untouched. And the order is load-bearing — locking first would capture
   any hidden characters sitting inside a locked citation or quote into the mapping, and step 6's
   restore would put them straight back into the finished text. The headless loop scrubs before
   `lock()` for exactly this reason. If `changed` is `true`, say so in the final report: the user
   should know their source was watermarked.

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
   python scripts/preserve.py --restore --mapping '<mapping json from step 2>' "<current masked text>" | python scripts/score.py --threshold 0.30
   ```
   `score.py` reads stdin, so pipe straight into it — no temp file. (This step used to write to
   `/tmp/untell_scoring.txt` and read it back with `$(cat ...)`. That works under bash — including
   Git Bash on Windows, which provides `/tmp` — but not in PowerShell, where `/tmp` does not
   exist; step 1 of this same skill already branches on Windows for the interpreter path. The pipe
   needs no temp file, so it also cannot leave a stale scoring file behind between iterations.)
   Read the JSON: `detectors` (per-detector P(AI)), `max` (the proxy you must push down),
   `flagged` (true ⇒ keep going), `tier`, and any `warning`/`failed_detectors` (say so honestly).

4. **Check the stop condition.** Score similarity:
   ```bash
   python scripts/quality.py "<ORIG masked>" "<current masked text>"
   ```
   This returns `similarity`, `method`, `confidence`, `bar`, and `passes` (the bar is
   metric-aware — `0.88` for BERTScore, `0.76` for semantic embeddings, `0.50` for the lite
   token-overlap fallback; each metric lives on its own scale, so compare `similarity` to the
   returned `bar`, never to a bar you remember).

   **Which similarity bar applies depends on whether the meaning gate below is available**, and
   this mirrors what the headless loop does in `meaning_preserved()`:
   - **Meaning gate available** → similarity is only a *drift floor*: require `similarity >= 0.30`
     and let entailment + roles decide. The strict bar was measured to reject **6 of 8 faithful**
     rewrites — heavy rewording is what humanizing *is*, and scoring it as meaning loss stalls the
     loop. Relaxing the floor while adding the NLI and role gates admitted 7 of 8 faithful rewrites
     and **0 of 11 bad** ones: simultaneously more permissive and strictly safer.
   - **Meaning gate unavailable** → fall back to the strict `passes` from `quality.py`. There is
     nothing else to lean on, and loosening the bar precisely when the checks that would catch a
     bad rewrite are missing would be pure risk.

   Then run the **meaning gate** — similarity alone is not sufficient and must not be your only
   check:
   ```bash
   python scripts/entailment.py "<ORIG masked>" "<current masked text>"
   ```
   Exit `0` = meaning preserved, `1` = rejected. Cosine similarity was measured to score a direct
   inversion ("runs faster" → "runs slower") at **0.974**, sailing past the 0.76 bar, while
   rejecting faithful register shifts that merely reword heavily. Entailment separates the two:
   the same inversion scores contradiction `0.998` and is rejected. **Discard any rewrite this
   step rejects, no matter how good its detector score is** — a lower AI score bought with
   altered meaning is not a win. If `available` is `false` (no `.[full]` extra) the check is
   skipped and you fall back to similarity plus your own reading.

   Then the **predicate-argument check**, which catches what the other two cannot:
   ```bash
   python scripts/roles.py "<ORIG masked>" "<current masked text>"
   ```
   Exit `0` = roles intact, `1` = the rewrite swapped who did what to whom. Measured on
   "The cache invalidated the request." → "The request invalidated the cache.": similarity
   `0.994`, entailment `0.988`, contradiction `0.005` — **both earlier gates pass it**, because
   every word is still there and the sentence still entails itself in aggregate. Only this check
   rejects it. A swap of two arguments is the cheapest way for a rewrite to look faithful and
   assert the opposite. Passive voice is not a swap and is not flagged.

   Finally the **quantity check**, which is mechanical rather than semantic:
   ```bash
   python scripts/numbers.py "<ORIG masked>" "<current masked text>"
   ```
   Exit `0` = every number survived, `1` = one was dropped; `missing` lists them. Step 2 does not
   lock bare single digits on purpose, so that "5" can become "five" — but that also lets a precise
   quantity slide into vagueness. Measured: "Only 7 of the 19 tests passed." → "Only a few of the
   19 tests passed." scores similarity `0.951`, contradiction `0.011`, entailment `0.007`, and
   clears the meaning gate by `0.002`. Spelling a number out is fine; dropping it is not.

   The four gates are complementary, not redundant: similarity catches drift, entailment catches
   negation and reversal of a claim, roles catches argument permutation, numbers catches a
   quantity quietly becoming vague. Run all four.

   Stop when **all** hold:
   - `max < threshold` (not flagged), **and**
   - similarity clears the bar that applies (drift floor `0.30` when the meaning gate ran, else
     the strict `passes` from `quality.py`), **and**
   - the meaning gate exits `0` (or is unavailable), **and**
   - the predicate-argument check exits `0` (or is unavailable), **and**
   - the quantity check exits `0`.

   **Confidence matters:** when `confidence` is `high` (full tier, semantic metric) **and the
   meaning gate did not run**, enforce the quality gate strictly — never accept a rewrite where
   `passes` is false. When the meaning gate *did* run, entailment and roles are the authority and
   similarity is the drift floor above; a `passes: false` with both gates clear is a heavy reword,
   which is the goal, not a failure. When `confidence` is
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

5. **Rewrite with feedback** (if not stopping). Apply `references/prompt-rubric.md` and inject NONE of
   the tells in `references/ai-tells.md` (em-dashes, AI vocabulary, tricolons, negated contrast,
   formulaic transitions, inflated copula, …). Use the per-detector scores AND the flagged sentences
   from step 4b to decide *what* to change — but always fix toward **plainer, naturally uneven human
   prose**, never by gaming a score:
   - High `perplexity_burstiness` ⇒ the rhythm/word choice is too uniform. Rewrite into ordinary,
     unevenly-paced prose with plain words. Do NOT engineer a staccato-fragment-plus-winding-clause
     cadence or reach for fancier words — both are humanizer fingerprints detectors are trained on.
   - High supervised scores (`roberta_openai`, `mage`) ⇒ break uniform structure and vary openings;
     remove formulaic transitions ("Moreover", "Furthermore", "Overall"). Don't add facts the source
     didn't state.
   Preserve meaning and **every sentinel**. Produce the new masked text. **Before continuing, verify
   every sentinel from step 2 still appears in the new text** — if any `⟦HZxxxx⟧` is missing you dropped
   a locked span (a citation, number, quote, or fact); redo the rewrite to put it back. Then go to step 3.

   **5b. Write 3 genuinely different drafts, score each, keep the best.** This is the single
   highest-leverage step in the whole loop — measured, it is worth more than any individual rewriting
   technique. Selecting among 3 drafts (instead of committing to the first) is most of what took the
   local ensemble's mean max P(AI) from 0.86 to **0.21**, and dropped the content/genre detector —
   previously believed immovable — from 0.73 to **0.02** (`docs/free-ceiling-measured.md`).

   Make the drafts *actually different* (different sentence order, different level of detail, a
   different opening move) rather than three near-copies; near-copies score near-identically and waste
   the step. Score each with step 3, then pick among the drafts **that hold the meaning gate** — and
   if none beats the current text, **keep the current text**. A rewrite that doesn't improve anything
   still costs meaning fidelity, so an unimproved draft is worse than no rewrite at all.

   **Do not simply take the lowest `max`.** Differences under **0.02** are detector noise, not
   signal, and the headless loop treats them as ties for exactly that reason. Among the drafts within
   0.02 of the best `max`, prefer, in order: **fewest AI tells** (`scripts/tells.py`), then lowest
   ensemble **`mean`**, then lowest `max` as the final tiebreak. A draft that also pushes the other
   detectors down is genuinely better even when `max` is unchanged — `max` alone is blind to that —
   and picking the marginally-lower-`max` draft that reads more like AI trades a real gain for a
   rounding error.

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
