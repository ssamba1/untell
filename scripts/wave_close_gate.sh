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

UNTELL_LITE_NO_TORCH=1 "$PY" -m pytest -q -m "not slow" -p no:randomly
status=$?

if [ $status -eq 0 ]; then
    echo "GATE PASS: $REF is green from a clean checkout"
else
    echo "GATE FAIL: $REF is RED from a clean checkout (pytest exit $status)"
    echo "A failure here is not sibling churn — nothing else is editing this tree."
fi
exit $status
