"""Eight checkers, and until now no way to tell which had ever had their findings read.

Round one hundred and two ended with a pattern that had four instances and no owner: **the first
version of a static rule here is always too loose.** The claim-verification proximity rule reported
15 contradictions, all false. The citation cross-check reported 35, of which 10 were its own fault.
The cache-patch rule had one finding and it was false. The result-key checker reported 38 distinct
pairs against 8 real ones.

Each was fixed by reading every finding while the list was short enough to read, and each fix was
recorded in the round that made it — and nowhere afterwards. A reader looking at `eval/` sees eight
checkers and no way to tell which gate a commit, which have had their findings verified, and which
report a number nobody has ever checked.

MEASURED across the register: **7 of 8 shipped a first version that was too loose**, and 7 of 8 now
carry a precision figure with the method that produced it.

⚠️ **A checker with no precision figure is not a precise one, it is an unmeasured one.** These tests
keep the two apart, which is round ninety's rule turned on the checkers themselves.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from eval import checkers

REPO = Path(__file__).resolve().parent.parent


def test_every_checker_in_the_register_actually_runs():
    """A register naming a command that does not exist is worse than no register."""
    for entry in checkers.REGISTER:
        module = re.search(r"python -m (\S+)", entry.command)
        assert module, entry.command
        path = REPO / (module.group(1).replace(".", "/") + ".py")
        assert path.exists(), f"{entry.command} names {path.name}, which does not exist"


def test_every_eval_checker_has_a_register_entry():
    """A checker added without an entry is one whose reliability nobody has stated."""
    registered = {
        re.search(r"python -m (\S+)", c.command).group(1) for c in checkers.REGISTER
    }
    # Modules in eval/ that define a `main` and print findings — the shape of a checker.
    candidates = set()
    for path in sorted((REPO / "eval").glob("*.py")):
        body = path.read_text(encoding="utf-8")
        if "def main(" in body and ("findings" in body or "--json" in body):
            candidates.add(f"eval.{path.stem}")
    known_not_checkers = {
        # Measures the checkers rather than the codebase: it plants defects and counts detections,
        # so it has no findings of its own to be precise about. Excluded with a reason rather than
        # silently, because an exclusion list that grows without them is how this test stops working.
        "eval.checker_recall",
        "eval.checkers", "eval.litreview", "eval.detection_power", "eval.mutation",
        "eval.register_conformity", "eval.constant_sensitivity", "eval.pre_llm_fpr",
        "eval.length_standardized", "eval.tells_auroc", "eval.holdout", "eval.arms",
        "eval.benchmark", "eval.ceiling", "eval.compare_humanizers", "eval.datasets",
        "eval.detector_audit", "eval.eval_policy", "eval.frankentext", "eval.prove",
        "eval.report", "eval.outlier_fairness", "eval.assisted_fairness", "eval.baselines",
    }
    missing = sorted(candidates - registered - known_not_checkers)
    assert not missing, (
        f"these look like checkers and have no register entry: {missing}. Add one saying what it "
        f"checks, whether it gates, and whether its findings have ever been read."
    )


def test_a_precision_figure_is_never_stated_without_its_method():
    """A number with no method behind it is the thing this repository keeps refusing to publish."""
    for entry in checkers.REGISTER:
        if entry.precision is None:
            assert entry.how_precision_was_measured is None, (
                f"{entry.command} has a method and no figure — record the figure"
            )
        else:
            assert entry.how_precision_was_measured, (
                f"{entry.command} claims precision {entry.precision!r} with no method"
            )
            assert len(entry.how_precision_was_measured) > 60, (
                f"{entry.command}: a method short enough to be a shrug is not a method"
            )


def test_unmeasured_is_reported_as_unmeasured_not_as_clean():
    """Folding 'never checked' into 'no findings' is how a register stops being worth reading."""
    rendered = checkers.render(checkers.report())
    unmeasured = [c for c in checkers.REGISTER if c.precision is None]
    for entry in unmeasured:
        assert "UNMEASURED" in rendered
        assert entry.findings_now, f"{entry.command} reports nothing and measures nothing"


def test_the_prose_uses_the_computed_count_not_a_remembered_one():
    """A hardcoded figure beside a computed one drifts, which is this repository's oldest defect.

    The first draft of `render` said "too loose five times out of eight" while the computed value
    was seven — in the round about checker reliability.
    """
    data = checkers.report()
    rendered = checkers.render(data)
    assert f"too loose {data['first_version_was_too_loose']} times out of {data['checkers']}" \
        in rendered


def test_the_gating_flag_matches_what_the_command_does():
    """A register claiming a checker gates when its exit code says otherwise is a false assurance."""
    gating = [c for c in checkers.REGISTER if c.gates]
    assert len(gating) >= 4
    for entry in gating:
        module = re.search(r"python -m (\S+)", entry.command).group(1)
        source = (REPO / (module.replace(".", "/") + ".py")).read_text(encoding="utf-8")
        assert re.search(r"return 1 if|return 1\b", source), (
            f"{entry.command} is registered as gating but never returns a non-zero exit code"
        )


@pytest.mark.parametrize("entry", checkers.REGISTER, ids=lambda c: c.command.split()[-1])
def test_a_first_version_defect_is_recorded_where_there_was_one(entry):
    """Seven of eight had one. Keeping the record is what makes the pattern visible at all."""
    if entry.first_version_defect is not None:
        assert len(entry.first_version_defect) > 60, entry.command


def test_the_register_runs_as_a_command():
    result = subprocess.run(
        [sys.executable, "-m", "eval.checkers"], cwd=REPO, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "UNMEASURED" in result.stdout or "precision" in result.stdout
