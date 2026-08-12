"""Assign and record one audit pass.

The agent running the loop is a small fast model, so every choice this file can make
mechanically is a choice the model cannot get wrong. It picks the target (least-audited
first, so the rotation cannot stall on one component), prints only that target's recipe
(so a 450KB history never has to enter a context window), and validates the record written
at the end (so a pass cannot claim a fix it did not commit).

    python .claude/audit_next.py
    python .claude/audit_next.py record --verdict clean --tests-before 5736 \
        --tests-after 5736 --note "probed X, invariant held"
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGETS = ROOT / "audit-targets.md"
LOG = ROOT / "audit-log.md"

VERDICTS = ("clean", "defect-fixed", "coverage-closed", "red-fixed")
# A verdict that claims work must point at the commit that holds it, and must leave the suite
# bigger than it found it. Anything else is a story, and a story is exactly what a cheap model
# will write when the probe was inconclusive and the pass feels like it should have produced
# something.
NEEDS_EVIDENCE = ("defect-fixed", "coverage-closed")

ROW = re.compile(
    r"^\|\s*(?P<n>\d+)\s*\|\s*(?P<target>T\d+)\s*\|\s*(?P<verdict>[a-z-]+)\s*\|"
    r"\s*(?P<before>\d+)\s*\|\s*(?P<after>\d+)\s*\|\s*(?P<commit>\S+)\s*\|\s*(?P<note>.*?)\s*\|$"
)


def target_ids() -> list[str]:
    return re.findall(r"^## (T\d+) ", TARGETS.read_text(encoding="utf-8"), re.M)


def recipe(target: str) -> str:
    text = TARGETS.read_text(encoding="utf-8")
    start = text.index(f"## {target} ")
    end = text.find("\n## ", start)
    return text[start : end if end != -1 else len(text)].rstrip()


def rows() -> list[dict[str, str]]:
    if not LOG.exists():
        return []
    out = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line.strip())
        if m:
            out.append(m.groupdict())
    return out


def pick(history: list[dict[str, str]]) -> str:
    """Least-audited target wins; ties go to the lowest id.

    Deliberately not "next in sequence": a pass that dies halfway would otherwise skip a
    target forever, and a target that keeps finding defects would never be revisited.
    """
    ids = target_ids()
    counts = {t: 0 for t in ids}
    for r in history:
        if r["target"] in counts:
            counts[r["target"]] += 1
    return min(ids, key=lambda t: (counts[t], ids.index(t)))


def cmd_next() -> int:
    history = rows()
    n = len(history) + 1
    target = pick(history)
    prior = [r for r in history if r["target"] == target]

    print(f"PASS {n}")
    print(f"TARGET {target}   (audited {len(prior)} time(s) before)")
    if prior:
        print("PRIOR PASSES ON THIS TARGET:")
        for r in prior[-3:]:
            print(f"  #{r['n']} {r['verdict']}: {r['note']}")
    baseline = history[-1]["after"] if history else "unknown"
    print(f"LAST RECORDED TEST COUNT: {baseline}")
    print()
    print(recipe(target))
    print()
    print("Now follow .claude/audit-loop.md from Step 1. Audit this target only.")
    return 0


def cmd_record(a: argparse.Namespace) -> int:
    history = rows()
    n = len(history) + 1
    target = a.target or pick(history)

    if a.verdict in NEEDS_EVIDENCE:
        if not a.commit or a.commit == "-":
            sys.exit(f"REFUSED: verdict '{a.verdict}' requires --commit <sha>.")
        if a.tests_after <= a.tests_before:
            sys.exit(
                f"REFUSED: verdict '{a.verdict}' claims work but the suite did not grow "
                f"({a.tests_before} -> {a.tests_after}). Add the regression test."
            )
    if a.tests_after < a.tests_before:
        sys.exit(
            f"REFUSED: the suite shrank ({a.tests_before} -> {a.tests_after}). "
            "Deleting or skipping tests to get green is never the fix."
        )
    note = a.note.strip().replace("|", "/")
    if len(note) < 20:
        sys.exit("REFUSED: --note must actually say what was probed and what the numbers were.")

    if not LOG.exists():
        LOG.write_text(
            "# Audit log\n\nOne row per pass. Written by `audit_next.py record`.\n\n"
            "| # | target | verdict | tests before | tests after | commit | note |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n",
            encoding="utf-8",
        )
    with LOG.open("a", encoding="utf-8") as f:
        f.write(
            f"| {n} | {target} | {a.verdict} | {a.tests_before} | {a.tests_after} "
            f"| {a.commit or '-'} | {note} |\n"
        )
    print(f"recorded pass {n} on {target}: {a.verdict}")
    return 0


def main() -> int:
    # The recipes contain em-dashes and en-dashes; on a Windows console defaulting to cp1252
    # they arrive as mojibake, and a small model reading a mangled instruction follows a
    # mangled instruction.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd")
    r = sub.add_parser("record", help="append this pass to the audit log")
    r.add_argument("--verdict", required=True, choices=VERDICTS)
    r.add_argument("--tests-before", required=True, type=int)
    r.add_argument("--tests-after", required=True, type=int)
    r.add_argument("--commit", default="")
    r.add_argument("--target", default="")
    r.add_argument("--note", required=True)
    a = p.parse_args()
    return cmd_record(a) if a.cmd == "record" else cmd_next()


if __name__ == "__main__":
    raise SystemExit(main())
