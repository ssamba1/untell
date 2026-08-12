"""Prove a new test actually catches the thing it was written for.

Step 3 of every pass says: take the fix away, watch the new test go red, put it back, watch
it go green. Written as instructions, that step gets skipped — it is four commands, it always
"obviously" works, and a small model under context pressure will report having done it. So it
is a script, and the pass records its exit code.

    python .claude/verify.py tests/test_a_thing.py --fix untell/scripts/thing.py

RED-then-GREEN and it exits 0. Anything else is a test that passes with and without the fix,
which is decoration: it would have passed before the bug, during it, and after.

Reverting is done by copy-and-restore rather than `git stash`, so a crash leaves the file on
disk rather than the change on a stash stack nobody remembers to pop.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def run(tests: list[str], timeout: int) -> tuple[bool, str]:
    try:
        p = subprocess.run(
            [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", *tests],
            cwd=ROOT,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    return p.returncode == 0, next(iter(reversed((p.stdout or "").strip().splitlines())), "?")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tests", nargs="+", help="the new test file(s)")
    ap.add_argument("--fix", required=True, help="the source file holding the fix under test")
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()

    fix = (ROOT / a.fix).resolve()
    if not fix.is_file():
        sys.exit(f"no such file: {a.fix}")

    fixed = fix.read_text(encoding="utf-8")
    head = subprocess.run(
        ["git", "show", f"HEAD:{a.fix.replace(chr(92), '/')}"],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if head.returncode != 0:
        sys.exit(f"REFUSED: {a.fix} is not in HEAD, so there is no 'before' to revert to. "
                 "Commit the surrounding code first, or verify by hand.")
    if head.stdout == fixed:
        sys.exit(f"REFUSED: {a.fix} is identical to HEAD - there is no fix here to take away. "
                 "Either the fix is not written yet or it is already committed.")

    ok_with, tail_with = run(a.tests, a.timeout)
    print(f"with fix     {'PASS' if ok_with else 'FAIL'}  {tail_with}")
    if not ok_with:
        print("\nThe test fails against your own fix. Fix the test, or the fix.")
        return 2

    try:
        fix.write_text(head.stdout, encoding="utf-8")
        ok_without, tail_without = run(a.tests, a.timeout)
    finally:
        fix.write_text(fixed, encoding="utf-8")
    print(f"without fix  {'PASS' if ok_without else 'FAIL'}  {tail_without}")

    if ok_without:
        print(
            "\nThe test passes WITHOUT the fix. It pins nothing about the defect - it would "
            "have passed before the bug existed. Delete it and write one that fails."
        )
        return 2
    print("\nverified: red without the fix, green with it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
