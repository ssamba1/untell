"""Precision is about the findings. Recall is about the defects. They are opposite questions.

Round one hundred and four completed the precision column: all eight checkers here carry a measured
share of findings that were real when somebody read them all. **None had a measured recall**, and a
checker reporting one finding and being right is 100% precise while missing forty.

Precision was measured by reading what came out. Recall has to be measured by putting defects in:
plant a known instance of exactly what a checker claims to catch, run it, and see whether it fires.

⚠️ **Recall against easy cases is worthless**, for the same reason the mutation harness needs a
positive control that moves 99.6% of documents rather than one that barely moves any. Every plant is
labelled easy or hard, and the split is reported: a checker catching 6 of 6 easy plants and 0 of 4
hard ones has a recall of 60% and a shape that matters more than the number.

MEASURED across 22 plants: **21 of 22 on the first run, 22 of 22 after one fix.**

## ✗ And the miss was a gap that a precision fix had created

`result_keys` missed a read **inside a closure over the result**. Round one hundred and two pruned
nested function bodies out of the module scan to kill false positives — `render(result)` was
contributing six — and that fix silently blinded the checker to a whole form. **No amount of reading
findings would have found it, because a blind spot produces no findings.** Only planting one did.

The scan now descends and carries the enclosing scope's origins inward; a parameter or local
assignment rebinds the name and clears what it inherited, so the false positives stay dead. Both
directions verified: 22 of 22 plants caught, and still zero findings on the repository.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from eval import checker_recall, checkers

REPO = Path(__file__).resolve().parent.parent
RECALL = json.loads((REPO / "eval" / "data" / "checker_recall.json").read_text())


def test_every_planted_defect_is_detected():
    """The measurement itself, re-run rather than read from the artefact."""
    with tempfile.TemporaryDirectory() as tmp:
        fresh = checker_recall.measure(Path(tmp))
    missed = [r["name"] for r in fresh["results"] if not r["detected"]]
    assert not missed, f"planted defects nothing caught: {missed}"
    assert fresh["planted"] == RECALL["planted"], "the artefact is stale"


def test_the_plants_include_forms_a_naive_checker_gets_wrong():
    """Recall over easy cases only measures nothing worth knowing."""
    for checker, row in RECALL["by_checker"].items():
        hard_total = int(row["hard"].split("/")[1])
        assert hard_total >= 3, f"{checker} has only {hard_total} hard plants"
    hard = [p for p in checker_recall.PLANTS if p.hard]
    assert len(hard) >= 10
    names = {p.name for p in hard}
    assert "inside a nested function that closes over it" in names, (
        "the plant that found a real blind spot must stay in the set"
    )


def test_the_closure_plant_is_the_one_that_found_a_real_gap():
    """Pinned because it is the evidence that planting beats reading for this class of defect."""
    plant = next(p for p in checker_recall.PLANTS
                 if p.name == "inside a nested function that closes over it")
    assert plant.checker == "result_keys"
    assert plant.hard is True
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "one"
        checker_recall._write_tree(root, plant)
        assert checker_recall._detects(plant, root), (
            "the closure form must stay caught; round 102's scope pruning had blinded it"
        )


def test_a_plant_that_should_not_fire_does_not(tmp_path):
    """Guards the measurement: a checker firing on everything would score 100% recall.

    A clean module with no defect must produce nothing, or the recall figure above is just the
    checker's willingness to report.
    """
    from eval import boundaries, constant_census, result_keys

    root = tmp_path / "clean"
    (root / "untell").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "untell" / "fine.py").write_text(
        "# MEASURED over 100 samples: twelve is where the rate stops moving.\n"
        "_FLOOR = 12\n\n\ndef f(n):\n    return n + 1\n"
    )
    (root / "tests" / "test_fine.py").write_text(
        "def test_x():\n    r = score_text('x')\n    return r['max']\n"
    )
    assert result_keys.reads(root, {"score_text": {"max"}}) == []
    assert boundaries.boundaries(root) == [], "no comparison, so no boundary"
    assert not [c for c in constant_census.named_constants(root) if not c["justified"]]


def test_the_register_records_recall_beside_precision():
    """Two numbers answering opposite questions; one alone is a half-measurement."""
    measured = [c for c in checkers.REGISTER if c.recall is not None]
    assert len(measured) >= 3
    for entry in measured:
        assert entry.precision is not None, (
            f"{entry.command} has recall and no precision — the pair is the point"
        )
        assert "/" in entry.recall, f"{entry.command}: recall must be a count, not a claim"


@pytest.mark.parametrize("checker", sorted({p.checker for p in checker_recall.PLANTS}))
def test_each_planted_checker_has_an_entry_in_the_register(checker):
    commands = " ".join(c.command for c in checkers.REGISTER)
    assert checker in commands, f"{checker} is measured for recall and absent from the register"
