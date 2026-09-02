"""If the detector were wrong, would anything fail?

This repository has more than ten thousand tests. Exactly one family of them — the audit checks in
`tests/test_every_audit_check_can_fail.py` — has ever been shown able to fail; the rest are trusted
because they are green, which is the property every vacuous test also has. Round sixty-two is the
warning: a fix there recreated a documented vacuity, and the only reason anyone noticed was that
somebody re-ran the negative case by hand.

Rounds ninety-one and ninety-two both found the same shape of defect — a verification performed once
by a person, recorded in prose, and therefore not performed again when the thing it covered changed.
**A test that cannot fail is that defect written in code.** It looks like a guard, it runs in CI, and
it guards nothing.

So: break the code on purpose and see whether the suite notices. Each mutant is a single small edit
to a shipped module — a comparison flipped, a constant moved, an operand dropped, `max` swapped for
`min`. A mutant the tests kill is a line the suite genuinely covers. **A mutant that survives is a
way the detector could be wrong today with every test still green.**

Two design choices worth stating, because both cost something:

* **Mutants are generated and run inside a throwaway git worktree**, never in the working tree. A
  mutation run that dies partway through must not be able to leave a shipped module edited, and a
  `try/finally` restore is not a guarantee when the thing being guarded against is a crash.
* **The test selection is per-module and named**, not the whole suite. Running ten thousand tests per
  mutant would make this affordable only as a one-off, and a mutation score nobody can re-run is
  another number recorded in prose.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Mutant:
    """One single-token edit, and where it goes."""

    path: str
    line: int
    kind: str
    before: str
    after: str


# What to mutate, and which tests must notice. Keeping the pairing explicit is the point: a mutation
# score computed against a test selection that does not exercise the module is a measurement of the
# selection, not of the code.
TARGETS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "untell/detectors/perplexity_burstiness.py",
        ("tests/test_burstiness_is_biased_low_when_there_are_few_sentences.py",
         "tests/test_no_number_under_a_published_figure_is_unexamined.py",
         "tests/test_lite_score_is_deterministic.py"),
    ),
    (
        "untell/humanness.py",
        # NOT test_humanness_caveats_reach_every_document.py: it fails unmutated in this
        # environment, because `torch` is absent and the full tier falls back to lite. Every mutant
        # measured against a red selection is scored killed for the wrong reason, which is why the
        # baseline is checked and reported rather than assumed.
        ("tests/test_humanness.py",
         "tests/test_humanness_abstains_on_what_it_cannot_read.py",
         "tests/test_humanness_bands_state_their_corpus.py"),
    ),
)

_COMPARISONS = {
    ast.Lt: ("<", ">="), ast.LtE: ("<=", ">"), ast.Gt: (">", "<="), ast.GtE: (">=", "<"),
}
_BINOPS = {ast.Add: ("+", "-"), ast.Sub: ("-", "+"), ast.Mult: ("*", "/"), ast.Div: ("/", "*")}


def mutants_for(source: str, path: str) -> list[Mutant]:
    """Every single-token mutation this module knows how to make in one file.

    Deliberately shallow. A mutation operator that rewrites control flow produces mutants that fail
    to import, and a mutant that cannot run is scored as killed while proving nothing.
    """
    tree = ast.parse(source)
    found: list[Mutant] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            operator = type(node.ops[0])
            if operator in _COMPARISONS:
                before, after = _COMPARISONS[operator]
                found.append(Mutant(path, node.lineno, "comparison", before, after))
        elif isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            before, after = _BINOPS[type(node.op)]
            found.append(Mutant(path, node.lineno, "arithmetic", before, after))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in {"max", "min"}:
            found.append(Mutant(path, node.lineno, "extremum", node.func.id,
                                "min" if node.func.id == "max" else "max"))
    return found


def apply_mutant(source: str, mutant: Mutant) -> str | None:
    """Rewrite one line, or None if the token is not there to swap.

    Returns None rather than guessing when a line holds several candidates and the first is not the
    one the AST found — a mutant applied to the wrong token is still a mutant, but it is no longer
    the one being reported, and the report is the output.
    """
    lines = source.splitlines(keepends=True)
    index = mutant.line - 1
    if index >= len(lines):
        return None
    line = lines[index]
    if line.count(mutant.before) != 1:
        return None
    lines[index] = line.replace(mutant.before, mutant.after, 1)
    return "".join(lines)


def _worktree(root: Path) -> tuple[Path, Path]:
    """A throwaway checkout of HEAD, with the corpus linked in rather than copied."""
    scratch = Path(tempfile.mkdtemp(prefix="untell-mutation-"))
    tree = scratch / "tree"
    subprocess.run(["git", "worktree", "add", "-q", "--detach", str(tree), "HEAD"],
                   cwd=root, check=True, capture_output=True)
    cache = root / ".anthology-cache"
    if cache.exists():
        (tree / ".anthology-cache").symlink_to(cache)
    return scratch, tree


_SUMMARY = re.compile(r"(\d+) failed")


def _failures(tree: Path, tests: tuple[str, ...], timeout: int) -> int:
    """How many tests in the selection fail. A timeout counts as a large number, i.e. a kill.

    ⚠️ **Counting failures rather than reading the exit code, and the difference is not academic.**
    An exit code answers "did anything fail", which is the wrong question wherever the baseline is
    already red — and it is red here, because `torch` is absent and `huggingface.co` is blocked by
    organization policy, so a broad selection starts at 7 failures. A first pass at the wider-suite
    follow-up compared pytest's whole summary LINE, which includes the elapsed time and therefore
    always differs; it scored 10 of 10 mutants killed when the true answer was 4. The number to
    compare is the count.
    """
    present = [t for t in tests if (tree / t).exists()]
    if not present:
        return 0  # nothing to run: no failure observed, the conservative answer
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:randomly", *present],
            cwd=tree, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 10_000
    match = _SUMMARY.search(result.stdout)
    if match:
        return int(match.group(1))
    # No "N failed" in the summary: either everything passed, or the run died before reporting.
    return 0 if result.returncode == 0 else 10_000


def run(root: Path = REPO, limit_per_file: int | None = None, timeout: int = 300) -> dict:
    """Introduce each mutant, run its module's tests, and record whether anything failed."""
    scratch, tree = _worktree(root)
    results: list[dict] = []
    try:
        for relative, tests in TARGETS:
            path = tree / relative
            original = path.read_text()
            candidates = mutants_for(original, relative)
            if limit_per_file:
                # Evenly spaced rather than the first N, so a capped run does not measure only the
                # top of one file.
                step = max(1, len(candidates) // limit_per_file)
                candidates = candidates[::step][:limit_per_file]

            baseline = _failures(tree, tests, timeout)
            for mutant in candidates:
                mutated = apply_mutant(original, mutant)
                if mutated is None:
                    continue
                try:
                    path.write_text(mutated)
                    killed = _failures(tree, tests, timeout) > baseline
                finally:
                    path.write_text(original)
                results.append({
                    "file": mutant.path, "line": mutant.line, "kind": mutant.kind,
                    "mutation": f"{mutant.before} -> {mutant.after}", "killed": killed,
                })
            results.append({"file": relative, "baseline_failures": baseline,
                            "baseline_passes": baseline == 0, "baseline": True})
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(tree)],
                       cwd=root, capture_output=True)
        shutil.rmtree(scratch, ignore_errors=True)

    mutants = [r for r in results if not r.get("baseline")]
    killed = [r for r in mutants if r["killed"]]
    survivors = [r for r in mutants if not r["killed"]]
    baselines = {r["file"]: r["baseline_failures"] for r in results if r.get("baseline")}
    return {
        "baselines": baselines,
        "mutants": len(mutants),
        "killed": len(killed),
        "survived": len(survivors),
        "score": round(100.0 * len(killed) / len(mutants), 1) if mutants else 0.0,
        "survivors": survivors,
    }


def render(report: dict) -> str:
    lines = []
    for name, failures in report["baselines"].items():
        if failures:
            lines.append(f"⚠️ {name}: its test selection already has {failures} failure(s) "
                         f"unmutated. Kills are counted against that floor, not against zero.")
    lines += [
        f"{report['mutants']} mutants introduced, {report['killed']} killed, "
        f"{report['survived']} survived — mutation score {report['score']}%.",
        "",
    ]
    if report["survivors"]:
        lines.append("Survivors — each is a way this code could be wrong with every test green:")
        for entry in report["survivors"]:
            lines.append(f"  {entry['file']}:{entry['line']}  {entry['kind']:<11} "
                         f"{entry['mutation']}")
    else:
        lines.append("No survivors: every mutation this tool knows how to make is caught.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None,
                        help="cap mutants per file, spaced evenly through it")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    report = run(limit_per_file=args.limit, timeout=args.timeout)
    print(json.dumps(report, indent=2) if args.as_json else render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
