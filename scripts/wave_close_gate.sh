#!/usr/bin/env bash
# Wave-close gate: is origin/main actually green?
#
# WHY THIS EXISTS. Wave 7 pushed a main on which every call to `untell_text` raised NameError. The
# suite caught it — tests/test_an_inert_budget_says_so.py fails in 2.3s against that commit, and it
# predates the defect. What failed was the PROTOCOL: in a 20-agent wave a red test is
# indistinguishable from ordinary concurrent churn, an agent correctly attributed the failure to a
# sibling mid-edit, and nothing re-checked main afterwards. The post-wave sweep ran only the wave's
# NEW test files, from the WORKING TREE, after the fix had landed — so it could not have caught it
# either. See issue #52.
#
# Two properties make this a gate rather than a formality:
#   1. CLEAN CHECKOUT of origin/main. The working tree contains uncommitted sibling work and is
#      exactly where a "is main ok?" check fools itself. This is the same mistake the holdout
#      harness made with its env gate, one layer up.
#   2. THE WHOLE FAST SUITE, not the wave's new files. The wave's own tests are the ones most likely
#      to be green, because their author just ran them.
#
# Usage:  bash scripts/wave_close_gate.sh          # gate origin/main
#         bash scripts/wave_close_gate.sh <ref>    # gate any ref
set -uo pipefail

REF="${1:-origin/main}"
REPO="$(git rev-parse --show-toplevel)"
PY="$REPO/.venv/Scripts/python.exe"
[ -x "$PY" ] || PY="python"
WT="$(mktemp -d)/wave-gate"

cleanup() { git -C "$REPO" worktree remove --force "$WT" >/dev/null 2>&1 || true; }
trap cleanup EXIT

git -C "$REPO" fetch -q origin || echo "warning: fetch failed; gating whatever $REF resolves to locally"
git -C "$REPO" worktree add -q --detach "$WT" "$REF" || { echo "GATE ERROR: cannot check out $REF"; exit 2; }

echo "gating $REF at $(git -C "$WT" rev-parse --short HEAD) in a clean checkout"
cd "$WT" || exit 2

# A BARE WORKTREE IS NOT AN INSTALLED PACKAGE, and a chunk of this suite needs one. MEASURED, twice:
#   - first gate run on origin/main: 24 failed / 8819 passed
#   - the same tests in the ordinary tree: test_binary_stdin_clean.py and
#     test_prove_missing_file_clean.py PASS
#   - adding PYTHONPATH="$WT" did NOT fix it (still 3 failed, FileNotFoundError) — those tests
#     invoke installed console scripts, which no amount of import path fixes
# `pip install -e .` here is not an option: it would repoint the developer's editable install at a
# temp directory this script deletes on exit.
#
# So the gate cannot ask "are there failures?" — in this environment there always are, and a check
# that is permanently red is the exact failure #20 was about. It asks the answerable question
# instead: ARE THERE FAILURES THAT WERE NOT THERE BEFORE? Environmental noise is identical between
# two runs and cancels; a regression does not.
#
# The baseline is a file of test ids, written on first run and updated deliberately. A baseline
# containing genuinely-broken tests is a hazard, so it is stored in the repo where it can be read,
# argued with, and shrunk — not hidden in a temp directory.
export PYTHONPATH="$WT${PYTHONPATH:+:$PYTHONPATH}"
BASELINE="$REPO/.claude/wave-gate-baseline.txt"

UNTELL_LITE_NO_TORCH=1 "$PY" -m pytest -q -m "not slow" -p no:randomly 2>&1 | tee "$WT/.gate.out"
grep -a "^FAILED" "$WT/.gate.out" | sed 's/^FAILED //; s/ - .*//' | sort -u > "$WT/.gate.failed"
count=$(wc -l < "$WT/.gate.failed")

if [ ! -f "$BASELINE" ]; then
    cp "$WT/.gate.failed" "$BASELINE"
    echo "GATE BASELINE WRITTEN: $count known failure(s) recorded in $BASELINE"
    echo "Read it. Every line is either an environment artifact or a real defect someone must own."
    status=0
else
    # Normalise the baseline before comparing. `comm` is a byte comparison, so a baseline written
    # by a Windows editor -- or by Python's text mode, which is how this happened -- carries a
    # trailing CR on every line and matches NOTHING. The failure mode is silent and maximally
    # confusing: the SAME test ids are reported as "no longer failing" AND as "not in the baseline"
    # in one run, because every baseline entry looks fixed and every failure looks new. MEASURED
    # after a CRLF-writing edit: 17 of 17 entries in both lists at once.
    tr -d '' < "$BASELINE" | sed '/^[[:space:]]*$/d' | sort -u > "$WT/.gate.baseline"
    new_failures=$(comm -23 "$WT/.gate.failed" "$WT/.gate.baseline")
    fixed=$(comm -13 "$WT/.gate.failed" "$WT/.gate.baseline")
    [ -n "$fixed" ] && { echo "no longer failing (shrink the baseline):"; echo "$fixed" | sed 's/^/  /'; }
    if [ -n "$new_failures" ]; then
        echo "GATE FAIL: failures that are NOT in the baseline —"
        echo "$new_failures" | sed 's/^/  /'
        echo "A failure here is not sibling churn — nothing else is editing this tree."
        status=1
    else
        echo "GATE PASS: $count failure(s), all known to the baseline; nothing new"
        status=0
    fi
fi

exit $status
