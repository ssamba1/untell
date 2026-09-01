"""The AI-assisted arm scores human text an LLM polished — where the literature says detectors fail.

A flag on the `human` or `assisted_*` arms is a false accusation of a person who did the work: the
originals are 2021 abstracts, published before ChatGPT existed. These tests pin the arm taxonomy and
the reporting rules, because the ways this module could mislead are all flattering ones — counting a
generated arm as a false accusation, or presenting a subgroup gap that the sample cannot support.
"""

from __future__ import annotations

import csv

import pytest

from eval.assisted_fairness import ARMS, HUMAN_AUTHORED, _render, load_rows


def test_only_human_authored_arms_count_as_false_accusations():
    """Miscounting a fully generated arm as a false accusation would inflate the headline number in
    the direction that flatters this repo's argument."""
    assert set(HUMAN_AUTHORED) == {"human", "assisted_chatgpt", "assisted_gemini"}
    for arm in HUMAN_AUTHORED:
        assert arm in ARMS.values()
    assert "generated_chatgpt" not in HUMAN_AUTHORED
    assert "generated_gemini" not in HUMAN_AUTHORED


def test_assisted_arms_are_distinct_from_generated_arms():
    """The whole point is the difference between 'an LLM polished my writing' and 'an LLM wrote it'.
    Collapsing them would make the arm measure nothing."""
    assert ARMS["AI-Assisted ChatGPT"] != ARMS["AI-Generated ChatGPT"]
    assert len(set(ARMS.values())) == len(ARMS)


def test_rows_without_author_status_are_dropped(tmp_path):
    """A row with no Status cannot be stratified, and silently pooling it into a subgroup rate would
    put unattributed text behind a fairness claim."""
    path = tmp_path / "d.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Status", "Abstract"])
        writer.writeheader()
        writer.writerow({"Status": "Native", "Abstract": "a real abstract"})
        writer.writerow({"Status": "", "Abstract": "unattributed"})
        writer.writerow({"Status": "Non-Native", "Abstract": ""})
    rows = load_rows(path)
    assert len(rows) == 1
    assert rows[0]["Status"] == "Native"


def test_the_report_states_that_overlapping_intervals_are_not_a_finding():
    """With ~30 per group the intervals are wide. A reader who takes a point-estimate gap as a
    demonstrated bias has been misled by the layout, so the layout has to say otherwise."""
    report = {
        "tier": "lite", "false_accusation_arms": list(HUMAN_AUTHORED),
        "arms": {"human": {
            "Native": {"flagged": 4, "n": 28, "rate": 0.143, "ci95": [0.057, 0.315]},
            "Non-Native": {"flagged": 2, "n": 32, "rate": 0.062, "ci95": [0.017, 0.202]},
            "all": {"flagged": 6, "n": 60, "rate": 0.1, "ci95": [0.047, 0.202]},
        }},
    }
    rendered = _render(report)
    assert "not established" in rendered
    assert "false accusations" in rendered


@pytest.mark.parametrize("arm", ["human", "assisted_chatgpt", "assisted_gemini"])
def test_human_authored_arms_are_marked_in_the_output(arm):
    report = {
        "tier": "lite", "false_accusation_arms": list(HUMAN_AUTHORED),
        "arms": {arm: {"all": {"flagged": 1, "n": 10, "rate": 0.1, "ci95": [0.0, 0.4]}}},
    }
    assert "<- false accusations" in _render(report)
