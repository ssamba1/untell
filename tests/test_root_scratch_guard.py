"""Guard: repo root must not accumulate stray *untracked* scratch that git can see.

Historically the root has grown _wt_slice*/  _mem_probe*/  and audit_tmp.*
artifacts from wave activity.  These are now gitignored (policy in .gitignore
under "Root-scratch policy") but gitignore only hides *known* patterns.
If a new scratch pattern is created that does NOT yet appear in .gitignore,
this test fires on the next CI run so it is caught and either cleaned up or
explicitly gitignored before it can pollute history.

How the check works:
  `git status --porcelain=v1` emits one line per path that git can see and
  that is either modified, staged, or untracked.  Gitignored files do NOT
  appear even with ``--untracked-files=all``.  We filter for lines that start
  with ``??`` (= new, untracked, not gitignored) and whose path component is
  a bare name at the repo root (no path separator after the leading ``??  ``).
  Any such path that matches a known-bad pattern is a failure.

Known-bad patterns that must NOT appear untracked at the repo root:
  _wt_*/          stray unregistered / leftover worktree copies
  _mem_probe*/    diagnostic memory-probe scripts
  audit_tmp*      captured audit output (JSON, error logs)
  _fix_*.py       one-off fixup scripts
  _probe*.py      one-off probe scripts (belong in .claude/probes/, not root)
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_BAD_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^_wt_"),
    re.compile(r"^_mem_probe"),
    re.compile(r"^audit_tmp"),
    re.compile(r"^_fix_.+\.py$"),
    re.compile(r"^_probe.+\.py$"),
]

ROOT = Path(__file__).resolve().parents[1]


def test_no_stray_untracked_scratch_at_root() -> None:
    """No untracked file or directory matching a known-bad pattern exists at
    the repo root according to git.  Gitignored scratch is excluded by design —
    the .gitignore 'Root-scratch policy' section already covers it."""
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        check=True,
    )

    offenders: list[str] = []
    for line in result.stdout.splitlines():
        # ?? = untracked, not ignored.  Only care about root-level entries.
        if not line.startswith("?? "):
            continue
        path = line[3:]  # strip "?? "
        # Root-level: no path separator present (trailing '/' is OK for dirs).
        name = path.rstrip("/")
        if "/" in name or "\\" in name:
            continue  # nested file — not our responsibility here

        for pat in _BAD_PATTERNS:
            if pat.match(name):
                offenders.append(f"{name!r} matches {pat.pattern!r}")
                break

    assert not offenders, (
        "Stray untracked scratch found at repo root — clean these up or add "
        "them to .gitignore under 'Root-scratch policy':\n  "
        + "\n  ".join(offenders)
    )
