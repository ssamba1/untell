"""Assign and record one pass of the audit loop.

The agent running the loop is a small fast model, so every choice this file can make
mechanically is a choice the model cannot get wrong. It picks the lane (fixed schedule), it
picks the target within that lane (least-audited first, so the rotation cannot stall), it
prints only that target's recipe (so a growing history never has to enter a context window),
and it validates the record written at the end (so a pass cannot claim a fix it did not
commit).

    python .claude/audit_next.py
    python .claude/audit_next.py record --verdict clean --tests-before 5736 \
        --tests-after 5736 --note "probed X, invariant held at N of M"
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGETS = ROOT / "audit-targets.md"
LANES = ROOT / "audit-lanes.md"
LOG = ROOT / "audit-log.md"
RECORDS = ROOT / "records"

# Weighted toward L1 because auditing is the lane that has actually found things here, and
# toward L2 because a suite this large is mostly unverified until something breaks it. The
# cycle is fixed rather than random so a pass is reproducible from its number alone.
SCHEDULE = [
    "L1", "L1", "L2", "L1", "L3", "L1", "L2", "L8",
    "L4", "L1", "L2", "L5", "L1", "L8", "L2", "L6",
    "L1", "L9", "L2", "L7",
]

# Small enough to mutate in an hour, and each one is pure logic where a flipped comparison is
# a real defect rather than a stylistic difference. The big files (run.py, tells.py, score.py)
# are deliberately absent: a single mutation run over 70KB would outlive its pass.
MUTATION_MODULES = [
    "untell/layout.py",
    "untell/text_split.py",
    "untell/scripts/preserve.py",
    "untell/scripts/numerals.py",
    "untell/scripts/sentences.py",
    "untell/scripts/hedges.py",
    "untell/scripts/voice.py",
    "untell/scripts/quality.py",
    "untell/scripts/scrub.py",
    "untell/scripts/latex.py",
    "untell/scripts/io_utils.py",
    "untell/scripts/verify.py",
    "untell/languages.py",
    "untell/config.py",
    "untell/_retry.py",
    "untell/_env.py",
]

VERDICTS = ("clean", "defect-fixed", "coverage-closed", "red-fixed", "queued")
# A verdict claiming work must point at the commit holding it and must leave the suite bigger
# than it found it. Anything else is a story, and a story is what a cheap model writes when
# the probe was inconclusive but the pass feels like it should have produced something.
NEEDS_EVIDENCE = ("defect-fixed", "coverage-closed")

ROW = re.compile(
    r"^\|\s*(?P<n>\d+)\s*\|\s*(?P<lane>L\d)\s*\|\s*(?P<target>\S+)\s*\|"
    r"\s*(?P<verdict>[a-z-]+)\s*\|\s*(?P<before>\d+)\s*\|\s*(?P<after>\d+)\s*\|"
    r"\s*(?P<commit>\S+)\s*\|\s*(?P<note>.*?)\s*\|$"
)


def sibling(module: str, attr: str) -> list[str]:
    """Names defined in a sibling script, read at call time.

    Duplicating the recipe and knob lists here would let them drift from the scripts that own
    them, and a dispatcher handing out a knob that no longer exists wastes a whole pass.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(module, ROOT / f"{module}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return sorted(getattr(mod, attr))


def target_ids() -> list[str]:
    return re.findall(r"^## (T\d+) ", TARGETS.read_text(encoding="utf-8"), re.M)


def section(path: Path, heading: str) -> str:
    text = path.read_text(encoding="utf-8")
    start = text.index(f"## {heading} ")
    end = text.find("\n## ", start)
    return text[start : end if end != -1 else len(text)].rstrip()


def rows() -> list[dict[str, str]]:
    if not LOG.exists():
        return []
    return [m.groupdict() for line in LOG.read_text(encoding="utf-8").splitlines()
            if (m := ROW.match(line.strip()))]


def least_used(options: list[str], history: list[dict[str, str]]) -> str:
    """Least-audited option wins; ties go to the earliest listed.

    Deliberately not "next in sequence": a pass that dies halfway would otherwise skip its
    target forever, and a target that keeps finding defects would never be revisited.
    """
    counts = {o: 0 for o in options}
    for r in history:
        if r["target"] in counts:
            counts[r["target"]] += 1
    return min(options, key=lambda o: (counts[o], options.index(o)))


def assign(history: list[dict[str, str]], offset: int = 0) -> tuple[int, str, str]:
    """The (offset+1)-th pass from here.

    Offset exists for the fleet: N workers starting at once all read the same log, so without
    it they would all be handed pass 1 on target T01 and do the same work N times. Each
    simulated step is appended to a local copy of the history, so worker 3's target accounts
    for what workers 1 and 2 are about to take.
    """
    history = list(history)
    for _ in range(offset + 1):
        n = len(history) + 1
        lane = SCHEDULE[(n - 1) % len(SCHEDULE)]
        if lane == "L1":
            target = least_used(target_ids(), history)
        elif lane == "L2":
            target = least_used(MUTATION_MODULES, history)
        elif lane == "L8":
            target = least_used(sibling("research", "RECIPES"), history)
        elif lane == "L9":
            target = least_used(sibling("experiment", "KNOBS"), history)
        else:
            target = lane
        history.append({"n": str(n), "lane": lane, "target": target, "verdict": "pending",
                        "before": "0", "after": "0", "commit": "-", "note": "in flight"})
    return n, lane, target


def cmd_next(offset: int = 0) -> int:
    history = rows()
    n, lane, target = assign(history, offset)
    prior = [r for r in history if r["target"] == target]

    print(f"PASS {n}")
    print(f"LANE {lane}")
    print(f"TARGET {target}   (worked {len(prior)} time(s) before)")
    if prior:
        print("PRIOR PASSES ON THIS TARGET:")
        for r in prior[-3:]:
            print(f"  #{r['n']} {r['verdict']}: {r['note']}")
    print(f"LAST RECORDED TEST COUNT: {history[-1]['after'] if history else 'unknown'}")
    print()
    print(section(LANES, lane))
    print()
    if lane == "L1":
        print(section(TARGETS, target))
    elif lane == "L2":
        print(f"Run: .venv/Scripts/python.exe .claude/mutate.py {target} --max 15 --record")
    elif lane == "L8":
        print(f"Run: .venv/Scripts/python.exe .claude/research.py run {target}")
    elif lane == "L9":
        print(f"Run: .venv/Scripts/python.exe .claude/experiment.py run {target} "
              "--recipe lite-hc3")
    print()
    print("Read .claude/audit-envelope.md before changing anything. Follow "
          ".claude/audit-loop.md. Work this target only.")
    return 0


def cmd_record(a: argparse.Namespace) -> int:
    history = rows()
    n, lane, target = assign(history, a.offset)
    lane, target = a.lane or lane, a.target or target

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

    row = (
        f"| {n} | {lane} | {target} | {a.verdict} | {a.tests_before} | {a.tests_after} "
        f"| {a.commit or '-'} | {note} |\n"
    )

    if a.worker:
        # Parallel passes run in separate worktrees, and every one of them appending to the
        # same table at EOF is a guaranteed merge conflict on work that never actually
        # disagreed. Workers drop a row on disk instead; the fleet runner, which is one
        # process, collects them into the log.
        RECORDS.mkdir(parents=True, exist_ok=True)
        (RECORDS / f"{a.worker}-{n}.row").write_text(row, encoding="utf-8")
        print(f"queued row for worker {a.worker}: {lane} on {target} -> {a.verdict}")
        return 0

    if not LOG.exists():
        LOG.write_text(
            "# Audit log\n\n"
            "| # | lane | target | verdict | before | after | commit | note |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- |\n",
            encoding="utf-8",
        )
    with LOG.open("a", encoding="utf-8") as f:
        f.write(row)
    print(f"recorded pass {n}: {lane} on {target} -> {a.verdict}")
    return 0


def main() -> int:
    # The recipes contain em-dashes; on a Windows console defaulting to cp1252 they arrive as
    # mojibake, and a small model reading a mangled instruction follows a mangled instruction.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--offset", type=int, default=0,
                   help="assign the pass this many ahead; the fleet gives each worker "
                        "a different one so they do not collide")
    sub = p.add_subparsers(dest="cmd")
    r = sub.add_parser("record", help="append this pass to the audit log")
    r.add_argument("--verdict", required=True, choices=VERDICTS)
    r.add_argument("--tests-before", required=True, type=int)
    r.add_argument("--tests-after", required=True, type=int)
    r.add_argument("--commit", default="")
    r.add_argument("--lane", default="")
    r.add_argument("--target", default="")
    r.add_argument("--offset", type=int, default=0)
    r.add_argument("--worker", default="", help="parallel worker id; queues the row "
                   "instead of appending, so worktrees never conflict on the log")
    r.add_argument("--note", required=True)
    a = p.parse_args()
    return cmd_record(a) if a.cmd == "record" else cmd_next(a.offset)


if __name__ == "__main__":
    raise SystemExit(main())
