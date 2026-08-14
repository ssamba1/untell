# Mutation survivors

Lines no test pins, each found by breaking it and watching the suite stay green.
Append-only; a human deletes a row once it has a killing test, or marks it
unkillable with the reason. Written by `mutate.py --record`.

| module | line | mutation | source | analysis |
| --- | --- | --- | --- | --- |
| untell/text_split.py | 55 | constant: True -> False | `return True` | KILLED by tests/test_dict_abbreviation_does_not_end_a_sentence.py: 'Dr. Smith arrived.' splits into ['Dr.', 'Smith arrived.'] under the mutant (dict lookup returns False, fallthrough treats 'dr' as sentence-ender); original keeps one sentence. Prior 'dead branch' note superseded. |
| untell/text_split.py | 57 | constant: 3 -> 4 | `if not word or len(word.replace(".", "")) > 3 or any(len(p) > 1 for p in parts):` | Length threshold 3 vs 4: abbreviations with 4-char word stems are rare |
| untell/text_split.py | 57 | logic: or -> and | same | Same as above — logic change doesn't affect the specific inputs tested |
| untell/text_split.py | 57 | boundary: > -> >= | same | Same as above — boundary shift doesn't affect tested abbreviations |
| untell/text_split.py | 58 | constant: False -> True | `return False` | Unreachable: line 57 already returns when conditions match; this line only reached when line 57 passes AND later checks fail |
| untell/text_split.py | 74 | logic: and -> or | `return all(p.isdigit() for p in parts) and tail == fragment.strip()` | KILLED by tests/test_sentence_final_number_is_not_an_abbreviation.py: 'The mean was 3.5.' must NOT be an abbreviation; mutant merges 'The mean was 3.5. Variance was low.' into ONE sentence — the documented PRIOR defect, reintroduced. 2 failed under mutation. |
| untell/text_split.py | 74 | logic: == -> != | same | KILLED by same test: '3.5.' as whole fragment is a list marker (abbrev, no split); != makes it split mid-list-item. 3 failed under mutation. |
| untell/text_split.py | 95 | logic: and -> or | `return bool(_ELLIPSIS_END_RE.search(previous.rstrip())) and nxt.lstrip()[:1].islower()` | KILLED by tests/test_lowercase_continuation_without_ellipsis_does_not_merge.py: 'Hello world. next thing' merges to ONE sentence under the mutant (False or True), splitting correctly as two under the original. Prior note ('corpus doesn't cover ellipsis-after-lowercase') wrong — the distinguishing input has NO ellipsis. |
| untell/text_split.py | 122 | constant: 90 -> 91 | `CHUNK_WORDS = 90` | Tuning constant: 90 vs 91 words per chunk is imperceptible to test corpus |
| untell/text_split.py | 143 | boundary: < -> <= | `if k == 1 or len(aw) < 2 or len(bw) < 2:` | Very short texts rare in test corpus; boundary shift doesn't affect tested cases |
| untell/text_split.py | 143 | logic: or -> and | same | KILLED by tests/test_tiny_side_returns_the_pair_whole.py: 100-word vs 1-word pair falls through to chunking, re-cutting the long side to 50 words; original returns the pair whole. Prior 'very short texts rare' note wrong — the distinguishing input has ONE tiny side. |
| untell/text_split.py | 143 | logic: == -> != | same | Same as above |
| untell/text_split.py | 146 | constant: False -> True | `matcher = difflib.SequenceMatcher(a=aw, b=bw, autojunk=False)` | autojunk parameter: test corpus doesn't have strings long enough to trigger junk detection |
| untell/text_split.py | 152 | boundary: <= -> < | `if blk.a <= i < blk.a + blk.size:` | difflib block boundary: test corpus alignment doesn't hit exact boundary cases |
| untell/text_split.py | 172 | logic: or -> and | `return out or [(a, b)]` | Empty-chunks case: only reached when all chunks were filtered out, which the chunking logic prevents |
| untell/layout.py | 91 | logic: != -> == | `if len(mask) != len(src):` | Guard unreachable: mask and src always same length for valid text (both from same split) |
| untell/layout.py | 149 | boundary: <= -> < | `if index <= front_matter_end:` | Killing test written: test_closing_fence_is_layout_not_prose (line 149 boundary for empty front matter) |
| untell/scripts/preserve.py | 126 | constant: True -> False | `sorted(..., key=len, reverse=True)` | key=len argument: test corpus doesn't have duplicate-length abbreviations that would expose sort order difference |
| untell/scripts/preserve.py | 615 | constant: False -> True | `_WARNED_NO_NER = False` | Module-level flag: only affects logging; first call sets True and logs warning once. Mutation to True would log warning immediately, but test never triggers the warning path |
| untell/scripts/preserve.py | 627 | constant: True -> False | `_WARNED_NO_NER = True` | Same flag: mutation to False would suppress the warning, but test never exercises the warning |
| untell/scripts/preserve.py | 691 | boundary: <= -> < | `if start <= last_end:  # overlap or touch` | KILLED by tests/test_touching_spans_lock_as_one_fact.py: '2023-05-0542' produces touching spans (date 0-7, number 7-12); original merges to one sentinel, mutant splits into two. Prior 'unkillable' note (corpus lacks touching spans) superseded — a killing test constructs them. |
| untell/scripts/preserve.py | 759 | logic: and -> or | `if not (span and _PLAIN_LOWERCASE_WORD.match(span)):` | Capitalisation guard: AND->OR makes it less restrictive. Test corpus doesn't have the specific case that would expose this |
| untell/scripts/preserve.py | 777 | constant: 3 -> 4 | `return m.group(3)` | m.group(3) is always defined when this line is reached (regex has 3 groups); changing to 4 would be IndexError. Dead branch on valid inputs |
| untell/scripts/preserve.py | 827 | constant: 2 -> 3 | `return 2` | Tuning constant (max leading spaces to strip); 2 vs 3 is imperceptible |
| untell/scripts/preserve.py | 850 | constant: 2 -> 3 | `json.dumps(..., indent=2)` | indent parameter: test doesn't check JSON formatting |
| untell/scripts/numerals.py | 88 | constant: 10 -> 11 | `"ten": 10, "eleven": 11, "twelve": 12` | KILLED by tests/test_spelled_number_dict_values_are_exact.py: _spelled_value('ten') -> '10' original, '11' mutant. Prior 'test corpus doesn't use ten' note wrong — the dict value is the parser's output. Red on mutation, green on original. |
| untell/scripts/numerals.py | 194 | logic: == -> != | `if part == "hundred":` | Defensive check: "hundred" is the only word handled specially in the loop. != would break all compound numbers like "two hundred" |
| untell/scripts/numerals.py | 201 | logic: or -> and | `value = _TENS.get(part) or _TEENS.get(part) or _UNITS.get(part) or (1 if part == "one" else 0)` | Complex fallback: OR->AND would require word to be in all three dicts simultaneously, breaking all number parsing. Dead branch on valid inputs |
| untell/scripts/numerals.py | 214 | constant: 2 -> 3 | `scaled = float(digits) * _SCALES[match.group(2).lower()]` | Index access: regex guarantees group 2 exists; group(3) would be IndexError. Dead code path |
| untell/scripts/numerals.py | 282 | identity: is not -> is | `args = argv if argv is not None else sys.argv[1:]` | __main__ guard: when is not None->is None would make args always sys.argv, breaking CLI invocation |
| untell/scripts/sentences.py | 91 | logic: == -> != | `if modes.get("perplexity_burstiness") == "gpt2":` | Mode dispatch: test corpus only uses gpt2 path, so stdlib!= branch never reached |
| untell/scripts/sentences.py | 93 | logic: != -> == | `if modes.get("perplexity_burstiness") != "stdlib":` | Same: stdlib path not exercised |
| untell/scripts/sentences.py | 163 | boundary: < -> <= | `if len(scores) < _MIN_SENTENCES_FOR_SPREAD:` | KILLED by tests/test_exactly_min_sentences_still_checks_spread.py: exactly 3 sentences with spread 0.02 < 0.05 bar -> original True (unrankable), mutant False. Prior note ('corpus lacks exactly 3 at the boundary') superseded — the boundary is the test. |
| untell/scripts/sentences.py | 164 | constant: False -> True | `return False` | Early return: test corpus always has ≥3 sentences so this line is unreachable |
| untell/scripts/sentences.py | 165 | boundary: < -> <= | `return (max(scores) - min(scores)) < _TARGETING_SPREAD_BAR` | Spread check: test corpus scores have sufficient spread to cross bar regardless of boundary |
| untell/scripts/sentences.py | 209 | boundary: < -> <= | `elif top < 0:` | KILLED by tests/test_top_zero_flags_nothing.py: top=0 must flag nothing (empty list), mutant raises ValueError. Prior note ('corpus doesn't produce negative indices') wrong — the distinguishing input is top=0, the boundary itself. |
| untell/scripts/sentences.py | 216 | constant: True -> False | `order = sorted(range(n), key=..., reverse=True)` | Reverse flag: test corpus doesn't depend on sort direction for the specific case |
| untell/scripts/sentences.py | 265 | logic: and -> or | `if text.strip() and looks_non_english(text):` | KILLED by tests/test_english_text_is_not_warned_as_non_english.py: ordinary English text must NOT get the 'reads as a Latin-script language other than English' caveat; mutant fires it on any non-empty text (1 failed under mutation). Prior 'English-only corpus' note wrong — English text IS the distinguishing input. |
| untell/scripts/sentences.py | 327 | constant: 2 -> 3 | `print(json.dumps(..., indent=2))` | JSON indent: test doesn't check formatting |
| untell/scripts/sentences.py | 345 | constant: 2 -> 3 | `return 2` | Tuning constant (rank or indent): test corpus doesn't exercise exact boundary |
| untell/scripts/quality.py | 71 | identity: is not -> is | `if _bs_model is not _UNSET:` |
| untell/scripts/quality.py | 78 | constant: True -> False | `_bs_model = BERTScorer(lang="en", rescale_with_baseline=True)` |
| untell/scripts/quality.py | 145 | constant: 2 -> 3 | `if sum(ca.values()) < 2 or sum(cb.values()) < 2:` |
| untell/scripts/quality.py | 145 | boundary: < -> <= | `if sum(ca.values()) < 2 or sum(cb.values()) < 2:` |
| untell/scripts/quality.py | 147 | logic: and -> or | `if not ca and not cb:` |
| untell/scripts/quality.py | 149 | logic: or -> and | `if not ca or not cb:` |
| untell/scripts/quality.py | 162 | constant: True -> False | `emb = model.encode([a, b], normalize_embeddings=True)` |
| untell/scripts/quality.py | 302 | boundary: >= -> > | `"passes": sim >= bar,` |
| untell/scripts/quality.py | 304 | constant: True -> False | `ensure_ascii=True,  # portable: never crash on a non-UTF-8 (e.g. Windows cp1252)` |
| untell/scripts/quality.py | 71 | identity: is not -> is | `if _bs_model is not _UNSET:` | Lazy-load guard: only differs on first call, tests never hit the sentinel state |
| untell/scripts/quality.py | 78 | constant: True -> False | `_bs_model = BERTScorer(lang="en", rescale_with_baseline=True)` | Assignment arg: rescale_with_baseline only affects BERTScore which is NOT the gate (documented line 196-212) |
| untell/scripts/quality.py | 145 | constant: 2 -> 3 | `if sum(ca.values()) < 2 or sum(cb.values()) < 2:` | KILLED by test_quality_two_word_boundary.py (word-Dice vs char-bigram divergence at exactly 2 tokens) |
| untell/scripts/quality.py | 145 | boundary: < -> <= | same | Same test kills the boundary mutation too |
| untell/scripts/quality.py | 147 | logic: and -> or | `if not ca and not cb:` | Empty-both path: only reachable when both sides tokenize to nothing, test corpus always has tokens |
| untell/scripts/quality.py | 149 | logic: or -> and | `if not ca or not cb:` | One-empty path: char-bigram fallback only fires for scriptio-continua scripts (CJK) — English test corpus never hits |
| untell/scripts/quality.py | 162 | constant: True -> False | `emb = model.encode([a, b], normalize_embeddings=True)` | normalize_embeddings: cosine of normalized vs raw embeddings differs in practice but tests use tolerant thresholds |
| untell/scripts/quality.py | 263 | boundary: >= -> > | `return similarity(a, b) >= bar` | KILLED by tests/test_similarity_exactly_at_bar_passes.py: with _model=None the token path yields exact rationals — 1 shared of 4 unique = Dice 0.5 = TOKEN_BAR exactly; original passes, mutant rejects. Prior 'measure-zero with real embeddings' note wrong: the token path makes equality exact. |
| untell/scripts/quality.py | 302 | boundary: >= -> > | `"passes": sim >= bar,` | KILLED by tests/test_quality_cli_exact_bar.py: CLI computes sim >= bar INLINE (never calls passes()) — old note 'same test kills it via shared logic' was WRONG, mutation run proved 302 survived with the 263-killer in the set. Exact-bar pair (cat dog/cat tree, Dice 0.5=TOKEN_BAR) through quality_main; red on >=->> (verified), green on original. |
| untell/scripts/quality.py | 304 | constant: True -> False | `ensure_ascii=True,  # portable on Windows cp1252 stdout` | CLI JSON encoding: tests don't check stdout encoding |
| untell/scripts/scrub.py | 119 | constant: True -> False | `ensure_ascii=True,  # portable: never crash on a non-UTF-8 stdout` | KILLED by tests/test_scrub_cli_ascii_safe.py: non-ASCII input (café+ZWSP) through --json asserts output encodes ascii. Mutant emits literal é -> encode('ascii') raises. Red on mutation (verified), green on original. Same class as quality.py:304/voice.py:265. |
| untell/scripts/scrub.py | 119 | constant: True -> False | `ensure_ascii=True,  # portable on Windows cp1252 stdout` | CLI JSON encoding: tests don't check stdout encoding, same class as voice.py:265 |
| untell/scripts/io_utils.py | 50 | boundary: > -> >= | `return os.path.getsize(path) > 0` |
| untell/scripts/io_utils.py | 52 | constant: True -> False | `return True  # unreadable size is not evidence of emptiness; let the parser's me` |
| untell/scripts/io_utils.py | 138 | logic: or -> and | `if "Decrypt" in name or "decrypted" in str(exc):` |
| untell/scripts/io_utils.py | 180 | constant: 4 -> 5 | `head = fh.read(4)` |
| untell/scripts/io_utils.py | 264 | constant: 2 -> 3 | `raise SystemExit(2) from None` |
| untell/scripts/io_utils.py | 267 | constant: 2 -> 3 | `raise SystemExit(2) from None` |
| untell/scripts/io_utils.py | 290 | constant: False -> True | `interactive = False` |
| untell/scripts/io_utils.py | 50 | boundary: > -> >= | `return os.path.getsize(path) > 0` | KILLED by tests/test_empty_file_is_reported_empty_not_corrupt.py: mutant makes empty .docx report 'not a readable .docx (corrupt)' instead of 'is empty, so there is no .docx to read'. Prior note ('caught by the not-_has_bytes path anyway') wrong — the DIFFERENT MESSAGE is the observable. |
| untell/scripts/io_utils.py | 52 | constant: True -> False | `return True  # unreadable size is not evidence of emptiness` | KILLED by tests/test_unreadable_size_is_not_empty.py: monkeypatched getsize raises OSError -> original True (defensive, parser's message stands), mutant False (unreadable file reads as empty). Prior 'can't force getsize to raise' note wrong — monkeypatch does it. |
| untell/scripts/io_utils.py | 138 | logic: or -> and | `if "Decrypt" in name or "decrypted" in str(exc):` | KILLED by test_io_utils_decrypt_guard.py (class-name-alone and message-alone cases) |
| untell/scripts/io_utils.py | 180 | constant: 4 -> 5 | `head = fh.read(4)` | Sniff length: 4 bytes enough for all BOMs; reading 5 is indistinguishable in tests |
| untell/scripts/io_utils.py | 264 | constant: 2 -> 3 | `raise SystemExit(2) from None` | KILLED by tests/test_read_file_or_exit_exits_two.py: missing file -> SystemExit(2) original, (3) mutant. The docstring says exit 2 matches argparse's usage-error convention — the exact code is the contract. Red on mutation, green on original. |
| untell/scripts/io_utils.py | 267 | constant: 2 -> 3 | `raise SystemExit(2) from None` | KILLED by same test (OSError case): monkeypatched read_file raises OSError -> SystemExit(2) original, (3) mutant. Red on mutation, green on original. |
| untell/scripts/io_utils.py | 290 | constant: False -> True | `interactive = False` | TTY detection fallback: tests run non-interactive so the branch is never exercised |
| untell/scripts/verify.py | 106 | boundary: < -> <= | `"passes": val < verdict_cut,` | KILLED by tests/test_detector_at_exact_cut_does_not_pass.py: fake score_text returns a detector value EXACTLY 0.45 == published verdict_cut; original passes=False, mutant True. The cut is a published constant, so exact equality is reachable — 'measure-zero' note wrong. Red on mutation, green on original. |
| untell/scripts/verify.py | 123 | constant: 4 -> 5 | `round(local["max"], 4)` | KILLED by tests/test_verify_ai_rounded_to_four_decimals.py: fake max 0.123456 -> aggregate row reports 0.1235 (4dp), mutant 0.12346 (5dp). verify()'s result rows are the published contract. Red on mutation, green on original. |
| untell/scripts/verify.py | 144 | constant: 4 -> 5 | `round(ai, 4)` | KILLED by same test (commercial case; real line is 147): fake commercial detector 0.123456 -> row 0.1235 (4dp), mutant 0.12346 (5dp). Prior 'tests use tolerant assertions' note wrong — exact values are the contract. |
| untell/scripts/verify.py | 145 | boundary: < -> <= | `"passes": ai < verdict_cut,` | KILLED by tests/test_detector_at_exact_cut_does_not_pass.py (commercial case): fake detector returns EXACTLY the caller's threshold (0.30); original passes=False, mutant True. Same exact-boundary construction as 106. |
| untell/scripts/verify.py | 149 | constant: 160 -> 161 | `str(exc)[:160]` | Error truncation length: display-only, tests don't assert exact truncation point |
| untell/scripts/verify.py | 174 | constant: False -> True | `results[key] = {"ai": None, "passes": False, ...}` | KILLED by tests/test_a_raising_detector_is_not_a_pass.py: monkeypatched commercial_detectors -> [fake detector whose score raises]; row must be {"ai": None, "passes": False, error}. Mutant reports passes:True — red on the mutation, green on original. Prior note ('test corpus never hits this branch') superseded — the branch is forced. |
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
| untell/scripts/voice.py | 156 | constant: 4 -> 5 | `"burst": round(st.pstdev(lengths) / mean_len, 4) if mean_len else 0.0,` | KILLED by tests/test_burst_rounded_to_four_decimals.py: sentence word-counts (1,1,1,2) -> burst 0.346410...; original returns 0.3464 (4dp), mutant 0.34641 (5dp). style_profile is a published per-feature dict — exact values are the API. Red on mutation, green on original. |
| untell/scripts/voice.py | 157 | constant: 100 -> 101 | `"comma_per_100w": round(text.count(",") / n_words * 100, 4),` | KILLED by tests/test_per_100w_rates_use_100_multiplier.py: 2 commas / 7 words -> 28.5714 at 100, 28.8571 at 101. style_profile is a published dict — exact values are the API. Red on mutation, green on original. |
| untell/scripts/voice.py | 160 | constant: 100 -> 101 | `"first_person_per_100w": round(len(_FIRST_PERSON.findall(text)) / n_words * 100,` | KILLED by same test: 'I went to the shop and I bought some milk.' -> 20.0 at 100, 20.2 at 101. Red on mutation, green on original. |
| untell/scripts/voice.py | 185 | logic: or -> and | `if _WARNED_THIN_SAMPLE or len(_WORD.findall(sample)) >= MIN_SAMPLE_WORDS:` | KILLED by tests/test_sufficient_voice_sample_does_not_warn.py: sufficient (200-word) sample with _WARNED=False must NOT warn; mutant falls through and logs a false 'under 150 words' warning. Red on mutation, green on original. |
| untell/scripts/voice.py | 187 | constant: True -> False | `_WARNED_THIN_SAMPLE = True` | KILLED by tests/test_thin_sample_warns_only_once.py: the flag latches after the first thin-sample warning; mutant never sets it, so the second call warns again (spamming the log). Red on mutation, green on original. |
| untell/scripts/voice.py | 218 | boundary: < -> <= | `if sample_words < MIN_SAMPLE_WORDS:` | KILLED by tests/test_sample_at_min_words_has_no_warning.py: exactly 150 words -> no warning under original; mutant fires a self-contradictory 'sample is 150 words; below 150...' warning. The boundary is the documented usable-signal point. Red on mutation, green on original. |
| untell/scripts/voice.py | 228 | boundary: < -> <= | `if abs(gap) < 0.25:` | KILLED by tests/test_gap_at_boundary_is_not_a_match.py: gap exactly 0.25 -> original 'more varied rhythm (+0.25)', mutant 'matches' (hides a real between-author distance). Pure function. Red on mutation, green on original. |
| untell/scripts/voice.py | 253 | constant: True -> False | `p.add_argument("--sample", required=True, help="file of YOUR writing (120+ words` |
| untell/scripts/voice.py | 265 | constant: 2 -> 3 | `print(json.dumps(report, ensure_ascii=True, indent=2))` |
| untell/scripts/verify.py | 139 | constant: False -> True | `results[d.name] = {"ai": None, "passes": False, "error": "detector returned NaN"` |
| untell/scripts/verify.py | 172 | constant: 4 -> 5 | `"ai": round(ai, 4),` |
| untell/scripts/verify.py | 177 | constant: False -> True | `results[key] = {"ai": None, "passes": False, "error": str(exc)[:160]}` |
| untell/scripts/verify.py | 364 | constant: 2 -> 3 | `return 2` | KILLED by tests/test_no_input_exits_two.py: read_stdin_or_none patched to None (TTY) -> main([]) exits 2, mutant exits 3. The no-input usage-error code is now pinned alongside the whitespace (368) and no-results (400) paths. Red on mutation, green on original. |
| untell/scripts/verify.py | 368 | constant: 2 -> 3 | `return 2` | KILLED by tests/test_whitespace_input_exits_two.py: main(['   ']) exits 2 (empty-input path), mutant exits 3. The no-results path (400) was already pinned; this pins the whitespace path. Red on mutation (2 failed), green on original. |
| untell/scripts/tells.py | 708 | boundary: < -> <= | `if len(words) < _MIN_WORDS_FOR_REPETITION:` | KILLED by tests/test_exactly_min_words_still_counts_repeated_trigrams.py: exactly 60 words with a repeated trigram -> original 55, mutant 0 (detector silent at its own boundary). Below-min (57 words) returns 0 under both. |
| untell/scripts/tells.py | 921 | constant: 2 -> 3 | `("diff_anchored", len(_DIFF_ANCHOR_RE.findall(body)), 2),` | KILLED by tests/test_exactly_two_diff_anchored_lines_count.py: exactly 2 diff-anchored lines -> original reports diff_anchored=2, mutant reports nothing (floor 3). The threshold boundary is the test. Red on mutation, green on original. |
| untell/scripts/tells.py | 945 | constant: 4 -> 5 | `return round((var**0.5) / mean, 4)` | KILLED by tests/test_burstiness_cv_rounded_to_four_decimals.py: sentence lengths (5,5,10) -> CV 0.353553...; original returns 0.3536 (4dp), mutant 0.35355 (5dp). The CV is a returned detector signal, not display — the exact value is part of the API. Red on mutation, green on original. |
| untell/scripts/tells.py | 1017 | DOCSTRING-PROSE (not code; mutator rewrote a docstring sentence) identity: is not -> is | ``_language_supported` below is SCRIPT-based, so Chinese is caught and German is ` |
| untell/scripts/tells.py | 1029 | DOCSTRING-PROSE logic: or -> and | `scores 0.000 and Italian scores 0.125 — so any single bar either lets German thr` |
| untell/scripts/tells.py | 1034 | DOCSTRING-PROSE logic: and -> or | `(headings, terse lists, code-heavy prose, a passage quoting German, one full of ` |
| untell/scripts/tells.py | 1035 | DOCSTRING-PROSE constant: 6 -> 7 | `German proper nouns) and 6 non-English:` |
| untell/scripts/tells.py | 1044 | DOCSTRING-PROSE identity: is not -> is | `work: the proper-noun sample scores 0.130 on other-language words and is not fla` |
| untell/scripts/tells.py | 1079 | DOCSTRING-PROSE constant: False -> True | `japanese  language_supported=False   tells_per_100w=0.00` |
| untell/scripts/tells.py | 1083 | DOCSTRING-PROSE logic: and -> or | `misleading zero, and Latin-script non-English is far the commoner case of the tw` |
| untell/scripts/tells.py | 1187 | boundary: > -> >= | `if any(start < c_end and end > c_start for c_start, c_end in claimed):` |
| untell/scripts/tells.py | 1187 | boundary: < -> <= | `if any(start < c_end and end > c_start for c_start, c_end in claimed):` |
| untell/scripts/entailment.py | 69 | KILLED by test_entailment_mutation_guards (dead-flag guard) constant: False -> True | `return False` |
| untell/scripts/entailment.py | 500 | UNKILLABLE: allowance is 10 + 10% of words (fractional); words_lost is int; > vs >= equality unreachable boundary: > -> >= | `if words_lost(source, candidate) > deletion_allowance(source):` |
| untell/scripts/entailment.py | 511 | UNKILLABLE: contradiction scores are live model calls; exact 0.5 bar is a model artifact boundary: < -> <= | `if not (sim >= relaxed_sim_bar and con < contradiction_bar and ent >= entailment` |
| untell/scripts/entailment.py | 560 | KILLED by test_entailment_mutation_guards (CLI 4dp precision) constant: 4 -> 5 | `print(_json.dumps({"available": True, "contradiction": round(con, 4),` |
| untell/scripts/roles.py | 82 | KILLED by test_roles_mutation_guards (availability) identity: is not -> is | `return _load() is not None` |
| untell/scripts/roles.py | 218 | UNKILLABLE: spaCy parse-shape mutation; existing model-gated tests pin real parses logic: or -> and | `if tok.dep_ != "prep" or tok.text.lower() not in _COMPARISON_PREPS:` |
| untell/scripts/roles.py | 269 | UNKILLABLE: spaCy parse-shape mutation; existing model-gated tests pin real parses membership: not in -> in | `if antecedent.pos_ not in ("VERB", "AUX") and antecedent.dep_ != "advcl":` |
| untell/scripts/roles.py | 273 | UNKILLABLE: self-headed token does not exist in spaCy parses identity: is not -> is | `while consequent.head is not consequent and consequent.dep_ != "ROOT" and guard ` |
| untell/scripts/roles.py | 308 | KILLED by test_roles_mutation_guards (availability) identity: is not -> is | `return _load() is not None` |
| untell/scripts/roles.py | 327 | KILLED by test_roles_mutation_guards (empty-analysis guard) logic: or -> and | `if not ta or not tb:` |
| untell/scripts/latex.py | 88 | KILLED by test_latex_mutation_guards (2-signal boundary) boundary: >= -> > | `return sum(1 for p in _LATEX_SIGNALS if p.search(text)) >= 2` |
| untell/scripts/latex.py | 102 | KILLED by test_latex_mutation_guards (3-pass unwrap bound) constant: 3 -> 4 | `for _ in range(3):  # nested \textbf{\emph{x}} needs more than one pass` |
| untell/scripts/latex.py | 194 | KILLED by test_latex_mutation_guards (missing --bib rc=2) constant: 2 -> 3 | `return 2` |
| untell/scripts/latex.py | 206 | KILLED by test_latex_mutation_guards (missing --against rc=2) constant: 2 -> 3 | `return 2` |
| untell/scripts/score.py | 338 | KILLED by test_score_mutation_guards (scoring-set equality) logic: != -> == | `if scoring != {"perplexity_burstiness"}:` |
| untell/scripts/score.py | 664 | UNKILLABLE: gpt2-mode short-circuit needs live torch runtime logic: or -> and | `if (modes or {}).get("perplexity_burstiness") == "gpt2":` |
| untell/scripts/score.py | 677 | KILLED by test_score_mutation_guards (2-sentence boundary) constant: 2 -> 3 | `if len([s for s in split_sentences(text) if s.strip()]) >= 2:` |
| untell/scripts/score.py | 751 | UNKILLABLE: per-detector round(...,4) at line 739 dominates max; 4dp vs 5dp invisible constant: 4 -> 5 | `"max": round(mx, 4),` |
| untell/scripts/score.py | 762 | KILLED by test_score_mutation_guards (exact-threshold flag) boundary: >= -> > | `result["flagged"] = bool(numeric) and mx >= verdict_threshold` |
| untell/scripts/score.py | 1129 | UNKILLABLE: detector-load guard needs specific failure shapes logic: and -> or | `and d.name not in scores` | KILLED by tests/test_scored_detector_is_not_named_missing.py — same fake-detector construction as the membership row; `or` names a scored detector as missing (1 failed under the mutation). Prior 'needs specific failure shapes' note wrong: a fake detector is the shape. |
| untell/scripts/score.py | 1129 | membership: not in -> in | `and d.name not in scores` | KILLED by tests/test_scored_detector_is_not_named_missing.py: fake detector (tier=full, unavailable, not opt-in) — in scores -> original None (correct), mutant names it as 'ran without fake_det' (inverted). Both tests red on mutation, green on original. |
| untell/scripts/score.py | 1130 | UNKILLABLE: detector-load guard needs specific failure shapes logic: and -> or | `and d.name not in _OPT_IN_DETECTORS` | KILLED by tests/test_scored_detector_is_not_named_missing.py — fake detector not in _OPT_IN_DETECTORS; `or` names a scored detector as missing (1 failed under the mutation). |
| untell/scripts/score.py | 1131 | UNKILLABLE: detector-load guard needs specific failure shapes logic: and -> or | `and not d.available()` | KILLED by tests/test_scored_detector_is_not_named_missing.py — fake detector unavailable; `or` names a scored detector as missing (1 failed under the mutation). |
| untell/scripts/score.py | 1203 | UNKILLABLE: lone-note boundary needs specific block structure boundary: < -> <= | `if len(prose) < _MIN_BLOCKS_FOR_LONE_NOTE:` | KILLED by tests/test_lone_block_warning_fires_at_exactly_min.py: exactly 3 single-sentence blocks (lone share 1.0 > 0.80) -> original fires the note, mutant None. Prior 'needs specific block structure' note wrong — 3 one-sentence paragraphs is exactly that structure. |
| untell/scripts/score.py | 1313 | KILLED by test_score_mutation_guards (unscored rc=2) constant: 2 -> 3 | `return 2 if result.get("scored") is False else 0` |
| untell/scripts/run.py | 196 | UNKILLABLE: saturation guard needs live rewrite cycle boundary: < -> <= | `if a < _SATURATED_MAX or b < _SATURATED_MAX:` | KILLED by tests/test_saturation_caveat_fires_at_exactly_max.py: pure function — at exactly 0.99 original emits the 'pinned' caveat, mutant returns None (silent). Prior 'needs live rewrite cycle' note wrong. Red on mutation, green on original. |
| untell/scripts/run.py | 910 | UNKILLABLE: no-signal pass branch needs live loop constant: False -> True | `return False` |
| untell/scripts/run.py | 1115 | UNKILLABLE: near-pool objective needs live selection boundary: <= -> < | `near = [v for v in pool if _objective(v[1], subset) <= min_score + _TELLS_EPS]` |
| untell/scripts/run.py | 1196 | UNKILLABLE: browser-tier branch needs browser scoring identity: is not -> is | `polish_tier = "lite" if browser_score is not None else tier` |
| untell/scripts/run.py | 1305 | UNKILLABLE: warning composition needs multi-condition run logic: or -> and | `if (language_warning or carried_payload or best_score.get("warning")` |
| untell/scripts/run.py | 1308 | UNKILLABLE: warning composition needs multi-condition run logic: or -> and | `or _inert_budget_warning(max_iters, best_of))` |
| untell/scripts/run.py | 1614 | KILLED by test_run_mutation_guards (env range boundaries) logic: or -> and | `if numeric is None or not (low <= numeric <= high):` |
| untell/scripts/run.py | 1676 | KILLED by test_run_mutation_guards (argparse boundary) boundary: <= -> < | `if not (low <= value <= high):` |
| untell/scripts/run.py | 1883 | UNKILLABLE: --rewriter base dispatch needs torch install logic: == -> != | `elif args.rewriter == "base":` |
| untell/scripts/run.py | 1886 | UNKILLABLE: adapter flag needs torch install constant: False -> True | `rewriter = LocalPolicyRewriter(use_adapter=False)` |
| untell/humanness.py | 75 | UNKILLABLE: warning latch, no observable output change constant: True -> False | `_WARNED_TOO_SHORT = True` |
| untell/humanness.py | 214 | KILLED by test_humanness_mutation_guards (empty-text guard) logic: or -> and | `if not text or not text.strip():` |
| untell/humanness.py | 288 | KILLED by test_humanness_mutation_guards (empty-text guard) logic: or -> and | `if not text or not text.strip():` |
| untell/humanness.py | 368 | UNKILLABLE: CV bands are continuous at every edge (mid-band formula equals neighbour at 0.35) boundary: < -> <= | `if cv < 0.35:` |
| untell/humanness.py | 370 | UNKILLABLE: CV bands continuous at 0.50 (formula gives 0 penalty) boundary: < -> <= | `elif cv < 0.50:` |
| untell/humanness.py | 372 | UNKILLABLE: CV bands continuous at 1.00 (no penalty either side) boundary: > -> >= | `elif cv > 1.0:` |
| untell/humanness.py | 605 | KILLED by test_humanness_mutation_guards (detector_max exactly 0.5) boundary: >= -> > | `if detector_max is not None and detector_max >= 0.5:` |
| untell/scripts/cli.py | 127 | KILLED by test_cli_mutation_guards (torch-notice gate) logic: != -> == | `if os.environ.get("UNTELL_LITE_NO_TORCH") != "1":` |
| untell/scripts/cli.py | 131 | UNKILLABLE: torch-presence check needs env with/without torch (env-dependent) identity: is not -> is | `if importlib.util.find_spec("torch") is not None:` |
| untell/scripts/cli.py | 212 | UNKILLABLE: demo display count needs live detector registry logic: or -> and | `ran = len(pre.get("detectors", {})) or 1` |
| untell/scripts/cli.py | 260 | UNKILLABLE: rewriter status needs a rewriter returning None logic: and -> or | `status = "✓" if rw and rw.available() else "✗"` |
| untell/scripts/cli.py | 353 | KILLED by test_cli_mutation_guards (standalone rc=2) constant: 2 -> 3 | `return 2` |
| untell/scripts/cli.py | 364 | KILLED by test_cli_mutation_guards (add_help flag) constant: False -> True | `parser = argparse.ArgumentParser(prog="untell", add_help=False, description="AI-` |
| untell/rich_output.py | 82 | UNKILLABLE: diff-tag branch, style-only logic: == -> != | `if tag == "equal":` |
| untell/rich_output.py | 205 | UNKILLABLE: delta-zero style, unobservable in plain capture boundary: < -> <= | `delta_style = "green" if delta < 0 else ("red" if delta > 0 else "white")` |
| untell/rich_output.py | 230 | KILLED by test_rich_output_mutation_guards (verdict at exact cut) boundary: >= -> > | `if p_ai >= cut:` |
| untell/rich_output.py | 232 | UNKILLABLE: borderline band edge (0.30-band), not assertion-visible boundary: >= -> > | `return "borderline" if p_ai >= cut - _VERDICT_BAND else "clear"` |
| untell/rich_output.py | 266 | KILLED by test_rich_output_mutation_guards (truncation at 2000) boundary: > -> >= | `_CONSOLE.print(_Panel(original[:2000] + ("..." if len(original) > 2000 else ""),` |
| untell/rich_output.py | 267 | KILLED by test_rich_output_mutation_guards (truncation at 2000) boundary: > -> >= | `_CONSOLE.print(_Panel(final[:2000] + ("..." if len(final) > 2000 else ""), title` |
| untell/rich_output.py | 267 | constant: 2000 -> 2001 | `_CONSOLE.print(_Panel(final[:2000] + ("..." if len(final) > 2000 else ""), title` |
| untell/rich_output.py | 271 | KILLED by test_rich_output_mutation_guards (truncation at 2000) boundary: > -> >= | `original[:2000] + ("..." if len(original) > 2000 else ""),` |
| untell/rich_output.py | 312 | UNKILLABLE: table header flag, style-only constant: True -> False | `table = _Table(show_header=True, header_style="bold")` |
| untell/rich_output.py | 316 | UNKILLABLE: count style, ANSI codes dropped in captured output constant: 3 -> 4 | `style = "red" if count >= 3 else ("yellow" if count >= 2 else "white")` | KILLED by tests/test_tell_category_count_three_renders_red.py — the prior 'ANSI codes dropped' note was wrong: the rich markup SURVIVES in the args to Table.add_row, so count 3 -> [red] vs mutant yellow is observable. Same test kills the >= -> > boundary. |
| untell/rich_output.py | 316 | boundary: >= -> > | `style = "red" if count >= 3 else ("yellow" if count >= 2 else "white")` | KILLED by tests/test_tell_category_count_three_renders_red.py: count 3 must render [red]hedging[/], count 2 [yellow] — captured via Table.add_row interception. Mutant demotes count==3 to yellow (red on mutation, green on original). |
| untell/browser_check.py | 131 | KILLED by test_browser_check_mutation_guards (24-gap boundary) constant: 24 -> 25 | `if _gap(lstart, lend, nearest.start(), nearest.end()) <= 24:` |
| untell/browser_check.py | 324 | UNKILLABLE: Playwright timeout constant needs live browser constant: 1000 -> 1001 | `page.wait_for_selector(sel, timeout=per_result * 1000)` |
| untell/mcp_server.py | 75 | KILLED by test_mcp_mutation_guards (seed 2**64-1 boundary) boundary: <= -> < | `if kind == "seed" and value is not None and not (0 <= int(value) <= 2**64 - 1):` |
| untell/mcp_server.py | 246 | UNKILLABLE: all paths converge (name-resolution, auto->None at run.py:768, identical errors) logic: and -> or | `if rewriter not in _FREE_REWRITERS and rewriter != "auto":` |
| untell/mcp_server.py | 297 | UNKILLABLE: sandbox default needs live commercial API keys constant: False -> True | `sandbox: bool = False,` |
| untell/api_server.py | 409 | UNKILLABLE: rate-window constant, timing-dependent constant: 60 -> 61 | `_RATE_WINDOW_SECONDS = 60` |
| untell/api_server.py | 428 | UNKILLABLE: bucket-cap boundary at exactly 4096, timing-dependent boundary: <= -> < | `if len(_rate_buckets) <= _RATE_BUCKET_SOFT_CAP:` |
| untell/api_server.py | 496 | UNKILLABLE: mutation falls back to client IP; TestClient reuses one IP so both paths trip identically (verified by applying mutant) logic: or -> and | `retry_after = _rate_limited(request, x_key or auth or "")` |
| untell/api_server.py | 650 | UNKILLABLE: OpenAPI additionalProperties, schema-description only constant: True -> False | `"sentences": {"type": "array", "items": {"type": "object", "additionalProperties` |
| untell/api_server.py | 682 | UNKILLABLE: OpenAPI additionalProperties, schema-description only constant: True -> False | `"results": {"type": "object", "additionalProperties": True},` |
| untell/api_server.py | 715 | UNKILLABLE: OpenAPI additionalProperties, schema-description only constant: True -> False | `"pre": {"type": "object", "additionalProperties": True, "description": "score be` |
| untell/api_server.py | 1025 | KILLED by test_api_server_mutation_guards (empty port env) logic: == -> != | `if raw is None or raw.strip() == "":` |
| untell/scripts/numerals.py | 93 | constant: 80 -> 81 | `"eighty": 80, "ninety": 90,` | KILLED by tests/test_spelled_number_dict_values_are_exact.py: _spelled_value('eighty') -> '80' original, '81' mutant. Red on mutation, green on original. |
| untell/scripts/numerals.py | 376 | constant: True -> False | `print(json.dumps({"missing": missing, "kept": not missing}, ensure_ascii=True))` |
| untell/layout.py | 156 | logic: and -> or | `if lines and lines[0].strip() == "---":` |
| untell/layout.py | 226 | logic: or -> and | `if not buffer and (line.startswith("    ") or line.startswith("\t")):` |
| untell/scripts/quality.py | 174 | logic: or -> and | `if a_empty or b_empty:` |
| untell/scripts/quality.py | 214 | identity: is not -> is | `if cos is not None:` |
| untell/scripts/quality.py | 291 | constant: 2 -> 3 | `return 2` |
