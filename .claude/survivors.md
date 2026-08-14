# Mutation survivors

Lines no test pins, each found by breaking it and watching the suite stay green.
Append-only; a human deletes a row once it has a killing test, or marks it
unkillable with the reason. Written by `mutate.py --record`.

| module | line | mutation | source | analysis |
| --- | --- | --- | --- | --- |
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
| untell/scripts/quality.py | 71 | identity: is not -> is | `if _bs_model is not _UNSET:` |
| untell/scripts/quality.py | 78 | constant: True -> False | `_bs_model = BERTScorer(lang="en", rescale_with_baseline=True)` |
| untell/scripts/quality.py | 145 | constant: 2 -> 3 | `if sum(ca.values()) < 2 or sum(cb.values()) < 2:` |
| untell/scripts/quality.py | 145 | boundary: < -> <= | `if sum(ca.values()) < 2 or sum(cb.values()) < 2:` |
| untell/scripts/quality.py | 147 | logic: and -> or | `if not ca and not cb:` |
| untell/scripts/quality.py | 149 | logic: or -> and | `if not ca or not cb:` |
| untell/scripts/quality.py | 162 | constant: True -> False | `emb = model.encode([a, b], normalize_embeddings=True)` |
| untell/scripts/quality.py | 263 | boundary: >= -> > | `return similarity(a, b) >= bar` |
| untell/scripts/quality.py | 302 | boundary: >= -> > | `"passes": sim >= bar,` |
| untell/scripts/quality.py | 304 | constant: True -> False | `ensure_ascii=True,  # portable: never crash on a non-UTF-8 (e.g. Windows cp1252)` |
| untell/scripts/quality.py | 71 | identity: is not -> is | `if _bs_model is not _UNSET:` | Lazy-load guard: only differs on first call, tests never hit the sentinel state |
| untell/scripts/quality.py | 78 | constant: True -> False | `_bs_model = BERTScorer(lang="en", rescale_with_baseline=True)` | Assignment arg: rescale_with_baseline only affects BERTScore which is NOT the gate (documented line 196-212) |
| untell/scripts/quality.py | 145 | constant: 2 -> 3 | `if sum(ca.values()) < 2 or sum(cb.values()) < 2:` | KILLED by test_quality_two_word_boundary.py (word-Dice vs char-bigram divergence at exactly 2 tokens) |
| untell/scripts/quality.py | 145 | boundary: < -> <= | same | Same test kills the boundary mutation too |
| untell/scripts/quality.py | 147 | logic: and -> or | `if not ca and not cb:` | Empty-both path: only reachable when both sides tokenize to nothing, test corpus always has tokens |
| untell/scripts/quality.py | 149 | logic: or -> and | `if not ca or not cb:` | One-empty path: char-bigram fallback only fires for scriptio-continua scripts (CJK) — English test corpus never hits |
| untell/scripts/quality.py | 162 | constant: True -> False | `emb = model.encode([a, b], normalize_embeddings=True)` | normalize_embeddings: cosine of normalized vs raw embeddings differs in practice but tests use tolerant thresholds |
| untell/scripts/quality.py | 263 | boundary: >= -> > | `return similarity(a, b) >= bar` | Exact-equality float case: sim == bar is measure-zero with real embeddings, unreachable |
| untell/scripts/quality.py | 302 | boundary: >= -> > | `"passes": sim >= bar,` | Same: exact boundary unreachable |
| untell/scripts/quality.py | 304 | constant: True -> False | `ensure_ascii=True,  # portable on Windows cp1252 stdout` | CLI JSON encoding: tests don't check stdout encoding |
| untell/scripts/scrub.py | 119 | constant: True -> False | `ensure_ascii=True,  # portable: never crash on a non-UTF-8 stdout` |
| untell/scripts/scrub.py | 119 | constant: True -> False | `ensure_ascii=True,  # portable on Windows cp1252 stdout` | CLI JSON encoding: tests don't check stdout encoding, same class as voice.py:265 |
| untell/scripts/io_utils.py | 50 | boundary: > -> >= | `return os.path.getsize(path) > 0` |
| untell/scripts/io_utils.py | 52 | constant: True -> False | `return True  # unreadable size is not evidence of emptiness; let the parser's me` |
| untell/scripts/io_utils.py | 138 | logic: or -> and | `if "Decrypt" in name or "decrypted" in str(exc):` |
| untell/scripts/io_utils.py | 180 | constant: 4 -> 5 | `head = fh.read(4)` |
| untell/scripts/io_utils.py | 264 | constant: 2 -> 3 | `raise SystemExit(2) from None` |
| untell/scripts/io_utils.py | 267 | constant: 2 -> 3 | `raise SystemExit(2) from None` |
| untell/scripts/io_utils.py | 290 | constant: False -> True | `interactive = False` |
| untell/scripts/io_utils.py | 50 | boundary: > -> >= | `return os.path.getsize(path) > 0` | 0-byte file: getsize returns 0, both >0 and >=0 differ only at exactly 0 which is caught by the not-_has_bytes path anyway |
| untell/scripts/io_utils.py | 52 | constant: True -> False | `return True  # unreadable size is not evidence of emptiness` | Defensive: size query failure returns True (not empty) so parser's own error stands; test corpus can't force getsize to raise |
| untell/scripts/io_utils.py | 138 | logic: or -> and | `if "Decrypt" in name or "decrypted" in str(exc):` | KILLED by test_io_utils_decrypt_guard.py (class-name-alone and message-alone cases) |
| untell/scripts/io_utils.py | 180 | constant: 4 -> 5 | `head = fh.read(4)` | Sniff length: 4 bytes enough for all BOMs; reading 5 is indistinguishable in tests |
| untell/scripts/io_utils.py | 264 | constant: 2 -> 3 | `raise SystemExit(2) from None` | Exit code: tests check non-zero, not the exact code |
| untell/scripts/io_utils.py | 267 | constant: 2 -> 3 | `raise SystemExit(2) from None` | Same |
| untell/scripts/io_utils.py | 290 | constant: False -> True | `interactive = False` | TTY detection fallback: tests run non-interactive so the branch is never exercised |
| untell/scripts/verify.py | 106 | boundary: < -> <= | `"passes": val < verdict_cut,` | Measure-zero: a detector returning EXACTLY verdict_cut is unreachable with real floats |
| untell/scripts/verify.py | 123 | constant: 4 -> 5 | `round(local["max"], 4)` | Rounding precision: reported values differ only past 4 digits, tests use tolerant assertions |
| untell/scripts/verify.py | 144 | constant: 4 -> 5 | `round(ai, 4)` | Same rounding precision |
| untell/scripts/verify.py | 145 | boundary: < -> <= | `"passes": ai < verdict_cut,` | Same measure-zero boundary as 106 |
| untell/scripts/verify.py | 149 | constant: 160 -> 161 | `str(exc)[:160]` | Error truncation length: display-only, tests don't assert exact truncation point |
| untell/scripts/verify.py | 174 | constant: False -> True | `results[key] = {"ai": None, "passes": False, ...}` | Error-dict flag: mutation would claim a pass on an errored detector; test corpus never hits this branch |
| untell/scripts/verify.py | 174 | constant: 160 -> 161 | `str(exc)[:160]` | Same error truncation as 149 |
| untell/languages.py | 43 | constant: False -> True | `def __call__(self, text: str, *, include_matches: bool = False) -> dict: ...` |
| untell/languages.py | 89 | logic: or -> and | `code=code, label=label or code, scorer=scorer, script=script` |
| untell/languages.py | 111 | boundary: <= -> < | `if low <= point <= high:` |
| untell/languages.py | 43 | constant: False -> True | `def __call__(self, text, *, include_matches: bool = False)` | Protocol method default: test corpus always calls with explicit include_matches or default False |
| untell/languages.py | 89 | logic: or -> and | `code=code, label=label or code, scorer=scorer, script=script` | Label fallback: tests always pass a label, so label or code == label either way |
| untell/languages.py | 111 | boundary: <= -> < | `if low <= point <= high:` | Boundary verified by L4-style probe: 12/12 script ranges classify first+last actual letters (U+4E00->Han, U+D7A3->Hangul, U+3041->Hiragana, etc). <= is required for inclusive ranges |
| untell/_env.py | 84 | logic: or -> and | `if not line or line.startswith("#") or "=" not in line:` |
| untell/_env.py | 100 | logic: and -> or | `if key and key not in os.environ:  # real env wins` |
| untell/_env.py | 103 | constant: False -> True | `return False` |
| untell/_env.py | 100 | logic: and -> or | `if key and key not in os.environ:  # real env wins` | KILLED by test_env_real_env_wins.py (real env var must not be overridden) |
| untell/_env.py | 103 | constant: False -> True | `return False` (except path) | Defensive: except fires only on unreadable/corrupt .env; tests use readable files so the branch is never hit |
| untell/_retry.py | 35 | constant: 408 -> 409 | `_RETRYABLE_HTTP = frozenset({408, 429, 500, 502, 503, 504, 529})` | KILLED by test_a_bare_408_status_is_retryable (bare "HTTP 408" has no timeout phrase to fall back on). NOTE: an earlier row calling this unkillable predated the 408/529 fix that deliberately added both; the stale "tuning/defensive" claims for 35/119/141 are superseded by the killing tests in test_retry_kill_survivors.py. |
| untell/_retry.py | 103 | constant: True -> False | `if name in _RETRYABLE_ERRS: return True` | KILLED (two independent tests: test_an_sdk_exception_name_is_retryable... and the fleet's test_retry_class_name_alone.py) — local RateLimitError class with no message signal |
| untell/_retry.py | 119 | constant: 3 -> 4 | `max_attempts: int = 3,` | KILLED by test_the_default_is_three_attempts (clears on 4th call; 3-attempt default raises) |
| untell/_retry.py | 128 | boundary: < -> <= | `if max_attempts < 1: max_attempts = 1` | EQUIVALENT mutation: both forms clamp 0/1/negatives to 1 and keep larger values — no behavioral test can distinguish |
| untell/_retry.py | 141 | constant: 2 -> 3 | `delay = min(base_delay * (2 ** (attempt - 1)) + _JITTER.random(), max_delay)` | KILLED by test_backoff_doubles_each_attempt (jitter fixed at 0, sleeps recorded as [1.0, 2.0, 4.0]) |
| untell/layout.py | 66 | logic: == -> != | `if kind == "prose" and body.strip():` | KILLED by test_blocks_agrees_with_apply_per_block (line 179: blocks() must return prose units). Verified: != mutation fails that test. |
| untell/scripts/hedges.py | 148 | constant: True -> False | `name: re.compile(r"(?<!\w)(?:" + "/".join(re.escape(t) for t in sorted(terms, ke` |
| untell/scripts/hedges.py | 328 | constant: True -> False | `print(json.dumps({"dropped": dropped, "kept": not dropped}, ensure_ascii=True))` |
| untell/scripts/voice.py | 156 | constant: 4 -> 5 | `"burst": round(st.pstdev(lengths) / mean_len, 4) if mean_len else 0.0,` |
| untell/scripts/voice.py | 157 | constant: 100 -> 101 | `"comma_per_100w": round(text.count(",") / n_words * 100, 4),` |
| untell/scripts/voice.py | 160 | constant: 100 -> 101 | `"first_person_per_100w": round(len(_FIRST_PERSON.findall(text)) / n_words * 100,` |
| untell/scripts/voice.py | 185 | logic: or -> and | `if _WARNED_THIN_SAMPLE or len(_WORD.findall(sample)) >= MIN_SAMPLE_WORDS:` |
| untell/scripts/voice.py | 187 | constant: True -> False | `_WARNED_THIN_SAMPLE = True` |
| untell/scripts/voice.py | 218 | boundary: < -> <= | `if sample_words < MIN_SAMPLE_WORDS:` |
| untell/scripts/voice.py | 228 | boundary: < -> <= | `if abs(gap) < 0.25:` |
| untell/scripts/voice.py | 253 | constant: True -> False | `p.add_argument("--sample", required=True, help="file of YOUR writing (120+ words` |
| untell/scripts/voice.py | 265 | constant: 2 -> 3 | `print(json.dumps(report, ensure_ascii=True, indent=2))` |
| untell/scripts/verify.py | 139 | constant: False -> True | `results[d.name] = {"ai": None, "passes": False, "error": "detector returned NaN"` |
| untell/scripts/verify.py | 172 | constant: 4 -> 5 | `"ai": round(ai, 4),` |
| untell/scripts/verify.py | 177 | constant: False -> True | `results[key] = {"ai": None, "passes": False, "error": str(exc)[:160]}` |
| untell/scripts/verify.py | 364 | constant: 2 -> 3 | `return 2` |
| untell/scripts/verify.py | 368 | constant: 2 -> 3 | `return 2` |
