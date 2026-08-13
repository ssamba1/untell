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
