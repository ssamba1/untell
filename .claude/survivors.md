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
| untell/scripts/tells.py | 708 | boundary: < -> <= | `if len(words) < _MIN_WORDS_FOR_REPETITION:` |
| untell/scripts/tells.py | 921 | constant: 2 -> 3 | `("diff_anchored", len(_DIFF_ANCHOR_RE.findall(body)), 2),` |
| untell/scripts/tells.py | 945 | constant: 4 -> 5 | `return round((var**0.5) / mean, 4)` |
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
| untell/scripts/score.py | 1129 | UNKILLABLE: detector-load guard needs specific failure shapes logic: and -> or | `and d.name not in scores` |
| untell/scripts/score.py | 1129 | membership: not in -> in | `and d.name not in scores` |
| untell/scripts/score.py | 1130 | UNKILLABLE: detector-load guard needs specific failure shapes logic: and -> or | `and d.name not in _OPT_IN_DETECTORS` |
| untell/scripts/score.py | 1131 | UNKILLABLE: detector-load guard needs specific failure shapes logic: and -> or | `and not d.available()` |
| untell/scripts/score.py | 1203 | UNKILLABLE: lone-note boundary needs specific block structure boundary: < -> <= | `if len(prose) < _MIN_BLOCKS_FOR_LONE_NOTE:` |
| untell/scripts/score.py | 1313 | KILLED by test_score_mutation_guards (unscored rc=2) constant: 2 -> 3 | `return 2 if result.get("scored") is False else 0` |
| untell/scripts/run.py | 196 | UNKILLABLE: saturation guard needs live rewrite cycle boundary: < -> <= | `if a < _SATURATED_MAX or b < _SATURATED_MAX:` |
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
| untell/rich_output.py | 316 | UNKILLABLE: count style, ANSI codes dropped in captured output constant: 3 -> 4 | `style = "red" if count >= 3 else ("yellow" if count >= 2 else "white")` |
| untell/rich_output.py | 316 | boundary: >= -> > | `style = "red" if count >= 3 else ("yellow" if count >= 2 else "white")` |
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

## 2026-08-14 me2 detector sweep 1/10: detectors/base.py (7 survivors)

| module | line | mutation | status |
|---|---|---|---|
| untell/detectors/base.py | 41 | `> 1.0` -> `>=` (clamp01) | UNKILLABLE: clamp01(1.0) identical under both comparisons |
| untell/detectors/base.py | 165 | WINDOW_WORDS 320 -> 321 | UNKILLABLE: constant shift moves every boundary; no test can pin without hardcoding the constant |
| untell/detectors/base.py | 175 | `<=` -> `<` (_split_to_width) | UNKILLABLE: boundary coincides with range-slice behavior (320<320 splits to one piece anyway) |
| untell/detectors/base.py | 219 | `<=` -> `<` (single-call) | KILLED by test_base_mutation_guards (exact-window newline preservation) |
| untell/detectors/base.py | 225 | `or` -> `and` (fallback) | UNKILLABLE: split_sentences only returns [] for text the boundary check catches first |
| untell/detectors/base.py | 239 | `>` -> `>=` (flush) | KILLED by test_base_mutation_guards (320+1 packing) |
| untell/detectors/base.py | 242 | `and` -> `or` (flush guard) | UNKILLABLE: only appends empty window that `if w.strip()` drops |
| untell/detectors/perplexity_burstiness.py | 126 | KILLED by test_pb_mutation_guards (zero-word CV exclusion) boundary: > -> >= | `lengths = [n for n in lengths if n > 0]` |
| untell/detectors/perplexity_burstiness.py | 202 | UNKILLABLE: tell-density tuning constant logic: or -> and | `density = float(score_tells(text).get("tells_per_100w") or 0.0)` |
| untell/detectors/perplexity_burstiness.py | 211 | UNKILLABLE: TTR window tuning constant constant: 100 -> 101 | `_TTR_WINDOW = 100` |
| untell/detectors/perplexity_burstiness.py | 252 | UNKILLABLE: whitespace guard; MIN-words guard catches same inputs logic: or -> and | `if not text or not text.strip():` |
| untell/detectors/perplexity_burstiness.py | 273 | KILLED by test_pb_mutation_guards (2-sentence path) constant: 2 -> 3 | `if len(nonempty) < 2:` |
| untell/detectors/perplexity_burstiness.py | 350 | UNKILLABLE: torch-gate env comparison needs live torch flip logic: == -> != | `if os.environ.get("UNTELL_LITE_NO_TORCH") == "1":` |
| untell/detectors/perplexity_burstiness.py | 357 | UNKILLABLE: _torch_ready availability constant constant: True -> False | `return True` |
| untell/detectors/perplexity_burstiness.py | 383 | UNKILLABLE: GPT-2 tokenizer kwargs, model-dependent constant: False -> True | `enc = tok(text, return_tensors="pt", return_offsets_mapping=True, verbose=False)` |
| untell/detectors/perplexity_burstiness.py | 386 | UNKILLABLE: GPT-2 chunk threshold (both), model-dependent constant: 2 -> 3 | `if total < 2:` |
| untell/detectors/perplexity_burstiness.py | 386 | boundary: < -> <= | `if total < 2:` |
| untell/detectors/perplexity_burstiness.py | 405 | UNKILLABLE: GPT-2 span boundary, model-dependent boundary: >= -> > | `if end >= total:` |
| untell/detectors/perplexity_burstiness.py | 409 | UNKILLABLE: GPT-2 chunk join, model-dependent boundary: > -> >= | `nll = torch.cat(chunks) if len(chunks) > 1 else chunks[0]` |
| untell/detectors/perplexity_burstiness.py | 442 | UNKILLABLE: GPT-2 idx guard, model-dependent boundary: < -> <= | `if idx < 0:` |
| untell/detectors/perplexity_burstiness.py | 451 | UNKILLABLE: GPT-2 per-sentence threshold, model-dependent boundary: >= -> > | `if len(per_sent) >= 2:` |
| untell/detectors/perplexity_burstiness.py | 525 | KILLED by test_pb_mutation_guards (exact-MIN abstain, both twins) boundary: < -> <= | `if len(_WORD.findall(text)) < _MIN_WORDS_FOR_SIGNAL:` |
| untell/detectors/mage.py | 25 | constant: False -> True | `_warned = False` | UNKILLABLE: module flag initializer, reset by every test setup
| untell/detectors/mage.py | 26 | constant: False -> True | `_dead = False  # set once a load fails so we never re-attempt the heavy import p` | UNKILLABLE: _dead initializer; tests set it explicitly so class default is masked
| untell/detectors/mage.py | 41 | constant: False -> True | `return False` | UNKILLABLE: torch-import branch needs a torch-less env
| untell/detectors/mage.py | 64 | logic: or -> and | `i2l = raw.get("id2label") or {}` | UNKILLABLE: id2label config parse, needs live snapshot_download
| untell/detectors/mage.py | 65 | logic: and -> or | `if not (i2l and all(isinstance(v, str) for v in i2l.values())):` | UNKILLABLE: config validation, needs live model dir
| untell/detectors/mage.py | 69 | constant: 2 -> 3 | `raw["num_labels"] = 2` | UNKILLABLE: num_labels rewrite in config fix, needs live load
| untell/detectors/mage.py | 88 | constant: True -> False | `MageDetector._dead = True` | UNKILLABLE: _dead latch in except path; requires a load failure with live HF
| untell/detectors/mage.py | 95 | constant: True -> False | `MageDetector._warned = True` | UNKILLABLE: _warned flag in except path, same
| untell/detectors/mage.py | 102 | constant: 1024 -> 1025 | `inputs = tok(window, return_tensors="pt", truncation=True, max_length=1024)` | UNKILLABLE: tokenizer max_length 1024, model-dependent
| untell/detectors/mage.py | 102 | constant: True -> False | `inputs = tok(window, return_tensors="pt", truncation=True, max_length=1024)` |
| untell/detectors/mage.py | 112 | logic: or -> and | `if "machine" in str(v).lower() or str(v).lower() in ("label_0", "ai", "fake")` | UNKILLABLE: ai_idx label regex needs live model.config
| untell/detectors/mage.py | 121 | logic: or -> and | `if "human" in str(v).lower() or str(v).lower() in ("label_1", "real")` | UNKILLABLE: human_idx label regex needs live model.config
| untell/detectors/mage.py | 127 | constant: 700 -> 701 | `p = windowed_max(text, lambda w: 1.0 - float(_probs(w)[human_idx]), 700)` | UNKILLABLE: window 700 constant, model-dependent
| untell/detectors/mage.py | 129 | constant: 700 -> 701 | `p = windowed_max(text, lambda w: float(_probs(w)[ai_idx]), 700)` | UNKILLABLE: window 700 constant, model-dependent
| untell/detectors/fast_detectgpt.py | 63 | constant: False -> True | `_dead = False` | UNKILLABLE: _dead initializer; tests set explicitly
| untell/detectors/fast_detectgpt.py | 64 | constant: False -> True | `_warned = False` | UNKILLABLE: _warned initializer
| untell/detectors/fast_detectgpt.py | 71 | constant: False -> True | `return False` | UNKILLABLE: available() torch-import branch needs torch-less env
| untell/detectors/fast_detectgpt.py | 72 | constant: True -> False | `return True` | UNKILLABLE: available() True return, torch presence assumed
| untell/detectors/fast_detectgpt.py | 92 | constant: True -> False | `FastDetectGPTDetector._dead = True` | UNKILLABLE: _dead latch in except path, needs live load failure
| untell/detectors/fast_detectgpt.py | 99 | constant: True -> False | `FastDetectGPTDetector._warned = True` | UNKILLABLE: _warned flag in except path
| untell/detectors/fast_detectgpt.py | 102 | constant: True -> False | `enc = tok(window, return_tensors="pt", truncation=True, max_length=512)` | UNKILLABLE: tokenizer max_length 512 (both), model-dependent
| untell/detectors/fast_detectgpt.py | 102 | constant: 512 -> 513 | `enc = tok(window, return_tensors="pt", truncation=True, max_length=512)` |
| untell/detectors/fast_detectgpt.py | 104 | boundary: < -> <= | `if ids.shape[1] < 2:` | UNKILLABLE: ids.shape guard needs live tokenizer output
| untell/detectors/fast_detectgpt.py | 117 | constant: 8 -> 9 | `discrepancy = ((actual - mean_ref) / torch.sqrt(var_ref + 1e-8)).mean().item()` | UNKILLABLE: var epsilon 1e-8 in torch path, model-dependent
| untell/scripts/audit.py | 227 | logic: == -> != | `int(found) == expected,` | KILLED by test_audit_mutation_guards (registry-count comparison)
| untell/scripts/audit.py | 619 | constant: 435 -> 436 | `These are the numbers the competitive claims rest on, and they were written by r` | UNKILLABLE: comment prose
| untell/scripts/audit.py | 623 | identity: is not -> is | `is not much; a number nobody can re-derive is, because there is no way to tell a` | UNKILLABLE: comment prose
| untell/scripts/audit.py | 715 | logic: and -> or | `printing if the sizes behind it are right — and they are the easiest thing in an` | UNKILLABLE: comment prose
| untell/scripts/audit.py | 720 | constant: 68 -> 69 | `decimal place, so the doc is not forced to print 68,545 to pass.` | UNKILLABLE: comment prose
| untell/scripts/audit.py | 724 | logic: and -> or | `130, 135 and 138 against a published 139 — so the pages now say so, and the chec` | UNKILLABLE: comment prose
| untell/scripts/audit.py | 759 | logic: and -> or | `Written because a page claimed "four of the eight largest repos in the field" an` | UNKILLABLE: comment prose
| untell/scripts/audit.py | 859 | identity: is not -> is | `Collection is not free (about ten seconds) and not constant: it depends on which` | UNKILLABLE: comment prose
| untell/scripts/audit.py | 878 | logic: and -> or | `check would fail on a correct machine — and a check that fails on correct machin` | UNKILLABLE: comment prose
| untell/scripts/audit.py | 882 | identity: is not -> is | `here, which is not drift but abandonment: the docs said 1868 and 2473 while the ` | UNKILLABLE: comment prose
| untell/scripts/audit.py | 1154 | logic: and -> or | `own unhelpful "does not provide the extra" — and the person hitting it is follow` | UNKILLABLE: comment prose
| untell/scripts/audit.py | 1193 | logic: and -> or | ```CITATION.cff`` said 0.1.0 while ``pyproject.toml`` and ``untell.__version__`` ` | UNKILLABLE: comment prose
| untell/scripts/audit.py | 1312 | logic: and -> or | `UNTELL_TIER, UNTELL_THRESHOLD, UNTELL_REWRITER, UNTELL_STYLE and UNTELL_BEST_OF ` | UNKILLABLE: comment prose
| untell/scripts/audit.py | 1346 | logic: and -> or | `the three built-in demo paragraphs and 4.22 -> 3.81 on HC3. Worse, the document ` | UNKILLABLE: comment prose
| untell/scripts/audit.py | 1474 | constant: 2 -> 3 | `indent=2,` | UNKILLABLE: JSON indent cosmetic (indent=2->3)
| untell/scripts/audit.py | 1551 | logic: and -> or | `return 0 if (not report.failures and not report.unattributed) else 1` | KILLED by test_audit_mutation_guards (exit code with failures)
| untell/detectors/binoculars.py | 38 | constant: False -> True | `return False` | UNKILLABLE: torch-import branch needs torch-less env
| untell/detectors/binoculars.py | 43 | constant: False -> True | `return False` | UNKILLABLE: CUDA check needs a GPU-less machine
| untell/detectors/binoculars.py | 67 | logic: or -> and | `if not self.available() or not text.strip():` | UNKILLABLE: available() gate needs no-CUDA env; empty-text caught by same guard
| untell/detectors/binoculars.py | 83 | constant: True -> False | `enc = tok(text, return_tensors="pt", truncation=True, max_length=512).to(device)` | UNKILLABLE: tokenizer max_length 512 (both), model-dependent
| untell/detectors/binoculars.py | 83 | constant: 512 -> 513 | `enc = tok(text, return_tensors="pt", truncation=True, max_length=512).to(device)` |
| untell/detectors/binoculars.py | 85 | boundary: < -> <= | `if ids.shape[1] < 2:` | UNKILLABLE: ids.shape guard needs live tokenizer
| untell/detectors/binoculars.py | 101 | constant: 8 -> 9 | `binoculars = float(log_ppl / (x_ppl + 1e-8))` | UNKILLABLE: epsilon 1e-8 in torch path
| untell/detectors/hc3_roberta.py | 27 | constant: False -> True | `_dead = False` | UNKILLABLE: model/env-dependent (dead/warned latch, torch branch, tokenizer kwarg)
| untell/detectors/hc3_roberta.py | 28 | constant: False -> True | `_warned = False` | UNKILLABLE: model/env-dependent (dead/warned latch, torch branch, tokenizer kwarg)
| untell/detectors/hc3_roberta.py | 35 | constant: False -> True | `return False` | UNKILLABLE: model/env-dependent (dead/warned latch, torch branch, tokenizer kwarg)
| untell/detectors/hc3_roberta.py | 36 | constant: True -> False | `return True` | UNKILLABLE: model/env-dependent (dead/warned latch, torch branch, tokenizer kwarg)
| untell/detectors/hc3_roberta.py | 58 | constant: True -> False | `HC3RobertaDetector._dead = True` | UNKILLABLE: model/env-dependent (dead/warned latch, torch branch, tokenizer kwarg)
| untell/detectors/hc3_roberta.py | 65 | constant: True -> False | `HC3RobertaDetector._warned = True` | UNKILLABLE: model/env-dependent (dead/warned latch, torch branch, tokenizer kwarg)
| untell/detectors/hc3_roberta.py | 68 | constant: True -> False | `inputs = tok(window, return_tensors="pt", truncation=True, max_length=512)` | UNKILLABLE: model/env-dependent (dead/warned latch, torch branch, tokenizer kwarg)
| untell/detectors/hc3_roberta.py | 68 | constant: 512 -> 513 | `inputs = tok(window, return_tensors="pt", truncation=True, max_length=512)` |
| untell/detectors/roberta_openai.py | 24 | constant: False -> True | `_dead = False` | UNKILLABLE: model/env-dependent (dead/warned latch, torch branch, tokenizer kwarg)
| untell/detectors/roberta_openai.py | 25 | constant: False -> True | `_warned = False` | UNKILLABLE: model/env-dependent (dead/warned latch, torch branch, tokenizer kwarg)
| untell/detectors/roberta_openai.py | 32 | constant: False -> True | `return False` | UNKILLABLE: model/env-dependent (dead/warned latch, torch branch, tokenizer kwarg)
| untell/detectors/roberta_openai.py | 33 | constant: True -> False | `return True` | UNKILLABLE: model/env-dependent (dead/warned latch, torch branch, tokenizer kwarg)
| untell/detectors/roberta_openai.py | 43 | constant: True -> False | `truncation=True,` | UNKILLABLE: model/env-dependent (dead/warned latch, torch branch, tokenizer kwarg)
| untell/detectors/roberta_openai.py | 44 | constant: 512 -> 513 | `max_length=512,` | UNKILLABLE: model/env-dependent (dead/warned latch, torch branch, tokenizer kwarg)
| untell/detectors/roberta_openai.py | 58 | constant: True -> False | `RobertaOpenAIDetector._dead = True` | UNKILLABLE: model/env-dependent (dead/warned latch, torch branch, tokenizer kwarg)
| untell/detectors/roberta_openai.py | 65 | constant: True -> False | `RobertaOpenAIDetector._warned = True` | UNKILLABLE: model/env-dependent (dead/warned latch, torch branch, tokenizer kwarg)
| untell/detectors/radar.py | 35 | constant: False -> True | `_warned = False` | UNKILLABLE: _warned initializer
| untell/detectors/radar.py | 38 | logic: or -> and | `if not (os.environ.get("UNTELL_ENABLE_RADAR") or os.environ.get("HUMANIZE_ENABLE` | UNKILLABLE: env-gate logic needs real env flip
| untell/detectors/radar.py | 39 | constant: False -> True | `return False  # opt-in only (non-commercial license)` | UNKILLABLE: opt-in return constant
| untell/detectors/radar.py | 44 | constant: False -> True | `return False` | UNKILLABLE: torch-import branch
| untell/detectors/radar.py | 45 | constant: True -> False | `return True` | UNKILLABLE: available() True return
| untell/detectors/radar.py | 59 | logic: or -> and | `if not self.available() or not text.strip():` | KILLED by test_radar_mutation_guards (opt-out must prevent 7B model load - MEASURED: mutation loaded model and scored 0.993)
| untell/detectors/radar.py | 66 | constant: True -> False | `RadarDetector._warned = True` | UNKILLABLE: _warned flag in except path
| untell/detectors/radar.py | 73 | constant: True -> False | `inputs = tok(window, return_tensors="pt", truncation=True, max_length=512)` | UNKILLABLE: tokenizer max_length 512 (both)
| untell/detectors/radar.py | 73 | constant: 512 -> 513 | `inputs = tok(window, return_tensors="pt", truncation=True, max_length=512)` |
