"""Every boundary this code has, and which of them anything tests.

Round ninety-seven measured it: over 339 comparison sites with both mutants run, of the 55 pairs
where the tests distinguish a branch **inversion** from an **off-by-one**, the inversion is caught
and the off-by-one missed at every one — 55 to 0.

Round ninety-eight acted on that for eight thresholds and killed 7 of 7 off-by-ones. Round
ninety-nine established why the technique does not generalise on its own: a property test is
exercised on whatever inputs a corpus contains, away from every boundary, and only a case
constructed **at** the boundary catches an off-by-one. It also established the limit — those eight
thresholds were found by grepping for names I happened to think of.

**That is the part a machine can do.** `x < THRESHOLD` has exactly one boundary and it is written in
the source. This enumerates them: every comparison in `untell/` between a value and a named
module-level constant, cross-referenced against the paired mutation sweep to say which are
protected.

The output is a register, not a score. A boundary nobody has tested is a place where the code could
switch one input early or late with the suite green — and for a constant a person meets, like the
word count below which no verdict is given, that is the tool disagreeing with its own documentation
about the document in front of the reader.

⚠️ **A boundary absent from the sweep is not a protected one.** The paired sweep covers the modules
whose tests could be run; two detectors need `torch`, which is absent here by organization policy.
Those are reported as `unmeasured` rather than folded in with the protected, on round ninety's rule:
a zero meaning "could not test" and a zero meaning "does not matter" are the same number and
opposite facts.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SWEEP = REPO / "eval" / "data" / "mutation_boundary.json"
TESTS = REPO / "tests"

# Constants that are not thresholds: sizes, caps and versions whose comparison has no interesting
# boundary for a reader. Kept explicit rather than pattern-matched, and small on purpose — the
# default is that a named constant in a comparison IS a boundary.
NOT_A_THRESHOLD = frozenset({
    "_SCORE_CACHE_SIZE", "_SCORE_CACHE_MAX_CHARS", "_SPACY_CACHE_MAXSIZE",
    "_SPACY_CACHE_MAX_CHARS", "_MANIFEST_VERSION", "_DEFAULT_PORT", "_RATE_WINDOW_SECONDS",
    "_MAX_INPUT_CHARS", "WINDOW_WORDS", "_CONTEXT",
})


def _module_constants(tree: ast.Module) -> set[str]:
    """Upper-case module-level names bound to a number."""
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        literal = isinstance(value, ast.Constant) and isinstance(value.value, (int, float)) \
            and not isinstance(value.value, bool)
        for target in targets:
            if isinstance(target, ast.Name) and target.id.isupper() and literal:
                found.add(target.id)
    return found


def boundaries(root: Path = REPO) -> list[dict]:
    """Every comparison between a value and a named numeric module constant."""
    out: list[dict] = []
    for path in sorted((root / "untell").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        constants = _module_constants(tree)
        if not constants:
            continue
        lines = text.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare) or len(node.ops) != 1:
                continue
            operator = node.ops[0]
            if not isinstance(operator, (ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
                continue
            named = [
                n.id for n in (node.left, node.comparators[0])
                if isinstance(n, ast.Name) and n.id in constants
            ]
            if not named or named[0] in NOT_A_THRESHOLD:
                continue
            out.append({
                "file": str(path.relative_to(root)),
                "line": node.lineno,
                "constant": named[0],
                "source": lines[node.lineno - 1].strip()[:100],
            })
    return out


def sweep_is_stale(root: Path = REPO) -> list[str]:
    """Test files newer than the sweep the register reads.

    ⚠️ **A register built on a stale sweep reports fixed boundaries as broken, and the first version
    of this module did exactly that.** It read a sweep taken before round ninety-eight's threshold
    tests existed, so all seven boundaries that round had verified as killed came back "unprotected".
    Every number it printed was wrong in the alarming direction, which is the direction that wastes
    the most work.

    Freshness is checked rather than assumed, and by modification time rather than by trusting
    whoever runs it to re-sweep first.
    """
    sweep = root / "eval" / "data" / "mutation_boundary.json"
    if not sweep.exists():
        return ["the sweep has not been run at all"]
    cutoff = sweep.stat().st_mtime
    return sorted(
        f"tests/{p.name}" for p in (root / "tests").glob("test_*.py")
        if p.stat().st_mtime > cutoff
    )


# Boundaries where the two operators CANNOT differ on any input the code can reach. These are
# equivalent mutants: they survive every sweep, and no test will ever kill them, because there is
# no behaviour to catch. Reporting them as "unprotected" invites writing a test that pretends to
# cover one, and a list that is mostly noise is a list nobody reads.
#
# ⚠️ Two entries were removed from this table after being added to it, and the reason both were
# wrong is the same: the argument compared what the operators RETURN and never asked what they DO.
# `api_server.py` at the bucket cap deletes nothing either way — but `>=` first SORTS four thousand
# entries to build the empty slice. `perplexity_burstiness` at the TTR floor returns 0.0 either way
# — but `>` gets there through a division and a `clamp01` call the early exit skips. Both were then
# killed by a test that watched the side effect. **An equivalence argument must cover side effects,
# or it is not an equivalence argument**, and "same value" is not "same behaviour".
#
# Keyed by the stripped SOURCE LINE, not the line number: numbers drift on every edit above them
# (round 133 lost a calibration test to exactly that), and `_LOCKED_SHARE_BAR` is compared at three
# sites of which only one is equivalent, so the constant alone cannot identify a row either.
EQUIVALENT: dict[tuple[str, str], str] = {
    ("untell/humanness.py", "if cv < _BURSTY_FLOOR:"):
        "The ramp in the next branch is CONSTRUCTED to meet the flat penalty at the floor: "
        "MAX * (0.50 - 0.35) / 0.15 == MAX * 1. The piecewise function is continuous there, so "
        "both branches compute the same penalty. IEEE arithmetic separates them by 5.55e-17 and "
        "`humanness` returns round(score * 100.0, 1), which erases it — MEASURED 69.0 either way.",
    ("untell/scripts/score.py", "if abs(estimate - _LOCKED_SHARE_BAR) > _LOCK_NOTE_MARGIN:"):
        "Flips only when abs(estimate - 0.50) == 0.15 exactly, and no IEEE double does: a "
        "difference in [0.5, 1) lands on a 2^-53 grid while 0.15 needs the finer grid of "
        "[0.125, 0.25), so the subtraction cannot produce it.",
    ("untell/scripts/score.py",
     "return _MOSTLY_LOCKED_NOTE if estimate > _LOCKED_SHARE_BAR else None"):
        "Reached only when the guard above passed, which excludes estimate == _LOCKED_SHARE_BAR "
        "by construction.",
}


def _equivalence(root: Path, entry: dict) -> str | None:
    """The recorded reason this boundary cannot be killed, or None if it is a real one.

    Re-reads the line from disk and matches on its text, so a row whose code has been rewritten
    stops matching and the boundary returns to the unprotected list rather than staying excused by
    a stale table entry.
    """
    try:
        line = (root / entry["file"]).read_text(encoding="utf-8").splitlines()[entry["line"] - 1]
    except (OSError, IndexError):
        return None
    return EQUIVALENT.get((entry["file"], line.strip()))


def register(root: Path = REPO) -> dict:
    """Boundaries, split by whether the sweep shows the off-by-one is caught."""
    sweep = json.loads((root / "eval" / "data" / "mutation_boundary.json").read_text())
    survived = {
        (s["file"], s["line"]) for s in sweep["survivors"] if s["kind"] == "boundary"
    }
    measured = set(sweep["baselines"])

    protected, unprotected, unmeasured, equivalent = [], [], [], []
    for entry in boundaries(root):
        if entry["file"] not in measured:
            unmeasured.append(entry)
        elif (entry["file"], entry["line"]) in survived:
            # A recorded equivalence only applies to a SURVIVOR. If one of these is ever reported
            # killed, the argument was wrong and the row belongs back in the measured population.
            reason = _equivalence(root, entry)
            (equivalent if reason else unprotected).append(
                {**entry, "why_equivalent": reason} if reason else entry)
        else:
            protected.append(entry)

    # Equivalent mutants are out of the denominator, not counted as protected. They cannot be
    # caught, so including them would cap the share below 100% forever; counting them as caught
    # would claim a test that does not exist.
    total = len(protected) + len(unprotected)
    return {
        "stale_since_sweep": sweep_is_stale(root),
        "boundaries": len(protected) + len(unprotected) + len(unmeasured) + len(equivalent),
        "protected": protected,
        "unprotected": unprotected,
        "unmeasured": unmeasured,
        "equivalent": equivalent,
        "protected_share": round(100.0 * len(protected) / total, 1) if total else 0.0,
    }


def all_importers(root: Path = REPO) -> dict[str, list[str]]:
    """Every test importing each module, UNCAPPED — the opposite of `mutation.test_index`.

    The sweep caps its selection because running 97 test files per mutant is unaffordable across
    thousands of mutants. For thirty boundaries it is affordable exactly once, and it is the only
    way to tell "no test covers this" from "the capped selection missed the test that does".
    """
    from eval.mutation import UNCOLLECTABLE

    found: dict[str, set[str]] = {}
    for path in sorted((root / "tests").glob("test_*.py")):
        relative = f"tests/{path.name}"
        if relative in UNCOLLECTABLE:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                if name.startswith("untell"):
                    found.setdefault(name, set()).add(relative)
    return {module: sorted(files) for module, files in found.items()}


_FLIP = {"<": "<=", "<=": "<", ">": ">=", ">=": ">"}


def verify_unprotected(root: Path = REPO, timeout: int = 600) -> dict:
    """Re-run each 'unprotected' boundary against every test that imports its module.

    ⚠️ **The register inherits the harness's blind spots, and the harness has had two.** Round
    ninety-five found stale bytecode masking mutations; round one hundred found the test selection
    dropping the very boundary tests it should have run. Both produced FALSE SURVIVORS. Acting on a
    register of thirty unprotected boundaries without checking it would repeat that at the cost of
    thirty tests written for code that is already covered.
    """
    import shutil
    import subprocess

    from eval.mutation import Mutant, _failures, _worktree, apply_mutant

    report = register(root)
    importers = all_importers(root)
    results: list[dict] = []
    scratch, tree = _worktree(root)
    try:
        for entry in report["unprotected"]:
            module = entry["file"][:-3].replace("/", ".")
            tests = tuple(importers.get(module, ()))
            if not tests:
                results.append({**entry, "verdict": "no test imports this module"})
                continue
            path = tree / entry["file"]
            original = path.read_text()
            line = original.splitlines()[entry["line"] - 1]
            operator = next((o for o in ("<=", ">=", "<", ">") if o in line), None)
            if operator is None:
                results.append({**entry, "verdict": "no operator found on the line"})
                continue
            mutated = apply_mutant(
                original, Mutant(entry["file"], entry["line"], "boundary",
                                 operator, _FLIP[operator]))
            if mutated is None:
                results.append({**entry, "verdict": "token ambiguous on the line"})
                continue
            baseline = _failures(tree, tests, timeout)
            try:
                path.write_text(mutated)
                after = _failures(tree, tests, timeout)
            finally:
                path.write_text(original)
            killed = after != baseline if baseline < 0 else after > baseline
            results.append({
                **entry, "tests_run": len(tests),
                "verdict": "killed by the wider suite" if killed else "genuinely unprotected",
            })
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(tree)],
                       cwd=root, capture_output=True)
        shutil.rmtree(scratch, ignore_errors=True)

    genuine = [r for r in results if r["verdict"] == "genuinely unprotected"]
    recovered = [r for r in results if r["verdict"] == "killed by the wider suite"]
    return {
        "checked": len(results),
        "genuinely_unprotected": len(genuine),
        "false_alarms": len(recovered),
        "results": results,
    }


def render(report: dict) -> str:
    lines = []
    if report.get("stale_since_sweep"):
        lines += [
            "⚠️ STALE: these test files are newer than the sweep, so a boundary they protect will",
            "   still be reported unprotected. Re-run:",
            "     python -m eval.mutation --all --kinds boundary --workers 4 --json \\",
            "       > eval/data/mutation_boundary.json",
            *(f"     {name}" for name in report["stale_since_sweep"][:6]),
            "",
        ]
    lines += [
        f"{report['boundaries']} comparison(s) against a named threshold in untell/.",
        f"  off-by-one caught     {len(report['protected'])}",
        f"  off-by-one SURVIVES   {len(report['unprotected'])}",
        f"  equivalent mutants    {len(report.get('equivalent', []))}  (cannot be killed; excluded "
        f"from the share)",
        f"  not measurable here   {len(report['unmeasured'])}",
        f"  protected share       {report['protected_share']}%",
        "",
    ]
    if report["unprotected"]:
        lines.append("Unprotected — the code could switch one input early or late, suite green:")
        for entry in report["unprotected"]:
            lines.append(f"  {entry['file']}:{entry['line']}  {entry['constant']}")
            lines.append(f"      {entry['source']}")
    for entry in report.get("equivalent", []):
        lines.append(f"  EQUIVALENT {entry['file']}:{entry['line']} {entry['constant']}")
        lines.append(f"      {entry['why_equivalent']}")
    for entry in report["unmeasured"]:
        lines.append(f"  UNMEASURED {entry['file']}:{entry['line']} {entry['constant']} — its "
                     f"module's tests could not run here")
    lines += [
        "",
        "A boundary absent from the sweep is not a protected one. Test each at n-1, n and n+1: two",
        "points leave the switch free to sit on either side of the gap, three pin it.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true",
                        help="re-run each unprotected boundary against EVERY test importing its "
                             "module, to tell a real gap from a selection artefact")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    if args.verify:
        checked = verify_unprotected()
        print(json.dumps(checked, indent=2) if args.as_json else "\n".join(
            [f"{checked['checked']} unprotected boundaries re-checked against every importing test.",
             f"  genuinely unprotected  {checked['genuinely_unprotected']}",
             f"  selection artefacts    {checked['false_alarms']}", ""]
            + [f"  {r['file']}:{r['line']} {r['constant']} — {r['verdict']}"
               for r in checked["results"]]))
        return 0
    report = register()
    print(json.dumps(report, indent=2) if args.as_json else render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
