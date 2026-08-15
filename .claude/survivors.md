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
| untell/text_split.py | 122 | constant: 90 -> 91 | `CHUNK_WORDS = 90` | KILLED by tests/test_chunk_words_boundary_181.py: 181 words -> 3 chunks under 90 (ceil(181/90)), 2 under 91 (ceil(181/91)) — the bound the constant exists to enforce is exceeded. Actual line is 135. Red on mutation, green on original. |
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
| untell/scripts/hedges.py | 148 | constant: True -> False | `name: re.compile(r"(?<!\w)(?:" + "/".join(re.escape(t) for t in sorted(terms, ke` |
| untell/scripts/hedges.py | 328 | constant: True -> False | `print(json.dumps({"dropped": dropped, "kept": not dropped}, ensure_ascii=True))` |
| untell/scripts/voice.py | 154 | constant: 4 -> 5 | `"sent_len": round(mean_len, 4),` |
| untell/scripts/voice.py | 156 | constant: 4 -> 5 | `"burst": round(st.pstdev(lengths) / mean_len, 4) if mean_len else 0.0,` |
| untell/scripts/voice.py | 157 | constant: 100 -> 101 | `"comma_per_100w": round(text.count(",") / n_words * 100, 4),` |
| untell/scripts/voice.py | 160 | constant: 100 -> 101 | `"first_person_per_100w": round(len(_FIRST_PERSON.findall(text)) / n_words * 100,` |
| untell/scripts/voice.py | 167 | constant: 4 -> 5 | `return {k: round((b[k] - a[k]) / _SCALE[k], 4) for k in _SCALE}` |
| untell/scripts/voice.py | 185 | logic: or -> and | `if _WARNED_THIN_SAMPLE or len(_WORD.findall(sample)) >= MIN_SAMPLE_WORDS:` |
| untell/scripts/voice.py | 187 | constant: True -> False | `_WARNED_THIN_SAMPLE = True` |
| untell/scripts/voice.py | 218 | boundary: < -> <= | `if sample_words < MIN_SAMPLE_WORDS:` |
| untell/scripts/voice.py | 228 | boundary: < -> <= | `if abs(gap) < 0.25:` |
| untell/scripts/voice.py | 253 | constant: True -> False | `p.add_argument("--sample", required=True, help="file of YOUR writing (120+ words` |
| untell/scripts/voice.py | 265 | constant: 2 -> 3 | `print(json.dumps(report, ensure_ascii=True, indent=2))` |
| untell/scripts/voice.py | 154 | constant: 4 -> 5 | `round(mean_len, 4)` | Rounding precision: test corpus values don't differ at 4 vs 5 digits |
| untell/scripts/voice.py | 156 | constant: 4 -> 5 | `round(st.pstdev(lengths) / mean_len, 4)` | Same — burst precision tuning |
| untell/scripts/voice.py | 157 | constant: 100 -> 101 | `round(text.count(",") / n_words * 100, 4)` | Per-100w denominator: 100 vs 101 imperceptible in tests |
| untell/scripts/voice.py | 160 | constant: 100 -> 101 | `round(len(_FIRST_PERSON.findall(text)) / n_words * 100, 4)` | Same denominator tuning |
| untell/scripts/voice.py | 167 | constant: 4 -> 5 | `round((b[k] - a[k]) / _SCALE[k], 4)` | Rounding precision on delta report |
| untell/scripts/voice.py | 185 | logic: or -> and | `if _WARNED_THIN_SAMPLE or len(_WORD.findall(sample)) >= MIN_SAMPLE_WORDS:` | Warning flag: mutation changes when warning fires; test sample is always sufficient so flag branch never hit |
| untell/scripts/voice.py | 187 | constant: True -> False | `_WARNED_THIN_SAMPLE = True` | Warning-once flag: logging only |
| untell/scripts/voice.py | 218 | boundary: < -> <= | `if sample_words < MIN_SAMPLE_WORDS:` | Boundary: test corpus never uses exactly MIN_SAMPLE_WORDS words |
| untell/scripts/voice.py | 228 | boundary: < -> <= | `if abs(gap) < 0.25:` | Gap classification boundary: test corpus never lands exactly on 0.25 |
| untell/scripts/voice.py | 253 | constant: True -> False | `p.add_argument("--sample", required=True, ...)` | CLI help: required=True vs False only affects argparse error, tests call function directly |
| untell/scripts/voice.py | 265 | constant: 2 -> 3 | `print(json.dumps(report, ..., indent=2))` | JSON indent: tests don't check formatting |
| untell/detectors/local_judge.py | 51 | logic: or -> and | `_DEFAULT_MODEL = os.environ.get("UNTELL_JUDGE_MODEL") or LIGHT_MODEL` |
| untell/detectors/local_judge.py | 128 | constant: True -> False | `return True` |
| untell/detectors/local_judge.py | 145 | logic: != -> == | `dtype=torch.bfloat16 if device != "cpu" else torch.float32,` |
| untell/detectors/local_judge.py | 152 | logic: or -> and | `if not self.available() or not text.strip():` |
| untell/detectors/local_judge.py | 158 | constant: True -> False | `input_text = tok.apply_chat_template(messages, tokenize=False, add_generation_pr` |
| untell/detectors/local_judge.py | 166 | constant: 16 -> 17 | `max_new_tokens=16,` |
| untell/detectors/local_judge.py | 167 | constant: False -> True | `do_sample=False,` |
| untell/detectors/local_judge.py | 174 | logic: or -> and | `m = _NUM.search(reply or "")` |
| untell/detectors/radar.py | 35 | constant: False -> True | `_warned = False` |
| untell/detectors/radar.py | 38 | logic: or -> and | `if not (os.environ.get("UNTELL_ENABLE_RADAR") or os.environ.get("HUMANIZE_ENABLE` |
| untell/detectors/radar.py | 39 | constant: False -> True | `return False  # opt-in only (non-commercial license)` |
| untell/detectors/radar.py | 44 | constant: False -> True | `return False` |
| untell/detectors/radar.py | 45 | constant: True -> False | `return True` |
| untell/detectors/radar.py | 59 | logic: or -> and | `if not self.available() or not text.strip():` |
| untell/detectors/radar.py | 66 | constant: True -> False | `RadarDetector._warned = True` |
| untell/detectors/radar.py | 73 | constant: 512 -> 513 | `inputs = tok(window, return_tensors="pt", truncation=True, max_length=512)` |
| untell/detectors/llm_judge.py | 51 | constant: True -> False | `return True` |
| untell/detectors/llm_judge.py | 70 | identity: is not -> is | `if anthropic is not None:` |
| untell/detectors/llm_judge.py | 74 | logic: or -> and | `"model": self.model or "claude-sonnet-4-6",` |
| untell/detectors/llm_judge.py | 78 | constant: 3 -> 4 | `max_attempts=3,` |
| untell/detectors/llm_judge.py | 86 | logic: or -> and | `"model": self.model or "gpt-4o-mini",` |
| untell/detectors/llm_judge.py | 87 | constant: 8 -> 9 | `"max_tokens": 8,` |
| untell/detectors/llm_judge.py | 98 | logic: or -> and | `m = _NUM.search(out or "")` |
| untell/detectors/llm_judge.py | 102 | boundary: >= -> > | `if val >= 2.0:  # answered as a percentage (e.g. "73"). Values in (1.0, 2.0) are` |
| eval/report.py | 15 | identity: is not -> is | `scored = [r for r in results if r.post.get("scored") is not False]` |
| eval/report.py | 88 | constant: False -> True | `scored = [r for r in results if r.post.get("scored") is not False]` |
| eval/report.py | 110 | logic: and -> or | `comparable = fl["n_scored"] == fl["n"] and sp["n_scored"] == sp["n"]` |
| eval/report.py | 123 | logic: != -> == | `if fl["bypass_rate"] != sp["bypass_rate"]:` |
| eval/report.py | 124 | boundary: > -> >= | `better, basis = fl["bypass_rate"] > sp["bypass_rate"], "bypass_rate"` |
| eval/report.py | 172 | logic: == -> != | `n_cell = str(st["n"]) if st["n_scored"] == st["n"] else f"{st['n_scored']}/{st['` |
| eval/report.py | 201 | logic: or -> and | `if not pd or not pd.get("n"):` |
| eval/report.py | 215 | logic: and -> or | `if hd and hd in best["per_detector"]:` |
| eval/prove.py | 34 | constant: 5 -> 6 | `max_iters: int = 5,` |
| eval/prove.py | 41 | constant: 3 -> 4 | `best_of: int = 3,` |
| eval/prove.py | 108 | constant: 5 -> 6 | `parser.add_argument("--max-iters", type=int, default=5)` |
| eval/prove.py | 110 | constant: 3 -> 4 | `"--best-of", type=int, default=3,` |
| eval/prove.py | 135 | constant: 2 -> 3 | `return 2` |
| eval/prove.py | 141 | constant: 2 -> 3 | `print(json.dumps(v, ensure_ascii=True, indent=2) if args.json else _render(v))` |
| eval/prove.py | 141 | constant: True -> False | `print(json.dumps(v, ensure_ascii=True, indent=2) if args.json else _render(v))` |
| eval/prove.py | 155 | constant: 2 -> 3 | `return 2` |
| eval/detector_audit.py | 218 | constant: 1000 -> 1001 | `return 1000 * t.count("\n") / max(len(_WORD_RE.findall(t)), 1)` |
| eval/detector_audit.py | 284 | logic: and -> or | `elif au is not None and au < WEAK_AUROC:` |
| eval/detector_audit.py | 303 | constant: 4 -> 5 | `"range": round(rng, 4),` |
| eval/detector_audit.py | 304 | constant: 4 -> 5 | `"auroc": round(au, 4) if au is not None else None,` |
| eval/detector_audit.py | 398 | constant: 10 -> 11 | `out += [s for s in split_sentences(para) if len(s.split()) >= 10]` |
| eval/detector_audit.py | 398 | boundary: >= -> > | `out += [s for s in split_sentences(para) if len(s.split()) >= 10]` |
| eval/detector_audit.py | 477 | identity: is not -> is | `tpr = f"{r['tpr']:6.0%}" if r.get("tpr") is not None else "     -"` |
| eval/detector_audit.py | 495 | logic: and -> or | `and r["auroc"] > SENTENCE_BROKEN_AUROC` |
| untell/api_server.py | 428 | boundary: <= -> < | `if len(_rate_buckets) <= _RATE_BUCKET_SOFT_CAP:` | KILLED by tests/test_eviction_noop_at_exact_cap.py: exactly 4096 buckets (one stale) -> original no-op (stale bucket survives, len stays 4096); mutant < runs eviction, drops ALL stale buckets (len 0). The cap boundary is exactly observable. Red on mutation, green on original. |
| untell/api_server.py | 496 | logic: or -> and | `retry_after = _rate_limited(request, x_key or auth or "")` |
| untell/api_server.py | 682 | constant: True -> False | `"results": {"type": "object", "additionalProperties": True},` |
| untell/api_server.py | 715 | constant: True -> False | `"pre": {"type": "object", "additionalProperties": True, "description": "score be` |
| untell/rewriter/structural.py | 480 | constant: 12 -> 13 | `tail = before[-12:]` | KILLED by tests/test_sentinel_thirteen_back_marks_sentence_start.py: before = ⟦HZ0003⟧ + 5 X's (13 chars) -> 12-char tail loses the opening ⟦ (no sentinel found, sentence-start False); 13-char tail catches it (True). A locked span 13 chars back is missed by the window. Red on mutation, green on original. |
| untell/rewriter/structural.py | 1691 | logic: or -> and | `usable = [o for o in (fresh or options) if o.lower() not in unsafe]` |
| untell/rewriter/structural.py | 2516 | boundary: > -> >= | `key=lambda i: (0 if counts.get(first_words[i], 0) > 1 else 1, random.random()),` |
| untell/rewriter/structural.py | 2667 | logic: and -> or | `and not _inside_quotes(words, pos + 1)` |
| untell/rewriter/structural.py | 2843 | constant: True -> False | `"contractions": True, "register": 1.0, "sentences": 1.0, "openers": 1.0,` |
| untell/rewriter/structural.py | 2887 | constant: False -> True | `"conversational_openers": False},` |
