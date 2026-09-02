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


def test_the_generator_finds_the_kinds_it_claims_to():
    """Round 97 added five operators; a comparison site now yields an inversion AND an off-by-one."""
    source = "def f(a, b):\n    if a < b:\n        return max(a - b, 0)\n    return a / b\n"
    kinds = {m.kind for m in mutation.mutants_for(source, "x.py")}
    assert kinds == {"comparison", "boundary", "arithmetic", "extremum"}


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
    """A module's budget must not be spent on integration tests that merely touch it.

    Round 100 widened the contract: breadth ranking alone systematically excluded boundary tests,
    which import the threshold constant AND its callers and therefore look broad. The selection now
    adds up to `CONSTANT_NAMING_TESTS` files that name the module's threshold constants, so the
    bound is the sum. This test failed on the change and is updated rather than relaxed — the cap
    still exists, it is just a different number.
    """
    index = mutation.test_index()
    assert index, "no test imports any untell module — the index is broken"
    ceiling = mutation.TESTS_PER_MODULE + mutation.CONSTANT_NAMING_TESTS
    for module, files in index.items():
        assert len(files) <= ceiling, f"{module}: {len(files)} selected, cap is {ceiling}"
        assert len(files) == len(set(files)), f"{module} selects a file twice"
        assert not (set(files) & mutation.UNCOLLECTABLE), (
            f"{module} selects a test that cannot even be collected in this environment"
        )


def test_a_boundary_test_is_selected_for_the_modules_it_covers():
    """The round-100 defect, pinned. Without this the sweep silently under-reports the suite.

    MEASURED: before the fix, `test_a_threshold_switches_exactly_where_it_says.py` imported five
    modules, ranked last by breadth for every one, and was selected for none — so a fresh sweep
    reported all seven off-by-ones round 98 had verified as killed still surviving. Same mutants,
    same tests, selection alone: 18.9% -> 25.4%, 22 kills recovered.
    """
    index = mutation.test_index()
    boundary_test = "tests/test_a_threshold_switches_exactly_where_it_says.py"
    covered = [
        "untell.scripts.score",
        "untell.humanness",
        "untell.scripts.tells",
        "untell.detectors.perplexity_burstiness",
        "untell.scripts.sentences",
    ]
    missing = [m for m in covered if boundary_test not in index.get(m, [])]
    assert not missing, (
        f"the dedicated boundary test is not selected for {missing}; their off-by-one mutants will "
        f"be reported as surviving when they are not"
    )


def test_discovery_never_pairs_a_module_with_an_empty_selection():
    """A module with no tests scores every mutant as surviving, silently."""
    for relative, tests in mutation.discovered_targets():
        assert tests, relative
        assert (REPO / relative).exists()


# ---------------------------------------------------------------------------
# Round 97: the operator set was an unchosen parameter of the harness.
#
# Three operators produced the scores in rounds 93-96. Five more were added, and MEASURED over 355
# mutants EVERY operator already implemented scores above EVERY operator that was not: the original
# three kill 62.6%, the added five 39.8%, and the package score falls 58.3% -> 46.2%.
#
# The sharpest row is `boundary`. It mutates the SAME comparison sites as `comparison` — `<` to
# `<=` rather than `<` to `>=` — so the pair is a controlled comparison. An inverted branch is
# caught by a test on either side; an off-by-one changes behaviour on exactly one input.
# ---------------------------------------------------------------------------

OPERATORS = json.loads((REPO / "eval" / "data" / "mutation_operators.json").read_text())
ORIGINAL_THREE = {"comparison", "arithmetic", "extremum"}


def test_the_harness_makes_every_operator_it_claims_to():
    """An operator that stops being generated silently removes the mutants it was added for."""
    kinds = set(OPERATORS["by_kind"])
    assert kinds >= {"comparison", "boundary", "arithmetic", "extremum",
                     "boolean", "membership", "identity", "constant"}


def test_boundary_and_comparison_mutate_the_same_sites():
    """The pairing that makes the 60%/25% gap a controlled result rather than a ranking."""
    source = "def f(a, b):\n    if a < b:\n        return 1\n    return 0\n"
    kinds = [m.kind for m in mutation.mutants_for(source, "x.py")]
    assert kinds.count("comparison") == 1
    assert kinds.count("boundary") == 1
    pair = {m.kind: (m.before, m.after) for m in mutation.mutants_for(source, "x.py")}
    assert pair["comparison"] == ("<", ">="), "inversion"
    assert pair["boundary"] == ("<", "<="), "off-by-one"


def test_the_off_by_one_is_harder_for_this_suite_than_the_inversion():
    """The round-97 finding. If this ever reverses, the suite's character changed."""
    inversion = OPERATORS["by_kind"]["comparison"]["score"]
    off_by_one = OPERATORS["by_kind"]["boundary"]["score"]
    assert off_by_one < inversion, (
        "an off-by-one should be harder to catch than a branch inversion; if it is not, either the "
        "suite gained boundary tests or the operators stopped meaning what they mean"
    )


def test_the_operators_that_were_already_implemented_are_the_easy_ones():
    """Stated as a test because it is the uncomfortable half of the finding."""
    def rate(names: set[str]) -> float:
        killed = sum(c["killed"] for n, c in OPERATORS["by_kind"].items() if n in names)
        total = killed + sum(c["survived"] for n, c in OPERATORS["by_kind"].items() if n in names)
        return 100.0 * killed / total if total else 0.0

    added = set(OPERATORS["by_kind"]) - ORIGINAL_THREE
    assert rate(ORIGINAL_THREE) > rate(added), (
        "the three operators chosen first score higher than the five added later — the published "
        "score was a property of the operator set as much as of the tests"
    )


def test_a_score_is_reported_with_the_operators_that_produced_it():
    """A mutation score without its operator set is not a reproducible number."""
    assert OPERATORS["by_kind"], "the artefact must record the per-operator breakdown"
    assert OPERATORS["mutants"] == sum(
        c["killed"] + c["survived"] for c in OPERATORS["by_kind"].values()
    )


def test_every_outcome_is_recorded_not_only_the_survivors():
    """A report listing survivors alone cannot support a paired comparison at all."""
    source = (REPO / "eval" / "mutation.py").read_text()
    assert '"outcomes"' in source, (
        "pairing two mutants at one site needs to know the other one ran, which a survivor list "
        "cannot say"
    )


# ---------------------------------------------------------------------------
# Round 97 (cont.): the paired result, unsampled.
#
# `--kinds comparison,boundary` with no `--limit` gives every comparison site BOTH mutants, so a
# survivor whose partner is absent cannot be confused with one whose partner was killed.
#
# MEASURED over 339 sites: of the 55 pairs where the suite distinguishes the two mutations, it
# catches the inversion and misses the off-by-one at every single one — 55 to 0. Exact binomial
# two-sided p = 5.6e-17. Killing an off-by-one implies killing the inversion, so `boundary` is
# strictly sharper and `comparison` strictly redundant beside it.
# ---------------------------------------------------------------------------

PAIRED = json.loads((REPO / "eval" / "data" / "mutation_paired.json").read_text())


def _paired_sites() -> dict:
    """(file, line) -> the kinds that SURVIVED there. Absent kinds were killed.

    Sound only because the run was unsampled: with `--limit` an absent kind could mean "never ran".
    """
    sites: dict[tuple[str, int], set[str]] = {}
    for entry in PAIRED["survivors"]:
        sites.setdefault((entry["file"], entry["line"]), set()).add(entry["kind"])
    return sites


def test_the_paired_run_covered_only_the_two_operators_and_did_not_sample():
    """Both premises of the analysis, asserted rather than assumed."""
    assert set(PAIRED["by_kind"]) == {"comparison", "boundary"}
    counts = PAIRED["by_kind"]
    ran = {k: c["killed"] + c["survived"] for k, c in counts.items()}
    assert ran["comparison"] == ran["boundary"], (
        "every comparison site yields exactly one of each; unequal totals mean the run sampled, "
        "and the pairing below would be measuring the sampling"
    )


def test_killing_the_off_by_one_always_implies_killing_the_inversion():
    """The round-97 finding, and the strongest statement the mutation work produced.

    A site where the off-by-one died and the inversion lived would be a test that distinguishes a
    boundary shift but not a branch reversal — mechanically close to impossible, and MEASURED it
    never happens in 339 sites.
    """
    sites = _paired_sites()
    backwards = [
        site for site, survived in sites.items()
        if "comparison" in survived and "boundary" not in survived
    ]
    assert not backwards, (
        f"{len(backwards)} site(s) caught the off-by-one and missed the inversion, which inverts "
        f"the difficulty ordering the operator set rests on: {backwards[:5]}"
    )


def test_the_off_by_one_is_the_survivor_at_every_discordant_site():
    """The same fact stated the other way, with the counts the ledger publishes."""
    sites = _paired_sites()
    only_boundary = sum(1 for s in sites.values() if s == {"boundary"})
    only_comparison = sum(1 for s in sites.values() if s == {"comparison"})
    assert only_comparison == 0
    assert only_boundary >= 20, (
        "too few discordant pairs to say anything; the two operators would be interchangeable"
    )


def test_the_unsampled_scores_are_the_ones_the_documents_quote():
    """Round 97 first published a sampled table and corrected it. The corrected figures must stand."""
    assert PAIRED["by_kind"]["comparison"]["score"] < 50.0
    assert PAIRED["by_kind"]["boundary"]["score"] < PAIRED["by_kind"]["comparison"]["score"]
    ledger = (REPO / "docs" / "research-verification.md").read_text()
    assert "35.4%" in ledger and "18.9%" in ledger, (
        "the unsampled figures are the answer to 'how many comparison sites are protected'; the "
        "sampled ones weight every module equally regardless of size"
    )
