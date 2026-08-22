# wave-gate baseline — read this before trusting it

`scripts/wave_close_gate.sh` reports failures that are NOT in `wave-gate-baseline.txt`. The baseline
is therefore a list of failures someone decided to tolerate, and **every line is a debt**.

Seeded 2026-08-21 from the first full gate run on `origin/main`: 24 failed, 8819 passed, 1h35m.
Those 24 are not 24 product defects. Triaged:

## Environment, not product (the gate's own limitation)

A bare git worktree is not an installed package, and these tests spawn subprocesses or invoke
installed console scripts. VERIFIED: they pass in the ordinary tree and fail in the worktree.
Adding `PYTHONPATH` was tried and does NOT fix them.

    test_binary_stdin_clean.py (2)      test_stdin_binary_exits_two.py
    test_prove_missing_file_clean.py    test_eval_bad_file_is_a_message.py
    test_ceiling_rejects_bad_args.py (2)    test_distill_rejects_degenerate_args.py (2)
    test_fuzz_harness_fixes.py (2)      test_loop_phase_timings.py

These should shrink to zero by making the gate install into an isolated environment. Until then they
are why the gate diffs rather than counts.

## Count drift — genuine, and RED (needs a human `untell-audit --fix-counts`)

    test_docs_claims.py (2)             test_console_script_list_matches_pyproject.py (2)
    test_every_audit_check_can_fail.py (2)

Tracked in `.claude/human-queue.md`. Removing these from the baseline is the point of that run.

## Genuine defects with owners

    test_surface_parity.py[humanize]  — wave 7 added --jsonl/--inspect/--html to the CLI and not to
                                        the other surfaces. Reproduces in the ordinary tree.
    test_features.py::test_loop_scrubs_hidden_chars — FIXED in 8ed2a43 (issue #57); delete this line
                                        at the next gate run.

## Unexamined

    test_everything_registered_can_fire.py[mage] (2)   test_audit_next_contract.py
    test_reduced_ensemble_is_reported.py

Nobody has looked at these yet. They are in the baseline because the gate had to start somewhere,
NOT because they are acceptable.

**The baseline shrinking is the metric.** A baseline that only ever grows is a list of things this
project decided to stop seeing.


## 2026-08-22 — shrunk from 24 to 17

The gate reports tests that STOPPED failing, not just new ones, and that half of its output is the
half that rots. Seven entries had been fixed by this wave and were still listed:

    test_audit_next_contract ... test_recording_an_identical_row_is_refused   (1a7b7ae)
    test_console_script_list_matches_pyproject ... x2
    test_docs_claims ... x2
    test_features ... test_loop_scrubs_hidden_chars
    test_surface_parity ... [humanize]                                        (0c4ec5a)

A baseline entry is a licence to fail. Leaving a fixed test in it means the gate would absorb a
RE-break of that exact test in silence -- which is the same defect the gate was built to fix, one
level up: the first version of this gate reported 24 failures on a good commit and cried wolf, and
a stale baseline is the mirror image, crying nothing when it should.

Removed, so those seven are now load-bearing again.

Not removed and still genuine: the `mage` pair, `audit_next_contract`'s other entries, and the
environment artifacts documented above.
