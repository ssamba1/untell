"""Perturbing every undefended constant, and refusing to believe the answer without a control.

Round eighty-nine counted 41 constants with no stated reason and swept five of them — the five that
looked important. Picking what to sweep is exactly the reflex the census existed to replace, so
round ninety perturbs all of them: change the constant, re-score both arms, record what moved.

MEASURED, target `lite_score`, on the arms behind the published AUROC: **0 of 35 testable constants
move the score.** That is only worth anything because of two things these tests hold in place.

**A positive control.** "0 of 35 move the score" and "the harness is broken" are the same output.
Round eighty-eight spent twenty minutes producing `0 scored` from a wrong dictionary key and caught
it only because zero was implausible; here zero is entirely plausible. So the register perturbs
`_BURST_WEIGHT` — known live from round eighty-nine's sweep — first, and **refuses to report**
unless it moves the score. It moves 99.6% of documents.

**A separate list for what cannot be tested.** Six constants are bound as function default arguments
or read at import time into another object. Rebinding the module global does not reach them, so
perturbation reports zero — the identical output to "this does not matter". They are detected
statically and listed apart, because a zero meaning "could not test" and a zero meaning "does not
matter" are the same number and opposite facts. `score.DEFAULT_THRESHOLD`, the loop threshold every
flag rate here is computed against, is one of them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval import constant_census as census
from eval import constant_influence as influence

REPO = Path(__file__).resolve().parent.parent
REGISTER = json.loads((REPO / "eval" / "data" / "constant_influence.json").read_text())
CENSUS = json.loads((REPO / "eval" / "data" / "constant_census.json").read_text())

CACHE = REPO / ".anthology-cache"
needs_corpus = pytest.mark.skipif(
    not (CACHE.exists() and any(CACHE.glob("*.xml"))),
    reason="Anthology corpus not cached (run `python -m eval.litreview --download`)",
)


def test_the_register_ran_its_control_and_the_control_passed():
    """Without this the whole report is one indistinguishable from a broken harness."""
    control = REGISTER["self_check"]
    assert control["passed"] is True
    assert control["moved_share"] > 50, (
        "the control constant must move a large share of documents; if it barely moves any, the "
        "harness is not demonstrably able to detect the constants it reports as inert"
    )
    assert control["max_score_delta"] > 0
    assert REGISTER["refused"] is False


def test_the_register_refuses_rather_than_reporting_zeros_it_cannot_justify():
    """The refusal path is the point of the control; it has to actually exist."""
    rendered = influence.render({"refused": True, "note": "control failed", "self_check": {}})
    assert rendered.startswith("REFUSED")


def test_no_undefended_constant_reaches_the_published_score():
    """The round-90 finding."""
    assert REGISTER["live"] == 0, [
        f"{r['name']} moves {r['moved_share']}% of documents" for r in REGISTER["rows"]
        if r["moved_share"] > 0
    ]
    assert REGISTER["tested"] >= 25, "too few constants tested for the zero to mean much"


def test_untestable_constants_are_listed_and_not_scored_as_zero():
    """A zero that means 'could not test' is the failure this whole module is shaped around."""
    unreachable = REGISTER["unreachable_by_perturbation"]
    assert unreachable, "at least the default-argument constants must be detected"
    names = {u["name"] for u in unreachable}
    assert "DEFAULT_THRESHOLD" in names, (
        "the loop threshold is bound as a default argument; a register that scored it 0.0000 "
        "would be reporting the most load-bearing number here as inert"
    )
    tested = {r["name"] for r in REGISTER["rows"]}
    assert not (names & tested), "a constant cannot be both untestable and tested"
    for entry in unreachable:
        assert entry["why"], "every entry must say why it could not be reached"


def test_the_static_detectors_find_the_two_capture_kinds():
    """Both detectors, on the repository itself rather than on a fixture."""
    captures = influence.default_argument_captures()
    imports = influence.import_time_uses()
    assert ("untell/scripts/score.py", "DEFAULT_THRESHOLD") in captures
    assert ("untell/scripts/score.py", "_MAX_INPUT_CHARS") in imports


def test_perturbation_restores_the_constant_even_when_scoring_raises():
    """A harness that leaks a perturbed global silently corrupts every later measurement."""
    from untell.detectors import perplexity_burstiness as pb

    original = pb._BURST_WEIGHT
    with pytest.raises(RuntimeError):
        with influence.perturbed(pb, "_BURST_WEIGHT", 0.99):
            assert pb._BURST_WEIGHT == 0.99
            raise RuntimeError("boom")
    assert pb._BURST_WEIGHT == original


def test_variants_are_sized_to_the_kind_of_number():
    """Halving a window of 2 and halving a threshold of 0.3 are different questions."""
    assert influence.variants(0.3) == [0.24, 0.375]
    assert influence.variants(100) == [50, 200]
    assert influence.variants(2) == [3]
    assert influence.variants(True) == []


def test_the_census_reads_a_comment_that_governs_a_group():
    """The defect that made round 89 publish 49 instead of 41."""
    lines = [
        "# MEASURED in round ninety: this is why all three hold these values.",
        "_ALPHA = 0.1",
        "_BETA = 0.2",
        "_GAMMA = 0.3",
    ]
    # The third constant in the group must still see the comment above the first.
    context = census._comment_context(lines, 4)
    assert "MEASURED" in context


def test_the_census_does_not_borrow_a_neighbouring_groups_comment():
    """Walking up too far would justify everything and the check could never fail."""
    lines = [
        "# MEASURED: this explains the first group only.",
        "_ALPHA = 0.1",
        "",
        "_BETA = 0.2",
        "SOMETHING = compute()",
        "_GAMMA = 0.3",
    ]
    assert "MEASURED" not in census._comment_context(lines, 6)


def test_the_corrected_count_is_the_one_published():
    """Round 89 published 49; the census now says 41 and the documents must agree."""
    assert CENSUS["named_undefended"] == 41
    for document in ("docs/index.md", "ROADMAP.md"):
        text = (REPO / document).read_text()
        if "with no stated reason" in text or "no stated reason" in text:
            assert "41" in text, f"{document} still quotes a superseded undefended count"


@needs_corpus
def test_the_committed_register_is_what_the_code_produces():
    fresh = influence.register(CACHE)
    assert fresh["live"] == REGISTER["live"]
    assert fresh["tested"] == REGISTER["tested"]
    assert fresh["rows"] == REGISTER["rows"]
