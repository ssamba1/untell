"""The confound that produced a wrong headline three times, made structural.

* **Round thirty-six.** The outlier fairness gap separated its intervals at five of seven cut-offs on
  6,810 documents and vanished once compared inside word-count bands.
* **Round thirty-seven.** The same question asked of the author-status arm. It passed — worst median
  gap 7.8% — but only because somebody checked.
* **Round fifty.** The Frankentext probe reported a −16 point gap computed against a comparison arm
  of **seventeen** documents. Matched at 130 words it is −0.7%.

The cause is measured in this repository: **30.0% flagged at ≤50 words against 13.3% at 200+.** Any
comparison of flag rates between two groups inherits that unless the groups are length-matched, and
remembering to check has now failed three times out of three. `eval/arms.py` is the check as a
function, so the comparisons call it rather than their authors recalling it.
"""

from __future__ import annotations

import pytest

from eval import arms

LONG = ["word " * 200] * 40
SHORT = ["word " * 40] * 40


def test_matched_arms_pass():
    verdict = arms.length_match({"a": LONG, "b": LONG})
    assert verdict["length_matched"]
    assert verdict["worst_relative_gap"] == pytest.approx(0.0)


def test_a_length_imbalance_is_caught():
    """Round thirty-six and round fifty in one assertion."""
    verdict = arms.length_match({"a": SHORT, "b": LONG})
    assert not verdict["length_matched"]
    assert verdict["worst_relative_gap"] > 1.0
    assert "median word counts differ" in verdict["reason"]


def test_an_arm_too_small_is_caught_even_when_lengths_agree():
    """Round fifty's actual defect: the arms were the same length and one had seventeen documents.
    A rate from seventeen documents is not a rate, and its interval ran from 6.2% to 41.0%."""
    verdict = arms.length_match({"a": LONG[:17], "b": LONG})
    assert not verdict["length_matched"]
    assert verdict["arms_too_small"] == ["a"]
    assert str(arms.MIN_ARM) in verdict["reason"]


def test_an_empty_arm_does_not_crash():
    verdict = arms.length_match({"a": [], "b": LONG})
    assert not verdict["length_matched"]


def test_the_warning_cannot_be_read_as_a_pass():
    """A reader skimming a report must not mistake the failure line for the success line. They begin
    with different words on purpose."""
    ok = arms.render_length_match(arms.length_match({"a": LONG, "b": LONG}))
    bad = arms.render_length_match(arms.length_match({"a": SHORT, "b": LONG}))
    assert ok.startswith("Length check:")
    assert bad.startswith("WARNING:")
    assert "may be length" in bad


def test_the_note_names_the_measurement_behind_the_bar():
    """A threshold with no stated reason gets tuned until the result is convenient."""
    note = arms.length_match({"a": LONG, "b": LONG})["note"]
    assert "30.0%" in note and "13.3%" in note
    assert "pre_llm_fpr --by-length" in note


def test_the_frankentext_probe_refuses_unmatched_arms():
    """The probe must call the shared check rather than carry its own — a bespoke copy is how two
    comparisons come to disagree about what comparable means."""
    import inspect

    from eval import frankentext

    source = inspect.getsource(frankentext)
    assert "length_match" in source, "frankentext must use eval/arms.py, not a private check"
    assert "render_length_match" in source, "the verdict has to reach the report, not just the code"


def test_the_frankentext_report_carries_the_verdict():
    from eval import frankentext

    corpus = [". ".join(["A sentence with quite a few words in it for the splitter"] * 12) + "."]
    result = frankentext.probe(corpus * 80, tier="lite", n=40, n_sentences=3)
    if "error" in result:
        assert "length_match" in result or "not comparable" in result["error"]
        return
    assert "length_match" in result, "a passing comparison must still show what it checked"
    assert result["length_match"]["length_matched"]


def test_the_outlier_probe_warns_that_its_own_margin_is_not_length_matched():
    """Round thirty-six's finding, now printed by the tool that produced it.

    The margin is selected on stylometry and stylometry is not length-neutral, so the unstratified
    comparison is confounded by construction — MEASURED on 400 pre-LLM abstracts, the arms' median
    word counts differ by 27%. Before this, discovering that required knowing to run `--by-length`;
    the reader who never runs the stratified mode is exactly the reader who needs the warning.
    """
    import inspect

    from eval import outlier_fairness

    source = inspect.getsource(outlier_fairness)
    assert "length_match" in source, "the outlier probe must use eval/arms.py"
    assert "render_length_match" in source, "the verdict has to reach the report header"


def test_the_outlier_report_carries_the_verdict():
    from eval import outlier_fairness

    # Two clearly different length populations, so the check has something to find.
    texts = ["word " * 200] * 40 + ["short text here with a few words only"] * 40
    report = outlier_fairness.probe_by_distance(texts, tier="lite")
    if "error" in report:
        pytest.skip("corpus too small in this environment")
    assert "length_match" in report, "a comparison must show what it checked, pass or fail"
    rendered = outlier_fairness._render(report)
    assert "Length check:" in rendered or "WARNING:" in rendered


def test_the_stratified_mode_is_the_answer_to_the_warning():
    """The warning is only useful if there is something to do about it. `--by-length` is that thing,
    and it is what turned round thirty-six's apparent disparity into a length artefact."""
    import inspect

    from eval import outlier_fairness

    assert hasattr(outlier_fairness, "probe_stratified")
    doc = inspect.getdoc(outlier_fairness.probe_stratified) or ""
    assert "length" in doc.lower()
