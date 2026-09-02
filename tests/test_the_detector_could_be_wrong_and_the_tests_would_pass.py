"""Ten thousand tests, and until now exactly one family had been shown able to fail.

`tests/test_every_audit_check_can_fail.py` mutates each audit check and asserts it notices. Nothing
else here has that property; the rest of the suite is trusted because it is green, which is the one
property every vacuous test also has. Round sixty-two is the warning — a fix there recreated a
documented vacuity, and it was caught only because somebody re-ran the negative case by hand.

Rounds ninety-one and ninety-two both found the same defect: a verification performed once by a
person, recorded in prose, and therefore not performed again when the thing it covered changed. **A
test that cannot fail is that defect written in code.** It runs in CI, it is green, and it guards
nothing.

`eval/mutation.py` breaks the detector on purpose. MEASURED over the two core scoring modules: **97
single-token mutants, 45 killed, 52 survived — a mutation score of 46.4%** against each module's own
named tests, with both baselines clean.

⚠️ **That number is against a named selection, not the whole suite, and the difference is large.**
A sample of 10 survivors re-run against a 1,543-test selection: **4 killed, 6 survived** — a
wider-suite kill rate of 40% among them, Wilson interval [17%, 69%]. So the suite as a whole catches
substantially more than 46%, and six of ten sampled survivors are still uncaught by 1,543 tests.
Both figures are reported because quoting either alone overstates the case in one direction.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from eval import mutation

REPO = Path(__file__).resolve().parent.parent
REPORT = json.loads((REPO / "eval" / "data" / "mutation.json").read_text())


def test_the_baselines_were_clean_so_the_kills_mean_something():
    """A mutant measured against a red selection is scored killed for the wrong reason."""
    for name, failures in REPORT["baselines"].items():
        assert failures == 0, (
            f"{name}: its selection had {failures} failure(s) unmutated, so its mutation score is "
            f"measuring the environment rather than the tests"
        )


def test_the_run_actually_introduced_mutants():
    """A mutation score computed over zero mutants is 0% and means nothing."""
    assert REPORT["mutants"] >= 50
    assert REPORT["killed"] > 0, "if nothing was killed the harness is not reaching the code"
    assert REPORT["survived"] > 0, "if nothing survived, check the mutants are being applied"
    assert REPORT["killed"] + REPORT["survived"] == REPORT["mutants"]


def test_the_score_has_not_silently_collapsed():
    """A ratchet on the tests themselves. It is allowed to improve, not to rot."""
    assert REPORT["score"] >= 40.0, (
        "the mutation score dropped below where round 93 measured it — some test that used to "
        "catch a broken detector no longer does"
    )


def test_every_survivor_names_a_place_somebody_could_look():
    """A survivor with no location is a statistic; with one it is a task."""
    for entry in REPORT["survivors"]:
        assert entry["file"] and entry["line"] > 0
        assert " -> " in entry["mutation"]
        assert entry["killed"] is False


def test_failures_are_counted_not_inferred_from_an_exit_code():
    """The defect this harness had, pinned so it cannot come back.

    An exit code answers "did anything fail", which is the wrong question wherever the baseline is
    already red — and it is red here, `torch` being absent and `huggingface.co` blocked by policy.
    """
    source = (REPO / "eval" / "mutation.py").read_text()
    assert "def _failures(" in source
    assert "returncode == 0" not in source.split("def _failures(")[1].split("def ")[1], (
        "kill detection outside _failures must not fall back to an exit code"
    )


def test_mutants_are_generated_only_where_they_can_be_applied():
    """A mutant applied to the wrong token is no longer the one being reported."""
    source = "x = a / b\ny = c / d if a < b else 0\n"
    found = mutation.mutants_for(source, "x.py")
    assert found
    ambiguous = mutation.Mutant("x.py", 2, "arithmetic", "/", "*")
    line_two_has_one_slash = source.splitlines()[1].count("/") == 1
    assert (mutation.apply_mutant(source, ambiguous) is not None) is line_two_has_one_slash


def test_applying_a_mutant_changes_exactly_one_line():
    source = "a = 1 + 2\nb = 3 + 4\n"
    mutant = mutation.Mutant("x.py", 1, "arithmetic", "+", "-")
    mutated = mutation.apply_mutant(source, mutant)
    assert mutated == "a = 1 - 2\nb = 3 + 4\n"


def test_a_mutant_out_of_range_is_declined_rather_than_guessed():
    assert mutation.apply_mutant("a = 1\n", mutation.Mutant("x.py", 99, "arithmetic", "+", "-")) is None


def test_the_generator_finds_the_three_kinds_it_claims_to():
    source = "def f(a, b):\n    if a < b:\n        return max(a - b, 0)\n    return a / b\n"
    kinds = {m.kind for m in mutation.mutants_for(source, "x.py")}
    assert kinds == {"comparison", "arithmetic", "extremum"}


def test_the_targets_name_tests_that_exist():
    """A target whose tests are missing scores every mutant as surviving, silently."""
    for relative, tests in mutation.TARGETS:
        assert (REPO / relative).exists(), relative
        assert tests, f"{relative} has no test selection"
        assert any((REPO / t).exists() for t in tests), (
            f"none of {relative}'s named tests exist; its mutation score would be meaningless"
        )


def test_mutation_runs_in_a_throwaway_worktree_not_the_working_tree():
    """A run that dies partway must not be able to leave a shipped module edited."""
    source = (REPO / "eval" / "mutation.py").read_text()
    tree = ast.parse(source)
    run = next(n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "run")
    calls = {n.func.id for n in ast.walk(run)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "_worktree" in calls, "run() must mutate a throwaway checkout, never the working tree"


# ---------------------------------------------------------------------------
# Round 94: the same question across the whole package rather than two modules.
#
# Round 93 paired two modules with test selections written by hand. A hand-written map does not
# reach 65 modules, and a mutation score covering only the files somebody remembered is the
# selection bias this repository keeps finding elsewhere. `discovered_targets()` derives the pairing
# from what each test file imports, ranking a module's tests by how FEW untell modules they import —
# a test importing one module is about that module; one importing twelve is an integration test that
# happens to touch it.
#
# MEASURED across 56 measurable modules: 108 mutants, 59 killed, 49 survived — 54.6%.
# ---------------------------------------------------------------------------

PACKAGE = json.loads((REPO / "eval" / "data" / "mutation_package.json").read_text())


def test_the_package_run_covers_far_more_than_two_modules():
    """The point of round 94. A score over two files is a score over two files."""
    assert len(PACKAGE["baselines"]) >= 40
    assert PACKAGE["mutants"] >= 80


def test_a_module_whose_baseline_is_unusable_is_skipped_not_scored():
    """The defect this run was re-run to fix, pinned so it cannot return.

    With a large sentinel for "the selection timed out", no mutant can ever exceed the baseline, so
    every mutant for that module is silently scored a survivor — indistinguishable from a genuinely
    uncovered line. That is round 90's lesson, committed in the harness written two rounds later.
    """
    assert mutation.UNUSABLE < 0, (
        "the unusable sentinel must not be a large number: as a baseline it would make every "
        "mutant for that module an automatic survivor"
    )
    for entry in PACKAGE["unmeasurable"]:
        assert entry["why"]
        assert entry["file"] not in {s["file"] for s in PACKAGE["survivors"]}, (
            f"{entry['file']} was skipped as unmeasurable and still contributed survivors"
        )


def test_modules_with_a_red_but_usable_baseline_are_still_measured():
    """A red baseline is a higher floor, not a reason to give up: kills compare against it."""
    assert PACKAGE["red_baselines"], (
        "this environment has absent optional dependencies, so some baselines must be red; "
        "if none are, the baseline is not being measured"
    )
    for name, failures in PACKAGE["red_baselines"].items():
        assert failures > 0
        assert failures != mutation.UNUSABLE
        assert name in PACKAGE["baselines"]


def test_the_package_score_has_not_silently_collapsed():
    assert PACKAGE["score"] >= 45.0, (
        "the package-wide mutation score dropped below where round 94 measured it"
    )


def test_the_test_index_prefers_tests_that_are_about_the_module():
    """A module's budget must not be spent on integration tests that merely touch it."""
    index = mutation.test_index()
    assert index, "no test imports any untell module — the index is broken"
    for module, files in index.items():
        assert len(files) <= mutation.TESTS_PER_MODULE, module
        assert not (set(files) & mutation.UNCOLLECTABLE), (
            f"{module} selects a test that cannot even be collected in this environment"
        )


def test_discovery_never_pairs_a_module_with_an_empty_selection():
    """A module with no tests scores every mutant as surviving, silently."""
    for relative, tests in mutation.discovered_targets():
        assert tests, relative
        assert (REPO / relative).exists()
