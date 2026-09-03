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
import os
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

# Test modules that fail at COLLECTION in this environment, because `torch` is absent and
# `huggingface.co` is blocked at the egress proxy by organization policy. A selection containing one
# of these reports an error rather than a failure count, which would score every mutant against it
# as killed.
# ⚠️ `untell/scripts/audit.py` is not here and is unmeasurable anyway, for a structural reason worth
# writing down rather than fixing with a longer timeout. Its most specific test —
# `test_every_audit_check_can_fail.py` — is itself a mutation suite: it mutates each audit check and
# re-runs the whole audit. MEASURED, one baseline pass over its selection takes **4m27s**, so a
# per-mutant timeout that accommodated it would put a single module's sweep in the hours.
#
# The cost is recorded rather than hidden: its one boundary, `_MODULE_DRIFT`, moved from
# "unprotected" to "unmeasured" in the register, which is the honest classification — a zero meaning
# "could not test" and a zero meaning "does not matter" are the same number and opposite facts.
UNCOLLECTABLE = frozenset({
    "tests/test_ai_index_uses_machine_label.py",
    "tests/test_bertscore_uses_rescaled_baseline.py",
    "tests/test_human_index_resolves_from_label_1.py",
    "tests/test_mage_window_is_700_words.py",
})

# How many test files to run per module. A cap is unavoidable — `untell.scripts.score` is imported
# by 96 test modules — and it makes the score PESSIMISTIC, since a mutant this selection misses may
# well be caught by a test outside it. Round ninety-three measured that gap directly rather than
# guessing at it: of survivors re-run against 1,543 tests, 40% died.
TESTS_PER_MODULE = 5

# On top of the breadth-ranked selection: test files that name the module's own THRESHOLD constants
# (those appearing in an ordering comparison), most specific first. Small, because its job is to
# catch the dedicated boundary test rather than to widen the selection generally.
#
# ⚠️ It remains a heuristic. A module with several threshold constants gives a file that names one
# of them a low rank, and `untell.scripts.score` needed five slots rather than three before the
# dedicated boundary test made the cut. Five is a round number, not the number that made one file
# pass; a module whose boundary test still falls outside it will under-report its own coverage, and
# the register in `eval/boundaries.py` is where that shows up.
CONSTANT_NAMING_TESTS = 5


def test_index(root: Path = REPO) -> dict[str, list[str]]:  # noqa: PT028
    """Module name -> the test files that import it, most focused on it first.

    "Most focused" is the test file importing the fewest `untell` modules overall. A test that
    imports one module is about that module; a test that imports twelve is an integration test that
    happens to touch it, and running the integration tests first would spend the whole budget
    without ever exercising the code being mutated.
    """
    imports: dict[str, set[str]] = {}
    for path in sorted((root / "tests").glob("test_*.py")):
        relative = f"tests/{path.name}"
        if relative in UNCOLLECTABLE:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        touched = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            touched.update(n for n in names if n.startswith("untell"))
        if touched:
            imports[relative] = touched

    breadth = {name: len(mods) for name, mods in imports.items()}
    index: dict[str, list[str]] = {}
    for relative, touched in imports.items():
        for module in touched:
            index.setdefault(module, []).append(relative)

    # ⚠️ **Breadth ranking has a systematic blind spot, and it is aimed at the tests this repository
    # has spent five rounds writing.** A boundary test imports the module's threshold constant AND
    # the callers that compare against it, so it touches several `untell` modules and ranks LAST by
    # breadth — then the cap drops it. MEASURED: after round ninety-eight verified seven off-by-ones
    # as killed, a fresh sweep still reported all seven surviving, because
    # `test_a_threshold_switches_exactly_where_it_says.py` imports five modules and was never
    # selected for any of them.
    #
    # So a test naming one of the module's own constants is always included, whatever its breadth.
    # That is a narrow rule with an exact target: a file that mentions `_MIN_WORDS_FOR_A_VERDICT` is
    # about that threshold no matter what else it imports.
    constants: dict[str, set[str]] = {}
    for path in sorted(root.rglob("untell/**/*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        module = str(path.relative_to(root))[:-3].replace("/", ".")
        declared = set()
        for node in tree.body:
            targets = node.targets if isinstance(node, ast.Assign) else (
                [node.target] if isinstance(node, ast.AnnAssign) else [])
            for target in targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    declared.add(target.id)
        # Only the constants that appear in an ORDERING comparison. Those are the module's
        # thresholds, and naming one is what distinguishes a boundary test from a test that happens
        # to import a size cap. Ranking on all constants put the dedicated boundary test outside the
        # top three for three of the four modules it covers.
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(
                node.ops[0], (ast.Lt, ast.LtE, ast.Gt, ast.GtE)
            ):
                for side in (node.left, *node.comparators):
                    if isinstance(side, ast.Name) and side.id in declared:
                        names.add(side.id)
        if names:
            constants[module] = names

    bodies = {
        f"tests/{p.name}": p.read_text(encoding="utf-8")
        for p in (root / "tests").glob("test_*.py")
        if f"tests/{p.name}" not in UNCOLLECTABLE
    }

    out: dict[str, list[str]] = {}
    for module, files in index.items():
        ranked = sorted(files, key=lambda f: (breadth[f], f))[:TESTS_PER_MODULE]
        # Ranked by HOW MANY of the module's constants a file names, not merely whether it names
        # one. A dedicated boundary test imports several — the threshold, the bar it is compared
        # against, the band it indexes — while an incidental test mentions one in passing. Without
        # the ranking, `untell.scripts.score` selected 35 test files and the sweep became unusable.
        def specificity(name: str, module: str = module) -> tuple[int, str]:
            body = bodies.get(name, "")
            return (-sum(1 for c in constants.get(module, ()) if c in body), name)

        named = sorted(
            (f for f in files if f not in ranked and specificity(f)[0] < 0),
            key=specificity,
        )[:CONSTANT_NAMING_TESTS]
        out[module] = ranked + named
    return out


def discovered_targets(root: Path = REPO) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Every module in `untell/` paired with the tests most about it.

    Replaces the hand-written pairing round ninety-three used for two modules. A hand-written map
    does not reach 65 modules, and a mutation score that only covers the files somebody remembered
    is the same selection bias this repository keeps finding elsewhere.
    """
    index = test_index(root)
    out = []
    for path in sorted((root / "untell").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        relative = str(path.relative_to(root))
        module = relative[:-3].replace("/", ".")
        tests = tuple(index.get(module, ()))
        if tests:
            out.append((relative, tests))
    return tuple(out)


# ⚠️ **The operator set is an unchosen parameter of this tool, and rounds eighty-six and
# eighty-seven are about exactly that.** Three operators were enough to produce a number; whether
# they reach the failure modes that matter is a separate question, and one only a wider set can
# answer. Round ninety-seven widened it and measured what the first three could not see.
#
# Negation, not boundary: `<` becomes `>=`, which inverts the branch. That is the easy mutant — any
# test exercising either side catches it. `_BOUNDARIES` below makes the off-by-one instead, `<` to
# `<=`, which changes behaviour on exactly one input and is what a real off-by-one looks like.
_COMPARISONS = {
    ast.Lt: ("<", ">="), ast.LtE: ("<=", ">"), ast.Gt: (">", "<="), ast.GtE: (">=", "<"),
}
_BOUNDARIES = {
    ast.Lt: ("<", "<="), ast.LtE: ("<=", "<"), ast.Gt: (">", ">="), ast.GtE: (">=", ">"),
}
_BINOPS = {ast.Add: ("+", "-"), ast.Sub: ("-", "+"), ast.Mult: ("*", "/"), ast.Div: ("/", "*")}
# `in`/`not in` and `is`/`is not` are separated from the ordering comparisons because they fail
# differently: an inverted membership test usually raises or empties a collection rather than
# shifting a number, and a suite can be blind to one while catching the other.
_MEMBERSHIP = {ast.In: ("in", "not in"), ast.NotIn: ("not in", "in")}
_IDENTITY = {ast.Is: ("is", "is not"), ast.IsNot: ("is not", "is")}
_BOOLEANS = {ast.And: ("and", "or"), ast.Or: ("or", "and")}


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
                before, after = _BOUNDARIES[operator]
                found.append(Mutant(path, node.lineno, "boundary", before, after))
            elif operator in _MEMBERSHIP:
                before, after = _MEMBERSHIP[operator]
                found.append(Mutant(path, node.lineno, "membership", before, after))
            elif operator in _IDENTITY:
                before, after = _IDENTITY[operator]
                found.append(Mutant(path, node.lineno, "identity", before, after))
        elif isinstance(node, ast.BoolOp) and type(node.op) in _BOOLEANS:
            before, after = _BOOLEANS[type(node.op)]
            found.append(Mutant(path, node.lineno, "boolean", before, after))
        elif isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            before, after = _BINOPS[type(node.op)]
            found.append(Mutant(path, node.lineno, "arithmetic", before, after))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in {"max", "min"}:
            found.append(Mutant(path, node.lineno, "extremum", node.func.id,
                                "min" if node.func.id == "max" else "max"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            found.append(Mutant(path, node.lineno, "constant", str(node.value),
                                str(not node.value)))
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
    # Belt and braces with PYTHONDONTWRITEBYTECODE: a checkout can inherit `__pycache__` from an
    # untracked directory, and stale bytecode is what makes a killed mutant look like a survivor.
    for cached in tree.rglob("__pycache__"):
        shutil.rmtree(cached, ignore_errors=True)
    return scratch, tree


_SUMMARY = re.compile(r"(\d+) failed")

# What `_failures` returns when a selection did not produce a failure count at all — it timed out,
# or it died before any test ran (a collection error, a missing dependency).
#
# ⚠️ **This must not be a large number, and making it one was a real defect.** With a sentinel of
# 10,000 as the baseline, no mutant can ever exceed it, so every mutant for that module is scored a
# survivor — silently, and indistinguishably from a genuinely uncovered line. MEASURED on the first
# full-package run: 3 of 58 modules timed out at baseline and contributed up to 9 spurious
# survivors. That is round ninety's lesson exactly, committed in the harness written two rounds
# after it: a zero meaning "could not test" and a zero meaning "does not matter" are the same number
# and opposite facts. A module whose baseline is unusable is now SKIPPED and listed, not scored.
UNUSABLE = -1


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
    # ⚠️ **Bytecode caching silently masks a mutation, and the default settings make it likely.**
    # CPython invalidates a `.pyc` on (mtime, size). Every mutation this tool makes is a
    # single-character swap — `-` for `+`, `<` for `>=` — so the file size is unchanged or nearly so,
    # and a write landing in the same mtime second leaves the stale bytecode valid. The mutated
    # source is then never loaded and the mutant is scored a SURVIVOR.
    #
    # MEASURED: `rich_output.py:104` was reported as surviving a test that compares the function
    # directly against `difflib._format_range_unified`, which it cannot survive — the same mutant in
    # a fresh worktree failed 7 tests. Every mutation figure taken before this fix is suspect in one
    # direction: too many survivors, never too few.
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        result = subprocess.run(
            [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:randomly",
             "-p", "no:cacheprovider", *present],
            cwd=tree, capture_output=True, text=True, timeout=timeout, env=environment,
        )
    except subprocess.TimeoutExpired:
        return UNUSABLE
    match = _SUMMARY.search(result.stdout)
    if match:
        return int(match.group(1))
    # No "N failed" in the summary: either everything passed, or the run died before reporting.
    return 0 if result.returncode == 0 else UNUSABLE


def _worker(root: Path, queue: list[tuple[str, tuple[str, ...]]], limit: int | None,
            timeout: int, kinds: frozenset[str] | None = None,
            ) -> tuple[list[dict], list[dict], dict]:
    """One worktree, working through its share of the modules."""
    scratch, tree = _worktree(root)
    results: list[dict] = []
    unmeasurable: list[dict] = []
    baselines: dict[str, int] = {}
    try:
        for relative, tests in queue:
            path = tree / relative
            original = path.read_text()
            candidates = mutants_for(original, relative)
            if kinds:
                candidates = [c for c in candidates if c.kind in kinds]
            if limit:
                step = max(1, len(candidates) // limit)
                candidates = candidates[::step][:limit]
            if not candidates:
                continue

            baseline = _failures(tree, tests, timeout)
            if baseline == UNUSABLE:
                unmeasurable.append({"file": relative, "tests": list(tests),
                                     "why": "its test selection times out or fails to collect, so "
                                            "no mutant against it could be scored"})
                continue
            baselines[relative] = baseline
            for mutant in candidates:
                mutated = apply_mutant(original, mutant)
                if mutated is None:
                    continue
                try:
                    path.write_text(mutated)
                    after = _failures(tree, tests, timeout)
                    killed = after == UNUSABLE or after > baseline
                finally:
                    path.write_text(original)
                results.append({"file": mutant.path, "line": mutant.line, "kind": mutant.kind,
                                "mutation": f"{mutant.before} -> {mutant.after}", "killed": killed})
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(tree)],
                       cwd=root, capture_output=True)
        shutil.rmtree(scratch, ignore_errors=True)
    return results, unmeasurable, baselines


def run_parallel(root: Path = REPO, limit_per_file: int | None = None, timeout: int = 300,
                 targets: tuple[tuple[str, tuple[str, ...]], ...] | None = None,
                 workers: int = 4, kinds: frozenset[str] | None = None) -> dict:
    """The same sweep, spread across several worktrees.

    Round ninety-four sampled 3 mutants per module because the serial run of all 1,397 candidates
    would have taken about four hours. Sampling was the right call for an estimate of the SCORE and
    the wrong one for the survivor LIST, which is the part anybody can act on: a sampled list names
    a third of the uncovered lines and gives no way to tell which two thirds it missed.

    Modules are dealt round-robin rather than in blocks, so one slow module does not leave a worker
    holding the whole tail.
    """
    from concurrent.futures import ThreadPoolExecutor

    chosen = list(targets or TARGETS)
    queues: list[list[tuple[str, tuple[str, ...]]]] = [[] for _ in range(max(1, workers))]
    for index, target in enumerate(chosen):
        queues[index % len(queues)].append(target)

    results: list[dict] = []
    unmeasurable: list[dict] = []
    baselines: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=len(queues)) as pool:
        for got, skipped, base in pool.map(
            lambda q: _worker(root, q, limit_per_file, timeout, kinds), queues,
        ):
            results.extend(got)
            unmeasurable.extend(skipped)
            baselines.update(base)

    killed = [r for r in results if r["killed"]]
    survivors = [r for r in results if not r["killed"]]
    by_kind: dict[str, dict[str, int]] = {}
    for row in results:
        cell = by_kind.setdefault(row["kind"], {"killed": 0, "survived": 0})
        cell["killed" if row["killed"] else "survived"] += 1
    for cell in by_kind.values():
        total = cell["killed"] + cell["survived"]
        cell["score"] = round(100.0 * cell["killed"] / total, 1) if total else 0.0
    return {
        "baselines": baselines,
        "unmeasurable": unmeasurable,
        "red_baselines": {k: v for k, v in baselines.items() if v},
        "by_kind": by_kind,
        "workers": len(queues),
        "mutants": len(results),
        "killed": len(killed),
        "survived": len(survivors),
        "score": round(100.0 * len(killed) / len(results), 1) if results else 0.0,
        "survivors": sorted(survivors, key=lambda r: (r["file"], r["line"])),
        # Every outcome, not only the survivors. Pairing the two mutants at one comparison site —
        # inversion against off-by-one — needs to know the partner RAN, and a survivor list cannot
        # distinguish "the partner was killed" from "the partner was never sampled". Without
        # `--limit` every site gets both, so survivors alone suffice; with it they do not, and the
        # ratio computed over that ambiguity measures the sampling rather than the tests.
        "outcomes": sorted(results, key=lambda r: (r["file"], r["line"], r["kind"])),
    }


def run(root: Path = REPO, limit_per_file: int | None = None, timeout: int = 300,
        targets: tuple[tuple[str, tuple[str, ...]], ...] | None = None) -> dict:
    """Introduce each mutant, run its module's tests, and record whether anything failed."""
    scratch, tree = _worktree(root)
    results: list[dict] = []
    unmeasurable: list[dict] = []
    try:
        for relative, tests in (targets or TARGETS):
            path = tree / relative
            original = path.read_text()
            candidates = mutants_for(original, relative)
            if limit_per_file:
                # Evenly spaced rather than the first N, so a capped run does not measure only the
                # top of one file.
                step = max(1, len(candidates) // limit_per_file)
                candidates = candidates[::step][:limit_per_file]

            baseline = _failures(tree, tests, timeout)
            if baseline == UNUSABLE:
                unmeasurable.append({"file": relative, "tests": list(tests),
                                     "why": "its test selection times out or fails to collect, so "
                                            "no mutant against it could be scored"})
                continue
            for mutant in candidates:
                mutated = apply_mutant(original, mutant)
                if mutated is None:
                    continue
                try:
                    path.write_text(mutated)
                    after = _failures(tree, tests, timeout)
                    # UNUSABLE means the mutant broke the run outright — an import error or a
                    # hang. That is the suite noticing in the loudest way available, so it counts.
                    killed = after == UNUSABLE or after > baseline
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
    by_kind: dict[str, dict[str, int]] = {}
    for row in mutants:
        cell = by_kind.setdefault(row["kind"], {"killed": 0, "survived": 0})
        cell["killed" if row["killed"] else "survived"] += 1
    for cell in by_kind.values():
        total = cell["killed"] + cell["survived"]
        cell["score"] = round(100.0 * cell["killed"] / total, 1) if total else 0.0
    return {
        "baselines": baselines,
        "unmeasurable": unmeasurable,
        "red_baselines": {k: v for k, v in baselines.items() if v},
        "by_kind": by_kind,
        "mutants": len(mutants),
        "killed": len(killed),
        "survived": len(survivors),
        "score": round(100.0 * len(killed) / len(mutants), 1) if mutants else 0.0,
        "survivors": survivors,
    }


def _all_importers(root: Path) -> dict[str, list[str]]:
    """Every test importing each module, uncapped — the opposite of `test_index`."""
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


def verify_survivors(survivors: list[dict], root: Path = REPO, sample: int = 24,
                     seed: int = 0, timeout: int = 600) -> dict:
    """How many reported survivors are genuinely uncaught by ANY test?

    A survivor is this harness's finding, and `eval/checkers.py` records every other checker's
    precision — the share of its findings that were real when somebody read them all. This one was
    the last left UNMEASURED, and it is the checker with the most reason to be wrong: **both of its
    known defects produced false survivors.** Stale bytecode meant a mutation never loaded (round
    ninety-five); a breadth-ranked test selection dropped the tests most likely to catch a boundary
    (round one hundred).

    The method is round one hundred and one's, generalised from boundary mutants to every operator:
    re-run each sampled survivor against **every test importing its module**, uncapped. Unaffordable
    across thousands of mutants; affordable once, on a sample, to put a number on the harness.

    Stratified by operator kind, because precision is not expected to be uniform — a boundary mutant
    that survives a capped selection is a different proposition from a constant flip that survives.
    """
    import collections
    import random
    import shutil
    import subprocess

    by_kind: dict[str, list[dict]] = collections.defaultdict(list)
    for entry in survivors:
        by_kind[entry["kind"]].append(entry)

    rng = random.Random(seed)
    chosen: list[dict] = []
    kinds = sorted(by_kind)
    per_kind = max(1, sample // len(kinds)) if kinds else 0
    for kind in kinds:
        pool = sorted(by_kind[kind], key=lambda e: (e["file"], e["line"]))
        chosen.extend(rng.sample(pool, min(per_kind, len(pool))))

    importers = _all_importers(root)
    results: list[dict] = []
    scratch, tree = _worktree(root)
    try:
        baselines: dict[str, int] = {}
        for entry in chosen:
            module = entry["file"][:-3].replace("/", ".")
            tests = tuple(importers.get(module, ()))
            if not tests:
                results.append({**entry, "verdict": "no test imports this module"})
                continue
            path = tree / entry["file"]
            original = path.read_text()
            before, after_token = entry["mutation"].split(" -> ")
            mutated = apply_mutant(
                original, Mutant(entry["file"], entry["line"], entry["kind"],
                                 before, after_token))
            if mutated is None:
                results.append({**entry, "verdict": "token ambiguous on the line"})
                continue
            if module not in baselines:
                baselines[module] = _failures(tree, tests, timeout)
            baseline = baselines[module]
            if baseline == UNUSABLE:
                results.append({**entry, "verdict": "its module's tests cannot run here"})
                continue
            try:
                path.write_text(mutated)
                observed = _failures(tree, tests, timeout)
            finally:
                path.write_text(original)
            killed = observed == UNUSABLE or observed > baseline
            results.append({
                **entry, "tests_run": len(tests),
                "verdict": "killed by the wider suite" if killed else "genuinely uncaught",
            })
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(tree)],
                       cwd=root, capture_output=True)
        shutil.rmtree(scratch, ignore_errors=True)

    scored = [r for r in results if r["verdict"] in
              {"genuinely uncaught", "killed by the wider suite"}]
    genuine = [r for r in scored if r["verdict"] == "genuinely uncaught"]
    per_kind_precision: dict[str, dict] = {}
    for kind in kinds:
        rows = [r for r in scored if r["kind"] == kind]
        if not rows:
            continue
        real = sum(1 for r in rows if r["verdict"] == "genuinely uncaught")
        per_kind_precision[kind] = {
            "sampled": len(rows), "genuine": real,
            "precision": round(100.0 * real / len(rows), 1),
        }
    return {
        "survivors_available": len(survivors),
        "sampled": len(results),
        "scored": len(scored),
        "genuinely_uncaught": len(genuine),
        "false_survivors": len(scored) - len(genuine),
        "precision": round(100.0 * len(genuine) / len(scored), 1) if scored else 0.0,
        "by_kind": per_kind_precision,
        "results": results,
    }


def render(report: dict) -> str:
    lines = []
    for entry in report.get("unmeasurable", []):
        lines.append(f"SKIPPED {entry['file']}: {entry['why']}")
    for name, failures in report["baselines"].items():
        if failures:
            lines.append(f"⚠️ {name}: its test selection already has {failures} failure(s) "
                         f"unmutated. Kills are counted against that floor, not against zero.")
    lines += [
        f"{report['mutants']} mutants introduced, {report['killed']} killed, "
        f"{report['survived']} survived — mutation score {report['score']}%.",
        "",
    ]
    if report.get("by_kind"):
        lines.append(f"  {'operator':<14} {'killed':>7} {'survived':>9} {'score':>7}")
        for kind, cell in sorted(report["by_kind"].items(), key=lambda kv: kv[1]["score"]):
            lines.append(f"  {kind:<14} {cell['killed']:>7} {cell['survived']:>9} "
                         f"{cell['score']:>6.1f}%")
        lines.append("")
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
    parser.add_argument("--all", action="store_true",
                        help="mutate every module in untell/, pairing each with the tests most "
                             "about it, instead of the two hand-written targets")
    parser.add_argument("--verify-survivors", type=Path, default=None, dest="verify",
                        help="measure this harness's own precision: re-run a stratified sample of "
                             "the survivors in this report against EVERY test importing their "
                             "module, uncapped")
    parser.add_argument("--sample", type=int, default=24)
    parser.add_argument("--kinds", type=str, default=None,
                        help="comma-separated operator kinds to run, e.g. comparison,boundary — "
                             "with no --limit this gives every site both of a pair, which is what "
                             "a paired comparison needs")
    parser.add_argument("--workers", type=int, default=1,
                        help="run the sweep across this many worktrees at once")
    parser.add_argument("--limit", type=int, default=None,
                        help="cap mutants per file, spaced evenly through it")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    if args.verify:
        prior = json.loads(args.verify.read_text())
        checked = verify_survivors(prior["survivors"], sample=args.sample,
                                   timeout=args.timeout)
        print(json.dumps(checked, indent=2) if args.as_json else "\n".join(
            [f"{checked['scored']} survivors re-checked against every importing test "
             f"(of {checked['survivors_available']} available).",
             f"  genuinely uncaught  {checked['genuinely_uncaught']}",
             f"  false survivors     {checked['false_survivors']}",
             f"  PRECISION           {checked['precision']}%", ""]
            + [f"  {k:<12} {v['genuine']}/{v['sampled']} genuine ({v['precision']}%)"
               for k, v in sorted(checked["by_kind"].items())]))
        return 0

    targets = discovered_targets() if args.all else None
    runner = run_parallel if args.workers > 1 else run
    kinds = frozenset(args.kinds.split(",")) if args.kinds else None
    kwargs = {"workers": args.workers, "kinds": kinds} if args.workers > 1 else {}
    report = runner(limit_per_file=args.limit, timeout=args.timeout, targets=targets, **kwargs)
    print(json.dumps(report, indent=2) if args.as_json else render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
