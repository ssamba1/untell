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
