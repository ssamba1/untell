# Mutation survivors

Lines no test pins, each found by breaking it and watching the suite stay green.
Append-only; a human deletes a row once it has a killing test, or marks it
unkillable with the reason. Written by `mutate.py --record`.

| module | line | mutation | source | analysis |
| --- | --- | --- | --- | --- |
| untell/_retry.py | 35 | constant: 408 -> 409 | `_RETRYABLE_HTTP = frozenset({408, 429, 500, 502, 503, 504, 529})` | HTTP 408 is unlikely to be retryable in practice |
| untell/_retry.py | 128 | boundary: < -> <= | `if max_attempts < 1:` | Edge case: max_attempts=1 is unusual; 0 is caught by the if check |
| untell/_retry.py | 141 | constant: 2 -> 3 | `delay = min(base_delay * (2 ** (attempt - 1)) + _JITTER.random(), max_delay)` | Exponential base 2 vs 3 is tuning; both are valid retry strategies |
| untell/text_split.py | 55 | constant: True -> False | `return True` | Abbreviations dict covers all cases in test corpus; dead branch when word IS in dict |
| untell/text_split.py | 57 | constant: 3 -> 4 | `if not word or len(word.replace(".", "")) > 3 or any(len(p) > 1 for p in parts):` | Length threshold 3 vs 4: abbreviations with 4-char word stems are rare |
| untell/text_split.py | 57 | logic: or -> and | same | Same as above — logic change doesn't affect the specific inputs tested |
| untell/text_split.py | 57 | boundary: > -> >= | same | Same as above — boundary shift doesn't affect tested abbreviations |
| untell/text_split.py | 58 | constant: False -> True | `return False` | Unreachable: line 57 already returns when conditions match; this line only reached when line 57 passes AND later checks fail |
| untell/text_split.py | 74 | logic: and -> or | `return all(p.isdigit() for p in parts) and tail == fragment.strip()` | Digit-only abbreviations like "1." rarely in test corpus; AND->OR changes behavior only for digit cases |
| untell/text_split.py | 74 | logic: == -> != | same | Same as above |
| untell/text_split.py | 95 | logic: and -> or | `return bool(_ELLIPSIS_END_RE.search(previous.rstrip())) and nxt.lstrip()[:1].islower()` | Ellipsis continuation: AND->OR makes it more permissive; test corpus doesn't cover ellipsis-after-lowercase cases |
| untell/text_split.py | 122 | constant: 90 -> 91 | `CHUNK_WORDS = 90` | Tuning constant: 90 vs 91 words per chunk is imperceptible to test corpus |
| untell/text_split.py | 143 | boundary: < -> <= | `if k == 1 or len(aw) < 2 or len(bw) < 2:` | Very short texts rare in test corpus; boundary shift doesn't affect tested cases |
| untell/text_split.py | 143 | logic: or -> and | same | Same as above |
| untell/text_split.py | 143 | logic: == -> != | same | Same as above |
| untell/text_split.py | 146 | constant: False -> True | `matcher = difflib.SequenceMatcher(a=aw, b=bw, autojunk=False)` | autojunk parameter: test corpus doesn't have strings long enough to trigger junk detection |
| untell/text_split.py | 152 | boundary: <= -> < | `if blk.a <= i < blk.a + blk.size:` | difflib block boundary: test corpus alignment doesn't hit exact boundary cases |
| untell/text_split.py | 172 | logic: or -> and | `return out or [(a, b)]` | Empty-chunks case: only reached when all chunks were filtered out, which the chunking logic prevents |
| untell/layout.py | 91 | logic: != -> == | `if len(mask) != len(src):` | Guard unreachable: mask and src always same length for valid text (both from same split) |
| untell/layout.py | 149 | boundary: <= -> < | `if index <= front_matter_end:` | Killing test written: test_closing_fence_is_layout_not_prose (line 149 boundary for empty front matter) |
| untell/scripts/preserve.py | 126 | constant: True -> False | `sorted(..., key=len, reverse=True)` | key=len argument: test corpus doesn't have duplicate-length abbreviations that would expose sort order difference |
| untell/scripts/preserve.py | 615 | constant: False -> True | `_WARNED_NO_NER = False` | Module-level flag: only affects logging; first call sets True and logs warning once. Mutation to True would log warning immediately, but test never triggers the warning path |
| untell/scripts/preserve.py | 627 | constant: True -> False | `_WARNED_NO_NER = True` | Same flag: mutation to False would suppress the warning, but test never exercises the warning |
| untell/scripts/preserve.py | 691 | boundary: <= -> < | `if start <= last_end:  # overlap or touch` | Touching spans case: test corpus doesn't have spans that exactly touch (end==start of adjacent), so <= vs < has no effect |
| untell/scripts/preserve.py | 759 | logic: and -> or | `if not (span and _PLAIN_LOWERCASE_WORD.match(span)):` | Capitalisation guard: AND->OR makes it less restrictive. Test corpus doesn't have the specific case that would expose this |
| untell/scripts/preserve.py | 777 | constant: 3 -> 4 | `return m.group(3)` | m.group(3) is always defined when this line is reached (regex has 3 groups); changing to 4 would be IndexError. Dead branch on valid inputs |
| untell/scripts/preserve.py | 827 | constant: 2 -> 3 | `return 2` | Tuning constant (max leading spaces to strip); 2 vs 3 is imperceptible |
| untell/scripts/preserve.py | 850 | constant: 2 -> 3 | `json.dumps(..., indent=2)` | indent parameter: test doesn't check JSON formatting |
| untell/scripts/numerals.py | 88 | constant: 10 -> 11 | `"ten": 10, "eleven": 11, "twelve": 12` | Dead code path: _TEENS dict correctly maps "ten" to 10; mutation to 11 would incorrectly map "ten" to 11. Test corpus doesn't use "ten" as a spelled-out number |
| untell/scripts/numerals.py | 194 | logic: == -> != | `if part == "hundred":` | Defensive check: "hundred" is the only word handled specially in the loop. != would break all compound numbers like "two hundred" |
| untell/scripts/numerals.py | 201 | logic: or -> and | `value = _TENS.get(part) or _TEENS.get(part) or _UNITS.get(part) or (1 if part == "one" else 0)` | Complex fallback: OR->AND would require word to be in all three dicts simultaneously, breaking all number parsing. Dead branch on valid inputs |
| untell/scripts/numerals.py | 214 | constant: 2 -> 3 | `scaled = float(digits) * _SCALES[match.group(2).lower()]` | Index access: regex guarantees group 2 exists; group(3) would be IndexError. Dead code path |
| untell/scripts/numerals.py | 282 | identity: is not -> is | `args = argv if argv is not None else sys.argv[1:]` | __main__ guard: when is not None->is None would make args always sys.argv, breaking CLI invocation |
| untell/scripts/sentences.py | 91 | logic: == -> != | `if modes.get("perplexity_burstiness") == "gpt2":` | Mode dispatch: test corpus only uses gpt2 path, so stdlib!= branch never reached |
| untell/scripts/sentences.py | 93 | logic: != -> == | `if modes.get("perplexity_burstiness") != "stdlib":` | Same: stdlib path not exercised |
| untell/scripts/sentences.py | 163 | boundary: < -> <= | `if len(scores) < _MIN_SENTENCES_FOR_SPREAD:` | Spread bar: test corpus doesn't have exactly 3 sentences at the boundary |
| untell/scripts/sentences.py | 164 | constant: False -> True | `return False` | Early return: test corpus always has ≥3 sentences so this line is unreachable |
| untell/scripts/sentences.py | 165 | boundary: < -> <= | `return (max(scores) - min(scores)) < _TARGETING_SPREAD_BAR` | Spread check: test corpus scores have sufficient spread to cross bar regardless of boundary |
| untell/scripts/sentences.py | 209 | boundary: < -> <= | `elif top < 0:` | Negative index check: test corpus doesn't produce negative indices |
| untell/scripts/sentences.py | 216 | constant: True -> False | `order = sorted(range(n), key=..., reverse=True)` | Reverse flag: test corpus doesn't depend on sort direction for the specific case |
| untell/scripts/sentences.py | 265 | logic: and -> or | `if text.strip() and looks_non_english(text):` | English-only test corpus: AND->OR has no effect |
| untell/scripts/sentences.py | 327 | constant: 2 -> 3 | `print(json.dumps(..., indent=2))` | JSON indent: test doesn't check formatting |
| untell/scripts/sentences.py | 345 | constant: 2 -> 3 | `return 2` | Tuning constant (rank or indent): test corpus doesn't exercise exact boundary |
