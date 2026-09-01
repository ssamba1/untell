"""A mutation sweep whose patterns no longer match is a sweep that kills nothing.

`scripts/mutation_sweep.py` breaks a line and checks a test notices. Every mutant is a literal string
that must appear in the source — so a refactor that rewrites one of those lines turns its mutant into
a no-op, and the sweep reports nine kills while testing eight things. The script itself prints STALE
and exits non-zero when that happens, but only when somebody runs it.

These tests fail in the ordinary suite instead. They do not run the mutations: that takes minutes and
edits source files, which is unsafe under `pytest-xdist`. They check that the sweep still describes
the code it claims to test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.mutation_sweep as MUT
from scripts.mutation_sweep import MUTANTS

REPO = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("path,old,new,testfile,label",
                         MUTANTS, ids=[m[4][:40] for m in MUTANTS])
def test_every_mutant_still_matches_the_source(path, old, new, testfile, label):
    """The silent failure. A mutant whose pattern has drifted is never applied, and the sweep counts
    it as killed."""
    source = (REPO / path).read_text(encoding="utf-8")
    assert old in source, (
        f"mutation `{label}` no longer matches {path} — it would be a no-op, and the sweep would "
        f"report a kill for a mutation it never made"
    )


@pytest.mark.parametrize("path,old,new,testfile,label",
                         MUTANTS, ids=[m[4][:40] for m in MUTANTS])
def test_every_mutation_actually_changes_something(path, old, new, testfile, label):
    """Applying it must alter the file.

    Checking `new not in source` was the obvious assertion and it was wrong: one mutant drops a
    trailing ` + ["words"]`, so its replacement is a SUBSTRING of the original and the check fired on
    a perfectly good mutation. The property that matters is not whether the mutated text is absent —
    it is whether performing the replacement changes anything.
    """
    assert old != new, f"mutation `{label}` is a no-op"
    source = (REPO / path).read_text(encoding="utf-8")
    assert source.replace(old, new, 1) != source, (
        f"applying `{label}` to {path} leaves the file unchanged — the sweep would report a kill "
        f"for a mutation that did nothing"
    )


@pytest.mark.parametrize("path,old,new,testfile,label",
                         MUTANTS, ids=[m[4][:40] for m in MUTANTS])
def test_every_mutant_names_a_test_file_that_exists(path, old, new, testfile, label):
    assert (REPO / testfile).exists(), f"`{label}` points at a missing test file: {testfile}"


def test_the_statistical_machinery_is_covered():
    """The sweep exists for the code where a wrong answer is invisible. A detector that scores
    slightly wrong shows up; an interval slightly too narrow turns an honest negative into a
    finding, and rounds 34 to 37 rest entirely on those intervals."""
    covered = {m[0] for m in MUTANTS}
    for required in ("eval/pre_llm_fpr.py", "eval/outlier_fairness.py",
                     "eval/length_standardized.py", "untell/scripts/score.py"):
        assert required in covered, f"the mutation sweep does not touch {required}"


# --- the vacuity pairs --------------------------------------------------------------------------


@pytest.mark.parametrize("testfile,module", MUT.VACUITY_PAIRS,
                         ids=[Path(t).stem[:44] for t, _ in MUT.VACUITY_PAIRS])
def test_every_vacuity_pair_points_at_files_that_exist(testfile, module):
    assert (REPO / testfile).exists(), f"vacuity pair names a missing test file: {testfile}"
    assert (REPO / module).exists(), f"vacuity pair names a missing module: {module}"


def test_sabotage_actually_breaks_a_module():
    """The check is worthless if `sabotage` produces something that still works. It must replace
    every public function body with a raise, and the result must still be valid Python — a syntax
    error would make every test file 'notice' for the wrong reason, reporting a clean bill of health
    from a file that never imported."""
    import ast

    source = "def a():\n    return 1\n\n\ndef b(x):\n    if x:\n        return 2\n    return 3\n"
    broken = MUT.sabotage(source)
    ast.parse(broken)  # must stay parseable
    namespace: dict = {}
    exec(compile(broken, "<sabotaged>", "exec"), namespace)  # noqa: S102
    for name in ("a", "b"):
        with pytest.raises(AssertionError, match="sabotaged"):
            namespace[name](1) if name == "b" else namespace[name]()


def test_sabotage_leaves_dunder_functions_alone():
    """`__init__` and friends are how a module loads. Breaking them turns 'the test noticed' into
    'the module would not import', which is a different and much weaker signal."""
    source = "def __getattr__(name):\n    return 1\n\n\ndef public():\n    return 2\n"
    broken = MUT.sabotage(source)
    assert "def __getattr__(name):\n    return 1" in broken
    assert broken.count("sabotaged") == 1


def test_the_vacuity_check_covers_the_modules_written_this_session():
    covered = {m for _t, m in MUT.VACUITY_PAIRS}
    for required in ("eval/outlier_fairness.py", "eval/length_standardized.py",
                     "eval/pre_llm_fpr.py", "untell/scripts/score.py",
                     "untell/scripts/sentences.py", "eval/assisted_fairness.py"):
        assert required in covered, f"no vacuity pair exercises {required}"
