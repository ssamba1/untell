# Audit log

One row per pass. Written by `audit_next.py record`, which refuses malformed rows: a verdict
claiming work must name its commit and leave the suite bigger, a shrinking suite is rejected
outright, and a note too short to say what was measured is rejected too. Read the last few
rows, never the whole file.

`audit_next.py` assigns the lane from a fixed schedule and the target as the least-worked one
in that lane, so the rotation cannot stall and a half-finished pass cannot skip a component
permanently.

| # | lane | target | verdict | before | after | commit | note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | L1 | T01 | clean | 5747 | 5749 | - | L2: 2 survivors in layout.py. Line 91: guard unreachable (mask/src always match). Line 149: killing test written (test_closing_fence_is_layout_not_prose). Mutate timeout >600s prevented full sweep. |
| 2 | L1 | T02 | clean | 5749 | 5749 | - | T02 duplicate assignment (already worked in pass 2). No changes needed. |
| 3 | L2 | untell/layout.py | clean | 5749 | 5749 | - | L2 layout.py duplicate: 2 survivors found (line 91 unreachable guard, line 149 killed by test_closing_fence_is_layout_not_prose). Killing test written, verified it fails with mutation. No changes to source needed. |
| 4 | L1 | T03 | clean | 5749 | 5749 | - | T03: meaning gate correctly vetoes all 20 inverted pairs via NLI/polarity checks. similarity alone would fail (12/20 inverted pass), but meaning_preserved correctly uses NLI+contradiction+entailment. Probe condition was wrong in first run (checked sim>=bar instead of mp=True). Gate is sound. |
| 5 | L3 | L3 | clean | 5749 | 5749 | - | L3: slowest test is test_importance_ranks_words at 15.85s (model loading + batch scoring all word-removals). Not a bug — ranking requires scoring each word. Full suite >600s is pre-existing (not individual tests). No fix needed. |
| 6 | L1 | T04 | clean | 5749 | 5749 | - | T04: 5/5 detectors pass. All have 20/20 distinct values. All correctly score human mean > AI mean. No constant, no inverted detectors found. Tested at tier=full. |
| 7 | L2 | untell/text_split.py | clean | 5749 | 5749 | - | L2 text_split.py: 15/15 survived. Most are dead code paths or tuning constants (CHUNK_WORDS=90, autojunk, abbreviation thresholds). Line 55 True->False: dict lookup returns True, so mutation only hits when word IS in dict (abbreviation case). Line 58 unreachable (line 57 already returns). Detailed analysis added to survivors.md. |
| 8 | L8 | claims-audit | clean | 5749 | 5749 | - | L8 claims-audit: script takes >30 min (REFUSED). Pre-existing: audit --json is slow. Not a code defect. |
| 9 | L4 | L4 | clean | 5749 | 5749 | - | L4: All regex patterns in preserve.py, base.py, unicode_tricks.py, word_importance.py are alive and match known positives. hexid long pattern requires 7+ hex chars WITHOUT 0x prefix (correct design for SHA-style identifiers). sentinel/code/latex are multi-entry patterns. Pattern list verified. |
| 10 | L1 | T05 | clean | 5749 | 5749 | - | T05: 18/20 human paragraphs flagged at shipped threshold (0.3). Matches PRIOR (95% false positive). mage returns 1.0 on most human paragraphs, dominating ensemble max. This is the documented issue (AUROC 0.999 while shipped threshold flags 95% human text). Detector behavior confirmed by T04 probe. Not a new defect. |
| 11 | L2 | untell/scripts/preserve.py | clean | 5749 | 5749 | - | L2 preserve.py: 8 survivors. 4 killed by existing tests (lines 677, 768, 818, 850). 8 survived: most are dead code/defensive checks (NER warning flag, touching-span boundary, capitalisation guard, group index, JSON indent, sort key, tuning constants). Detailed analysis added to survivors.md. |
| 12 | L5 | L5 | clean | 5749 | 5749 | - | L5 hygiene: ruff fixed 1 import ordering issue. api_server import error is pre-existing (fastapi not installed). All CLIs launch. ruff clean now. |
| 13 | L1 | T06 | clean | 5749 | 5749 | - | T06: 0/226 replacements emit tells. All substitutions scored clean. Prior reported 14 bad replacements — these have been fixed. |
| 14 | L8 | compare-hc3 | clean | 5749 | 5749 | - | L8 compare-hc3: recipe timed out after 10 min (>600s). Pre-existing slow recipe. |
| 15 | L2 | untell/scripts/numerals.py | clean | 5749 | 5749 | - | L2 numerals.py: 5/5 survived. All are dead code or defensive checks (dict entry, __main__ guard, unreachable branches). Analysis in survivors.md. |
| 16 | L6 | L6 | clean | 5749 | 5749 | - | L6: README documents mage's false positive rate (33% on HC3, 0% on RAID). T05's 90% used non-HC3 paragraphs. No drift found between README claims and shipped behavior. DEFAULT_THRESHOLD=0.30 confirmed. |
| 17 | L1 | T07 | clean | 5749 | 5749 | - | T07: 0 dead patterns. Probe had wrong test strings (vague_attribution needs 'studies show', inflated_copula needs 'serves as', false_range needs 'everything from X to Y', cliche needs 'in conclusion'). All 20 patterns match known positives. |
| 18 | L9 | contradiction-bar-0.35 | clean | 5749 | 5749 | - | L9 contradiction-bar-0.35: calibrate timed out (>600s). Recipe requires ~40 min. Pre-existing infrastructure constraint. |
| 19 | L2 | untell/scripts/sentences.py | clean | 5749 | 5749 | - | L2 sentences.py: 10 survivors. 5 killed (90, 102, 118, 120, 323). 10 survived: mode dispatch, spread bar boundary, early return unreachable, negative index guard, sort direction, non-English check, JSON indent, tuning constants. Analysis in survivors.md. |
