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


def test_published_spread_reproduces_the_papers_reported_figures(tmp_path):
    """A check on our aggregation arithmetic against a peer-reviewed result rather than against
    itself. Pratama reports FAR 44.44% and MFAR 4.17% on 72 human abstracts scored by three tools;
    if `published_spread` cannot reproduce both, one of us is wrong and it is probably us.

    The fixture reconstructs the published distribution exactly: GPTZero flagged 0 of 72, ZeroGPT 12
    (9 'ai' + 3 'mixed'), DetectGPT 23 (22 + 1), overlapping so that 32 articles are flagged by at
    least one tool and 3 by a majority.
    """
    import csv as _csv

    from eval.assisted_fairness import published_spread

    # 32 articles flagged by >=1 tool; of those, 3 flagged by 2 tools (a majority of 3); 0 by all.
    rows = []
    for article in range(1, 73):
        if article <= 3:
            labels = ["human", "ai", "mixed"]        # two flags -> majority
        elif article <= 32:
            labels = ["human", "human", "ai"]        # one flag  -> union only
        else:
            labels = ["human", "human", "human"]
        for tool, label in zip(("GPTZero", "ZeroGPT", "DetectGPT"), labels):
            rows.append({"article": str(article), "text": "original", "tool": tool, "label": label})

    path = tmp_path / "results.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = _csv.DictWriter(handle, fieldnames=["article", "text", "tool", "label"])
        writer.writeheader()
        writer.writerows(rows)

    spread = published_spread(path)
    assert spread["n_articles"] == 72
    assert spread["rules"]["any"]["flagged"] == 32
    assert abs(spread["rules"]["any"]["rate"] - 0.4444) < 0.001, "published FAR not reproduced"
    assert abs(spread["rules"]["majority"]["rate"] - 0.0417) < 0.001, "published MFAR not reproduced"
    assert spread["rules"]["unanimous"]["flagged"] == 0


def test_mixed_counts_as_a_flag():
    """The 4-point difference between 40.28% and the published 44.44% is exactly this choice. An
    author told their abstract is partly AI has still been accused."""
    from eval.assisted_fairness import FLAG_LABELS

    assert "mixed" in FLAG_LABELS and "ai" in FLAG_LABELS
    assert "human" not in FLAG_LABELS


def test_the_report_says_the_subgroup_label_is_a_proxy():
    """`Status` is institutional country, not language background. The literature names that
    substitution as a defect (doi:10.1016/j.jdin.2025.10.017), so a reader of the table has to see it
    — a caveat only in the docstring is a caveat nobody reads."""
    report = {
        "tier": "lite", "false_accusation_arms": list(HUMAN_AUTHORED),
        "arms": {"human": {"Native": {"flagged": 1, "n": 10, "rate": 0.1, "ci95": [0.0, 0.4]}}},
    }
    rendered = _render(report)
    assert "INSTITUTIONAL COUNTRY" in rendered
    assert "not language background" in rendered
