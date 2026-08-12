"""Refuse the commits the envelope forbids, before they exist.

`audit-envelope.md` is prose, and prose is advice. An unattended loop needs the boundary to
be a wall it hits, not a paragraph it interprets — especially a small fast model, which will
read "never change a threshold" and then change a threshold because this particular one felt
like a bug.

So this reads the staged diff and exits non-zero on anything RED: a published number, a
tuning constant, a dependency, a deleted or skipped test, history rewriting. AMBER passes but
demands the queue entry be staged alongside it. Everything else is silent.

    python .claude/guard.py              # check what is staged
    python .claude/guard.py --range HEAD~3..HEAD
    python .claude/guard.py --install-hook

Nothing here is a substitute for the envelope: a wall stops the moves you predicted. It is a
floor under it, so the predictable failures cannot happen at 3am while nobody is reading.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ".claude/human-queue.md"

# Files a measured number lives in. A figure in any of these was produced under stated
# conditions by a person who can defend it; edited by an unattended loop it becomes a figure
# nobody can cite.
RED_FILES = [
    re.compile(p)
    for p in (
        r"^docs/free-ceiling",
        r"^docs/humanizer-",
        r"^docs/why-best",
        r"^docs/what-would-make",
        r"^README\.md$",
        r"^CHANGELOG\.md$",
        r"^CITATION\.cff$",
        r"^_private/",
        r"^\.env",
        r"\.claude/audit-envelope\.md$",
        r"\.claude/guard\.py$",
    )
]

# The recorder's refusals and the loop's own boundary. An agent that can edit the thing that
# says no has nothing saying no.
RED_SELF = re.compile(r"\.claude/(audit_next|guard)\.py$")

AMBER_FILES = [re.compile(p) for p in (r"^\.github/", r"^pyproject\.toml$", r"^untell/SKILL\.md$")]

# A tuning constant is the product. Changing one silently changes every result anyone has
# quoted, and the change looks exactly like a bug fix in a diff.
TUNING = re.compile(
    r"^[+-]\s*_?[A-Z][A-Z0-9_]*"
    r"(THRESHOLD|_BAR|BAR|FLOOR|WEIGHT|WEIGHTS|_RATE_LIMIT|DEFAULT_[A-Z_]+)"
    r"[A-Z0-9_]*\s*[:=]"
)
DEP = re.compile(r"^[+-]\s*[\"']?[a-zA-Z0-9_.-]+\s*(>=|==|~=|<)\s*[\d\"']")
SKIP = re.compile(r"^\+\s*@pytest\.mark\.(skip|xfail)")
# re.M is load-bearing: this one is scanned over the whole diff rather than line by line, so
# without it `^` anchors to the start of the string and the pattern matches exactly once, at
# byte zero, which is never a `-def test_`. It read as "no tests removed" for every diff.
TEST_DEF = re.compile(r"^([+-])\s*(?:async\s+)?def (test_\w+)", re.M)


def sh(*args: str) -> str:
    # encoding is explicit because `text=True` alone decodes with the console codepage, and
    # cp1252 cannot decode this repo's own README: the reader thread dies, `.stdout` comes
    # back None, and the return code is still 0. A guard that silently sees an empty diff
    # approves everything, which is the worst way for a guard to fail.
    return (
        subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        ).stdout
        or ""
    )


def changed_files(rng: str | None) -> list[str]:
    out = sh("diff", "--name-only", "--cached") if rng is None else sh("diff", "--name-only", rng)
    return [f for f in out.splitlines() if f.strip()]


def diff_text(rng: str | None) -> str:
    return sh("diff", "--cached", "-U0") if rng is None else sh("diff", "-U0", rng)


def deleted_files(rng: str | None) -> list[str]:
    args = ["diff", "--name-only", "--diff-filter=D"]
    out = sh(*args, "--cached") if rng is None else sh(*args, rng)
    return [f for f in out.splitlines() if f.strip()]


def check(rng: str | None) -> tuple[list[str], list[str]]:
    files, diff = changed_files(rng), diff_text(rng)
    red: list[str] = []
    amber: list[str] = []

    for f in files:
        norm = f.replace("\\", "/")
        if any(p.search(norm) for p in RED_FILES) or RED_SELF.search(norm):
            red.append(f"RED file touched: {f} - a human owns this one. Put it in the queue.")
        if any(p.search(norm) for p in AMBER_FILES):
            amber.append(f"AMBER file touched: {f}")

    for f in deleted_files(rng):
        if f.replace("\\", "/").startswith("tests/"):
            red.append(f"RED: test file deleted: {f}. Green by deletion is not green.")

    # Net-removed test functions catch the subtler version: the file survives, the test that
    # was in the way does not.
    added = {m.group(2) for m in TEST_DEF.finditer(diff) if m.group(1) == "+"}
    removed = {m.group(2) for m in TEST_DEF.finditer(diff) if m.group(1) == "-"}
    gone = sorted(removed - added)
    if gone and len(added) >= len(removed):
        # Same count out as in: a rename, which the envelope puts in AMBER. Blocking it would
        # make the guard stricter than the rule it enforces, and a guard that blocks allowed
        # work teaches its operator to bypass it.
        amber.append(f"test(s) renamed, none lost: {', '.join(gone)}")
    else:
        for name in gone:
            red.append(f"RED: test removed: {name}. Fix the code, not the test that noticed.")

    for line in diff.splitlines():
        if line.startswith(("+++", "---")):
            continue
        if TUNING.match(line):
            red.append(f"RED: tuning constant changed: {line.strip()[:88]}")
        if DEP.match(line) and "pyproject" in diff[: diff.index(line)][-4000:]:
            red.append(f"RED: dependency changed: {line.strip()[:88]}")
        if SKIP.match(line):
            red.append(f"RED: test skipped/xfailed: {line.strip()[:88]}")

    if amber and QUEUE not in [f.replace("\\", "/") for f in files]:
        amber.append(
            f"AMBER work must be written down in the same commit - stage {QUEUE} with an entry."
        )
    return red, amber


HOOK = """#!/bin/sh
# Installed by .claude/guard.py --install-hook. Remove with: rm .git/hooks/pre-commit
exec python .claude/guard.py
"""


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--range", dest="rng", default=None, help="e.g. HEAD~3..HEAD")
    ap.add_argument("--install-hook", action="store_true", help="wire in as a pre-commit hook")
    a = ap.parse_args()

    if a.install_hook:
        # Deliberately not added to .pre-commit-config.yaml: that file is shared with humans
        # and another session working this repo, and a guard written for the loop should not
        # start refusing their commits.
        hook = ROOT / ".git" / "hooks" / "pre-commit"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text(HOOK, encoding="utf-8", newline="\n")
        print(f"installed {hook} (local only, not shared; delete the file to remove)")
        return 0

    red, amber = check(a.rng)
    for m in amber:
        print(f"  warn  {m}")
    for m in red:
        print(f"  BLOCK {m}")
    if red:
        print(
            f"\n{len(red)} envelope violation(s). This commit is not yours to make. "
            f"Write it to {QUEUE} with the command and output, record the pass as 'queued', "
            "and move on."
        )
        return 2
    if amber:
        print(f"\n{len(amber)} amber item(s) - allowed, provided the queue entry is in this commit.")
        return 1
    print("clean: nothing staged crosses the envelope")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
