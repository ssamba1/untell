"""Collect swarm worker rows + branches into main, then push.

Fleet pattern (audit_fleet.ps1 style) but run by the orchestrator:

1. For each worktree swarm0..swarmN: copy .claude/records/swarmN-*.row into the
   main tree's records dir (workers queue rows there; the collector appends).
2. For each branch loop/swarmN: merge into main with --no-ff; if a merge
   conflicts, abort it, leave the branch, and queue an AMBER entry.
3. Append the row files to .claude/audit-log.md, RENUMBERING any pass number
   that is already taken in the live log (documented collision class: worker
   rows were computed against a stale log copy while the main agent records
   directly from the live log).
4. Commit the log + queue, push.

Usage:
    python .claude/collect_swarm.py --workers 8
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\Admin\Humanize")
LOG = ROOT / ".claude" / "audit-log.md"
QUEUE = ROOT / ".claude" / "human-queue.md"
RECORDS = ROOT / ".claude" / "records"
ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*(L\d)\s*\|")

def sh(*args: str, cwd: Path | None = None) -> str:
    r = subprocess.run(args, cwd=cwd or ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  !! {args[0]} rc={r.returncode}: {r.stderr.strip()[:300]}")
    return r.stdout.strip()

def taken_numbers() -> set[int]:
    if not LOG.exists():
        return set()
    out = set()
    for line in LOG.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line.strip())
        if m:
            out.add(int(m.group(1)))
    return out


def taken_lines() -> set[str]:
    """Every row line already in the log, stripped (issue #16 dedup guard).

    audit_next.py refuses byte-identical rows at record time; the collector is the last
    line of defence for rows queued by fleet workers against a stale log, which is
    exactly how the 55 duplicate pass-rows happened. A row whose exact text is already
    present is the same pass recorded twice - skip it.
    """
    if not LOG.exists():
        return set()
    return {line.strip() for line in LOG.read_text(encoding="utf-8").splitlines()
            if ROW.match(line.strip())}

def next_free(n: int, taken: set[int]) -> int:
    while n in taken:
        n += 1
    return n


def classify_row(text: str, taken: set[int], seen: set[str]) -> tuple[str, bool]:
    """Decide whether a queued row may be appended, and under what number.

    Returns (new_text, ok). ok=False means the row is a byte-identical duplicate
    (its exact text is already in the log) and must be SKIPPED — the fleet
    accident issue #16 names. ok=True means the row is new; its pass number is
    renumbered if it collides with an already-taken number.

    Extracted from the append loop so the collector's dedupe is testable without
    touching git (issue #16 pins this as the last line of defence).
    """
    m = ROW.match(text)
    if not m:
        return text, False
    if text in seen:
        return text, False
    n = int(m.group(1))
    new = text
    if n in taken:
        nn = next_free(n + 1, taken)
        new = re.sub(r"^\|\s*\d+", f"| {nn}", text, count=1)
        taken.add(nn)
    else:
        taken.add(n)
    seen.add(new)
    return new, True

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--merge-only", action="store_true",
                    help="merge branches but do not append rows (rows stay queued)")
    a = ap.parse_args()

    taken = taken_numbers()
    print(f"live log: {len(taken)} pass numbers taken")

    # 1. Fetch latest main first so merges start from a current base.
    sh("git", "fetch", "origin", "main")
    sh("git", "merge", "origin/main", "--no-edit")

    # 2. Merge each worker branch.
    merged, conflicted = [], []
    for i in range(a.workers):
        branch = f"loop/swarm{i}"
        ahead = sh("git", "rev-list", "--count", f"main..{branch}")
        if not ahead or ahead == "0":
            print(f"  swarm{i}: nothing to merge")
            continue
        # Collect rows FIRST so a merge conflict cannot cost the record.
        tree = ROOT / ".claude" / "worktrees" / f"swarm{i}"
        recdir = tree / ".claude" / "records"
        if recdir.exists():
            for rf in sorted(recdir.glob("*.row")):
                dest = RECORDS / rf.name
                dest.write_text(rf.read_text(encoding="utf-8"), encoding="utf-8")
                print(f"  swarm{i}: queued row {rf.name}")
        r = subprocess.run(["git", "merge", "--no-ff", "--no-edit", branch],
                           cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            subprocess.run(["git", "merge", "--abort"], cwd=ROOT, capture_output=True)
            conflicted.append(branch)
            print(f"  swarm{i}: CONFLICT left on {branch}")
            continue
        merged.append(branch)
        print(f"  swarm{i}: merged {ahead} commit(s)")

    # 3. Append rows (unless merge-only), deduping byte-identical text and renumbering
    # collisions.
    if not a.merge_only:
        rows = sorted(RECORDS.glob("*.row"), key=lambda p: p.name)
        if rows:
            taken = taken_numbers()
            seen = taken_lines()
            appended = 0
            with LOG.open("a", encoding="utf-8") as f:
                for rf in rows:
                    text = rf.read_text(encoding="utf-8").strip()
                    new, ok = classify_row(text, taken, seen)
                    if not ok:
                        if text in seen:
                            print(f"  skip {rf.name}: byte-identical row already in the log")
                        else:
                            print(f"  !! bad row {rf.name}: {text[:60]}")
                        rf.unlink()
                        continue
                    f.write(new + "\n")
                    rf.unlink()
                    appended += 1
            print(f"appended {appended} rows")
        if merged or appended:
            sh("git", "add", ".claude/audit-log.md", ".claude/human-queue.md")
            sh("git", "commit", "-m", "chore(loop): collect fleet round rows")

    # 4. Push with retry: the concurrent main agent pushes every ~30s, so a
    # non-fast-forward rejection is the common case, not the exception.
    for attempt in range(5):
        r = subprocess.run(["git", "push", "origin", "main"], cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode == 0:
            print("push ok")
            break
        print(f"  push rejected (attempt {attempt+1}): {r.stderr.strip()[-200:]}")
        subprocess.run(["git", "fetch", "origin", "main"], cwd=ROOT,
                       capture_output=True, text=True)
        rr = subprocess.run(["git", "merge", "origin/main", "--no-edit"], cwd=ROOT,
                            capture_output=True, text=True)
        if rr.returncode != 0:
            print("  merge of origin/main after rejected push FAILED, aborting")
            subprocess.run(["git", "merge", "--abort"], cwd=ROOT, capture_output=True)
            break

    if conflicted:
        with QUEUE.open("a", encoding="utf-8") as f:
            f.write(f"\n## fleet AMBER - swarm merge conflicts ({len(conflicted)})\n\n"
                    f"WHAT   {', '.join(conflicted)} conflicted with main and were not merged.\n"
                    "NEXT   merge by hand, or delete the branch if superseded.\n")
    print("done")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
