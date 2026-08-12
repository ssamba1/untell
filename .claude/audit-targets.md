# Audit targets

One target per pass. `audit_next.py` picks it for you — do not choose.

Before calling anything, confirm the signature so you do not waste a turn guessing:

```python
import inspect, importlib
m = importlib.import_module("untell.scripts.preserve")
print(inspect.signature(m.lock))
```

Every recipe below is: **PROBE** (what to run) → **INVARIANT** (what must hold) →
**PRIOR** (what this component did wrong before, so you know the failure shape).

---

## T01 — preserve locks drop part of a fact

FILE `untell/scripts/preserve.py` — `lock`, `restore`, `find_sentinels`

PROBE Build a list of at least 25 fact strings, one per type: negative number (`-15`),
percentage (`5%`), currency (`$1,200`), decimal (`3.14`), year (`1998`), date (`March 3, 2024`),
range (`10–20`), fraction (`2/3`), ordinal (`4th`), scientific (`1.2e-9`), unit (`15 kg`),
version (`v2.1.0`), hex (`0xFF`), dotted identifier (`np.float64`), URL, email, DOI, ISBN,
citation (`(Smith, 2019)`), quoted span, proper noun, acronym, time (`14:30`), phone,
temperature (`-40°C`). Embed each in a sentence. `lock` it, then check the locked text.

INVARIANT For every fact, the ENTIRE fact is inside a sentinel — not a prefix of it.
Print, per fact: the fact, whether a sentinel covers it, and the exact substring covered.
`-15` covered as `15` is a FAILURE, not a pass.

PRIOR 11 of 28 fact types were unprotected and 7 more were PARTIAL — locked in a way that
looked locked and silently dropped the sign or the unit. Note the round-trip test
`restore(*lock(t)) == t` cannot detect this: unlocked text passes through unchanged, so the
property holds either way. Do not rely on it.

---

## T02 — hidden-character carriers pass through

FILE `untell/scripts/scrub.py` — `scrub_hidden`, `count_hidden`

PROBE Feed every invisible/watermark class, one per test string: ZWSP U+200B, ZWNJ U+200C,
ZWJ U+200D, word joiner U+2060, BOM U+FEFF, soft hyphen U+00AD, NBSP U+00A0, narrow NBSP
U+202F, figure space U+2007, hair space U+200A, en/em space U+2002/U+2003, LTR/RTL marks
U+200E/U+200F, LRE/RLE/PDF U+202A/U+202B/U+202C, tag characters U+E0000–U+E007F, variation
selectors U+FE00–U+FE0F, combining-mark stacks.

INVARIANT `count_hidden(t) == len(t) - len(scrub_hidden(t))` for every input. Pin the
invariant, not a per-class list.

PRIOR 12 of 19 carrier classes passed straight through while the counter reported 0. The
counter and the scrubber drifted apart three separate times, one class at a time.

---

## T03 — the similarity gate accepts inverted meaning

FILE `untell/scripts/run.py` — `similarity`, `meaning_preserved`, `recommended_bar`

PROBE 20 pairs where exactly one word flips the meaning: faster/slower, increased/decreased,
before/after, always/never, more/fewer, above/below, accept/reject, with/without, and 12
more. Score each pair. Also score 20 genuine paraphrase pairs as a control.

INVARIANT Every inverted pair must score BELOW the bar `recommended_bar` returns, and the
inverted set's scores must be clearly separated from the paraphrase control set. Print both
sets and the bar.

PRIOR "runs faster" → "runs slower" scored 0.974 against a 0.76 bar. The "meaning preserved"
guarantee did not hold at all, and no test noticed.

---

## T04 — a detector is dead, constant, or inverted

FILE `untell/detectors/` — `load_detectors`, `Tier`

PROBE Load each detector. Score 10 known-human and 10 known-AI PARAGRAPHS (150+ words each —
not sentences). Print per detector: the 20 raw scores, the min, the max, and the number of
distinct values.

INVARIANT No detector may return a constant. No detector may score human text higher than AI
text on average. Report the mean of each class per detector.

PRIOR One detector emitted a constant and was documented as an "immovable wall" because the
number never moved. Another was anti-correlated but audited OK because the audit's probes
were single sentences and the real loop scores paragraphs — burstiness is undefined on one
sentence. `mage` returns exactly 1.0, which silently disabled candidate selection.

---

## T05 — flagged rate at the shipped threshold

FILE `untell/detectors/`, `untell/scripts/score.py`

PROBE Score 20 known-HUMAN paragraphs. Count how many the shipped threshold flags as AI.

INVARIANT The false-positive rate on human text at the SHIPPED threshold must be low. Print
the count and the threshold used.

PRIOR An audit reported AUROC 0.999 while the shipped threshold flagged 95% of human text.
AUROC measures separation and hides calibration. Measure AT the threshold that ships.

---

## T06 — a replacement emits the tell it fixes

FILE `untell/scripts/tells.py`, `untell/humanness.py` — `score_tells`

PROBE Extract every hard-coded bad→good replacement table in the file. For each entry, run
`score_tells` on the GOOD side.

INVARIANT No replacement's output may itself match any catalogued tell. Print every entry
whose good side scores non-zero.

PRIOR 14 replacements produced a catalogued tell as their output. Every such table needs the
good column asserted, not just the bad one.

---

## T07 — a counting regex matches nothing

FILE `untell/scripts/tells.py` and every module with a counting pattern

PROBE For each compiled pattern, run it against a string you construct to be a known
positive for that pattern. Print pattern name, pattern source repr, and match count.

INVARIANT Every counting pattern matches its known positive at least once. A pattern that
matches nothing must be deleted, not left in.

PRIOR Three patterns contained a literal 0x08 backspace byte where `\b` was intended inside
an `r"..."` string. They matched nothing, read as a clean score of zero, and 2526 tests were
blind to it.

---

## T08 — a tell fires at a non-human rate

FILE `untell/humanness.py`, `untell/scripts/tells.py`

PROBE For every hard-coded word list, opener list, or substitution rate, measure the emitted
frequency in rewriter output over 20 documents, and the same frequency in a human corpus.
Print both columns side by side.

INVARIANT The emitted rate must be within the human range. Both columns, not one.

PRIOR Openers were frequency-screened against human text — every word was human-attested —
then applied at 12x the human rate. "though" was emitted 29 times. A fingerprint made
entirely of human words.

---

## T09 — the rewriter is a no-op

FILE `untell/scripts/run.py` — `untell_text`; `untell/rewriter/composite.py`

PROBE Run `untell_text` end to end on 10 documents. Print, per document: input length,
output length, whether the text changed at all, the similarity score, and the pre/post
detector scores.

INVARIANT `similarity == 1.000` on any document means nothing was rewritten. The count of
changed documents must be 10 of 10, and the loop must not report "passed" for a document it
did not change.

PRIOR The DEFAULT rewriter shipped as a no-op on 10 of 10 documents: `mage` saturates at
exactly 1.0, so the `cand < best` comparison against `max` never fired and every candidate
was rejected. The report said "passed". `similarity 1.000` was the only visible tell.

---

## T10 — a gate rejects everything the rewriter actually emits

FILE `untell/scripts/entailment.py`, `untell/scripts/verify.py`, `untell/scripts/quality.py`

PROBE Do NOT hand-write the candidate rewrites. Capture the candidates the real rewriter
emits (log them inside the loop), then run the gate over those. Print accept/reject per
candidate.

INVARIANT The gate must not reject the rewriter's normal output. A rejection rate near 100%
means the loop silently rewrites nothing.

PRIOR A predicate-argument veto scored 9/9 on hand-written bad rewrites and 0/13 false
vetoes — then rejected EVERY candidate the structural rewriter produced, because that
rewriter's main move (joining clauses with "though"/"while") read to the veto as a changed
connective. A hand-written probe set cannot contain the cases the rewriter actually emits.

---

## T11 — output is ungrammatical but scores clean

FILE `untell/scripts/run.py`, `untell/rewriter/structural.py`

PROBE Rewrite 10 documents and READ every output sentence. Print them. Count sentence
fragments, dangling clauses, doubled connectives, and broken subject-verb agreement.

INVARIANT Zero fragments. A metric cannot see grammar — a fragment is perfectly clean to a
tell catalogue and to a detector score.

PRIOR The pipeline emitted sentence fragments invisibly for a long time. Nothing in the
metric stack could see them; only reading the output found them.

---

## T12 — long documents stop being rewritten partway

FILE `untell/text_split.py` — `split_sentences`, `aligned_chunks`; `untell/scripts/run.py`

PROBE Rewrite a 5000-word document. Compare input and output paragraph by paragraph. Print
the index of the last paragraph that actually changed.

INVARIANT Changes must reach the final paragraph. Also check detector scoring: score the
same text with a distinctive tell placed at word 50 and at word 2000.

PRIOR Detectors read only the first ~380 words, so the tail was never scored. Rewriting
reaching the end was never checked by anything.

---

## T13 — layout constructs are corrupted or skipped

FILE `untell/layout.py` — `blocks`, `apply_per_block`, `restore_layout_lines`

PROBE Round-trip a document containing: a fenced code block, an indented code block, a
nested list, a table, YAML front matter, a block quote, a footnote, an inline math span, a
display math block, and a horizontal rule.

INVARIANT Every non-prose construct comes out byte-identical. Prose around them is rewritten.
Print a diff per construct.

PRIOR The fenced code block was the one construct nobody had a test for.

---

## T14 — a neutral transform changes the verdict

FILE `untell/attacks/unicode_tricks.py`

PROBE Take 10 human documents. Apply transforms that change no words: NBSP for space,
straight quotes for curly, CRLF for LF, double space after period, trailing whitespace.
Score before and after.

INVARIANT The verdict must not move. Print flagged-count before and after, and the tell count
before and after.

PRIOR Substituting U+00A0 took human text from 5/10 to 9/10 flagged and hid 2 of 5 tells.
Ask which side of the ledger an asymmetric error lands on — this one made human text look AI.

---

## T15 — numbers are invented or lost

FILE `untell/scripts/numerals.py` — `missing_numbers`, `numbers_kept`

PROBE Rewrite 20 documents dense with figures. For each, compare the multiset of numbers in
input and output — including spelled-out forms ("fifteen" vs "15"), signs, and units.

INVARIANT No number may be dropped, changed, or invented. Print every mismatch with both
sides.

PRIOR Two of three spelled-number leaks are fixed; the invented-number path is a known open
case with a recorded 0/80 measurement. If your probe finds an invented number, check
`.claude/audit-log.md` and the numerals memory before calling it new.

---

## T16 — the API server fails open

FILE `untell/api_server.py`, `untell/mcp_server.py`

PROBE Via `fastapi.testclient`: empty body, missing required field, wrong types, 1MB input,
null bytes, a text field of `""`, unicode-only input, and two concurrent requests.

INVARIANT No 500s. No request returns a score for input it could not process. Empty input
must not be classified as AI.

PRIOR Empty string was classified as AI, and a score was floored at exactly the detection
threshold — both plausible-looking outputs, neither an error.

---

## T17 — a failure path returns a neutral value

FILE `untell/detectors/base.py`, `untell/scripts/score.py`, `untell/_retry.py`

PROBE Grep for `0.5`, `except`, and every default-on-failure return in the scoring path.
Force each failure (unreachable model, missing key, timeout) and print what the caller sees.

INVARIANT A failure must be visible to the caller — a flag, a `None`, an exception. It must
never be a number that reads as a valid score.

PRIOR "Neutral 0.5 on failure" appeared in five separate components. A dead component that
returns 0.5 is indistinguishable from a working one that is unsure.

---

## T18 — a CLI reports success having done nothing

FILE `untell/scripts/cli.py`, `run.py`, `score.py`, `audit.py`

PROBE For each console entry point: empty stdin, a file that does not exist, a file of only
whitespace, `--json` on every subcommand. Print stdout, stderr, and `$LASTEXITCODE`.

INVARIANT A run that produced no result exits non-zero. `--json` output parses. An error
message names the file.

PRIOR A report that reported nothing exited zero.

---

## T19 — an aggregate disagrees with the per-item record

FILE `eval/` — `detector_audit.py`, `ceiling.py`, `tells_auroc.py`, `report.py`

PROBE Run an eval that prints a mean. Then print the per-item record behind that mean and
recompute by hand.

INVARIANT Mean and per-item record agree, and the reported `n` matches the number of items
actually scored. Print the corpus name and size alongside every number.

PRIOR Three times in one session the aggregate and the paired record disagreed; the per-item
record was right every time. Also: nine results generalised from a single demo corpus. Every
number is a property of its corpus — say which corpus, or the number means nothing.

---

## T20 — a mock-only test proves nothing

FILE `tests/` — any test that asserts a constructed string, query, escape, or payload shape

PROBE Grep tests for assertions on a built string that is later handed to an external engine
(a query, an escape, a regex, a serialized payload, a subprocess argv). For each, run ONE
real round-trip through the actual engine.

INVARIANT The engine accepts what the test asserts. If the shape test passes and the real
call fails, the test was decoration.

PRIOR In a sibling project a quoting fix survived 27 review passes and every reviewer because
its test mocked the engine: it asserted SQL-style quote doubling, and the real engine wanted
backslash escaping. A mock cannot tell a valid escape from an invalid one. Defensive code
plus a green mock test is NOT verified — only a real round-trip is.
