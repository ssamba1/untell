"""The literature survey's headline ratio must be re-derivable, not just asserted in a document.

`docs/research-verification.md` argues from a count: under 2% of ACL detection papers address false
positives or fairness, against ~30% on evasion robustness. That number carries the strategy in
ROADMAP section 7, so it needs the same treatment as every other published figure here — a way to
re-check it.

These tests pin the classifier's behaviour on synthetic abstracts (so they run with no network and
no cached corpus), which is what would catch the failure that actually matters: a regex edited into
matching nothing, silently turning a real count into zero.
"""

from __future__ import annotations

import pytest

from eval import litreview


def _paper(pid: str, title: str, abstract: str) -> dict[str, str]:
    return {"id": pid, "title": title, "abstract": abstract}


CORPUS = [
    _paper("x.1", "Detecting machine-generated text under paraphrase attack",
           "We show that adversarial paraphrasing evades every detector we test."),
    _paper("x.2", "A detector that bounds false positives",
           "We constrain the FPR of AI-generated text detection using conformal prediction."),
    _paper("x.3", "Bias in AI text detection",
           "Detectors are biased against non-native writers, raising fairness concerns."),
    _paper("x.4", "A machine translation system for low-resource languages",
           "We improve BLEU on four language pairs. Nothing here concerns detection."),
]


def test_the_detection_filter_excludes_unrelated_papers():
    """Guards the guard: if DETECTION matched everything, every ratio below would be meaningless."""
    result = litreview.survey(CORPUS)
    assert result["abstracts"] == 4
    assert result["detection_papers"] == 3, "the MT paper is not a detection paper"


@pytest.mark.parametrize("topic", sorted(litreview.TOPICS))
def test_every_topic_pattern_can_fire(topic):
    """A topic that cannot match anything would report an honest-looking zero forever.

    This is the same reachability rule the repo applies to tells, detectors and rewriters: anything
    registered must demonstrate it can fire.
    """
    probes = {
        "robustness/paraphrase": "adversarial paraphrasing evades the detector",
        "human-AI mixed/edited": "AI-polished hybrid text detection",
        "watermark": "watermark detection for generated text",
        "education/integrity": "student essay detector for academic integrity",
        "calibration/thresholds": "we calibrate the detector at TPR@1%FPR",
        "false positives/accusation": "the detector's false positive rate on human text",
        "fairness/non-native bias": "detector fairness for non-native writers",
        "disability/neurodivergence": "do detectors flag autistic and dyslexic writers",
    }
    hit = _paper("p", "AI-generated text detection", probes[topic])
    assert litreview.papers_for_topic([hit], topic), f"{topic} matched nothing it should match"


def test_topic_counts_are_over_the_detection_subset_only():
    """The published ratio is topics-within-detection. Counting over the whole corpus would inflate
    every row and quietly change what the number means."""
    noise = CORPUS + [
        _paper("y.1", "Fairness in machine translation",
               "We study bias against non-native speakers in translation quality.")
    ]
    assert litreview.survey(noise)["topics"]["fairness/non-native bias"] == 1


def test_flatten_reads_through_inline_markup():
    """Anthology titles carry <fixed-case> and <i>; reading .text alone truncates at the first tag,
    which would drop most of the abstract and silently shrink every count."""
    import xml.etree.ElementTree as ET

    element = ET.fromstring("<title>Detecting <fixed-case>AI</fixed-case> text</title>")
    assert litreview._flatten(element) == "Detecting AI text"


def test_missing_cache_reports_how_to_fix_it_rather_than_crashing(tmp_path, capsys):
    assert litreview.main(["--cache", str(tmp_path / "absent")]) == 1
    assert "--download" in capsys.readouterr().err
