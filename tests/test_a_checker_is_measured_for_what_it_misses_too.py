"""Precision is about the findings. Recall is about the defects. Both are inflated by bad evidence.

`eval/checkers.py` records a measured precision for every checker here, each obtained by reading
every finding. Precision and recall answer opposite questions — a checker reporting one finding and
being right is 100% precise and may be missing forty — so recall is measured by putting defects in
rather than reading what comes out.

## Why every plant is a pair

Round one hundred and six planted six defects for `cache_keys`, got **50% recall with the easy cases
missed**, and nearly published it. Three plants named their mutable global `_STATE`, and
`"_STATE".isupper()` is **True**, which this repository's convention and the checker's own docstring
both read as *immutable*. The plants contained no defect; the checker was at 100%.

Precision is inflated by a false finding; recall is **deflated** by a false plant. What caught it
was disbelief and a docstring — a judgement, not a mechanism — and round one hundred and six left
the problem open.

Every plant is now a **minimal edit of its own control**, which makes four outcomes distinguishable
where there were two:

| fires on | outcome |
|---|---|
| defective only | detected |
| neither | **the plant is empty** — round 106's error |
| both | **the control is dirty** |
| clean only | the checker is inverted |

The `cache_keys` pairs differ from their controls **only in the case of the global's name** — the
exact distinction that was got wrong — so writing the pair forces the author to say which side of
the convention each is on. MEASURED: 28 pairs, 28 detected, 0 broken.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from eval import checker_recall, checkers

REPO = Path(__file__).resolve().parent.parent
RECALL = json.loads((REPO / "eval" / "data" / "checker_recall.json").read_text())


def test_every_pair_is_detected_and_none_is_broken():
    """Re-run rather than read from the artefact."""
    with tempfile.TemporaryDirectory() as tmp:
        fresh = checker_recall.measure(Path(tmp))
    assert not fresh["broken_pairs"], [
        f"{b['checker']}/{b['name']}: {b['outcome']}" for b in fresh["broken_pairs"]
    ]
    missed = [r["name"] for r in fresh["results"] if r["outcome"] != checker_recall.DETECTED]
    assert not missed, f"planted defects nothing caught: {missed}"


def test_round_106s_malformed_plant_is_classified_as_empty_not_as_a_miss(tmp_path):
    """The mechanism, on the exact case that motivated it.

    Both sides name the global in UPPER case, so neither contains a defect. Round 106 had only the
    defective half and scored it as the checker missing something.
    """
    pair = checker_recall.Pair(
        "cache_keys", "round 106", False,
        "from functools import lru_cache\n\n_STATE = {'n': 1}\n\n\n"
        "@lru_cache(maxsize=8)\ndef f(x):\n    return x + _STATE['n']\n",
        "from functools import lru_cache\n\n_STATE = {'n': 1}\n\n\n"
        "@lru_cache(maxsize=8)\ndef f(x):\n    return x + _STATE['n'] + 1\n",
    )
    assert checker_recall.classify(pair, tmp_path, 0) == checker_recall.EMPTY_PLANT


def test_a_dirty_control_is_classified_as_such(tmp_path):
    """The other way a pair can be broken: the clean side already carries the defect."""
    pair = checker_recall.Pair(
        "cache_keys", "dirty control", False,
        "from functools import lru_cache\n\n_state = {'n': 1}\n\n\n"
        "@lru_cache(maxsize=8)\ndef f(x):\n    return x + _state['n']\n",
        "from functools import lru_cache\n\n_state = {'n': 1}\n\n\n"
        "@lru_cache(maxsize=8)\ndef f(x):\n    return x + _state['n'] + 1\n",
    )
    assert checker_recall.classify(pair, tmp_path, 1) == checker_recall.DIRTY_CONTROL


def test_a_well_formed_pair_is_detected(tmp_path):
    """The corrected version of the same plant, so the three outcomes are shown side by side."""
    pair = checker_recall.Pair(
        "cache_keys", "corrected", False,
        "from functools import lru_cache\n\n_STATE = {'n': 1}\n\n\n"
        "@lru_cache(maxsize=8)\ndef f(x):\n    return x + _STATE['n']\n",
        "from functools import lru_cache\n\n_state = {'n': 1}\n\n\n"
        "@lru_cache(maxsize=8)\ndef f(x):\n    return x + _state['n']\n",
    )
    assert checker_recall.classify(pair, tmp_path, 2) == checker_recall.DETECTED


def test_the_tool_refuses_to_report_a_recall_when_a_pair_is_broken():
    """A broken pair scores as a miss it did not commit, which is how 50% got published."""
    rendered = checker_recall.render({
        "pairs": 1, "detected": 0, "recall": 0.0,
        "broken_pairs": [{"checker": "x", "name": "y", "outcome": checker_recall.EMPTY_PLANT}],
        "by_checker": {}, "results": [],
    })
    assert "REFUSING TO REPORT" in rendered


def test_each_edit_is_small_enough_to_isolate_the_defect():
    """A pair differing everywhere isolates nothing, and its outcome means nothing."""
    for pair in checker_recall.PAIRS:
        assert pair.edit_lines() <= 4, (
            f"{pair.checker}/{pair.name} differs by {pair.edit_lines()} lines; the defect is not "
            f"isolated and a failure could not be attributed to it"
        )
        assert pair.clean != pair.defective, f"{pair.checker}/{pair.name} has an empty edit"


def test_the_plants_include_forms_a_naive_checker_gets_wrong():
    """Recall over easy cases only measures nothing worth knowing."""
    for checker, row in RECALL["by_checker"].items():
        assert int(row["hard"].split("/")[1]) >= 3, f"{checker} has too few hard plants"
    names = {p.name for p in checker_recall.PAIRS if p.hard}
    assert "inside a closure over the result" in names, (
        "the plant that found a real blind spot in round 105 must stay in the set"
    )


def test_the_cache_keys_pairs_differ_only_in_the_case_of_the_name():
    """The pairing that makes round 106's error unwritable, asserted directly."""
    case_pairs = [p for p in checker_recall.PAIRS
                  if p.checker == "cache_keys" and "_STATE" in p.clean]
    assert len(case_pairs) >= 3
    for pair in case_pairs:
        assert "_state" in pair.defective, f"{pair.name}: the defective side must be mutable"
        assert pair.clean.replace("_STATE", "_state") == pair.defective, (
            f"{pair.name}: the edit must be the case alone, or it is testing something else too"
        )


def test_the_register_records_recall_beside_precision():
    measured = [c for c in checkers.REGISTER if c.recall is not None]
    assert len(measured) >= 4
    for entry in measured:
        assert entry.precision is not None, f"{entry.command} has recall and no precision"
        assert "/" in entry.recall, f"{entry.command}: recall must be a count, not a claim"


@pytest.mark.parametrize("checker", sorted({p.checker for p in checker_recall.PAIRS}))
def test_each_planted_checker_has_an_entry_in_the_register(checker):
    commands = " ".join(c.command for c in checkers.REGISTER)
    assert checker in commands, f"{checker} is measured for recall and absent from the register"
