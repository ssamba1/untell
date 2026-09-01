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

from pathlib import Path

import pytest

from eval import litreview

CACHE = Path(__file__).resolve().parent.parent / ".anthology-cache"

needs_corpus = pytest.mark.skipif(
    not (CACHE.exists() and any(CACHE.glob("*.xml"))),
    reason="Anthology corpus not cached (run `python -m eval.litreview --download`)",
)


def _abstract_entries() -> dict:
    """id -> {title, abstract} for the cached corpus."""
    return {p["id"]: p for p in litreview.load_abstracts(CACHE)}


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
        "multilingual/cross-lingual": "a multilingual benchmark for machine-generated text",
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


# --- the detection filter must not drift on either side ------------------------------------------
#
# `DETECTION` gates every topic count and therefore the ratio the strategy rests on. It once carried
# a bare `detector` alternative, which matched Chinese spelling correction, hallucination detection
# in machine translation, sarcasm and out-of-distribution detection: MEASURED, 213 of 526 matches —
# 40% — arrived that way. Tightening it is only safe if RECALL is pinned too, because losing
# on-topic papers biases the topics unevenly while leftover noise is roughly flat.

ON_TOPIC = [
    "2025.acl-long.1292",      # author roles and detection
    "2026.customnlp4u-1.1",    # BAID, bias assessment of AI detectors
    "2026.eacl-srw.20",        # the Czech disconfirmation — dropped by a phrase-only filter
    "2026.findings-acl.990",   # TTP-Detect, third-party watermark verification
    "2026.acl-long.663",       # the American newspapers audit
    "2024.acl-long.674",       # RAID
    "2025.emnlp-main.971",     # DivScore
    "2026.findings-acl.380",   # ExaGPT
    "2024.emnlp-demo.35",      # LLM-DetectAIve
]

OFF_TOPIC = [
    "2023.acl-long.570",       # Chinese spelling check
    "2023.acl-long.650",       # factual errors in summarization
    "2023.acl-long.717",       # out-of-domain detection with pre-trained LMs
    "2023.acl-long.478",       # multi-modal knowledge retrieval
]


def _matches(entry: dict) -> bool:
    return bool(litreview.DETECTION.search(entry["title"] + " " + entry["abstract"]))


@needs_corpus
@pytest.mark.parametrize("pid", ON_TOPIC)
def test_a_paper_the_strategy_cites_is_still_counted(pid):
    """Recall. Dropping any of these silently changes a published ratio, and the Czech result is the
    one that disconfirms part of our own thesis — losing it would bias the corpus toward agreeing
    with us."""
    index = _abstract_entries()
    if pid not in index:
        pytest.skip(f"{pid} not in the cached volumes")
    assert _matches(index[pid]), f"{pid} is cited by the strategy but no longer counts as detection"


@needs_corpus
@pytest.mark.parametrize("pid", OFF_TOPIC)
def test_a_paper_about_some_other_kind_of_detection_is_not_counted(pid):
    """Precision. These are what a bare `detector` alternative let in."""
    index = _abstract_entries()
    if pid not in index:
        pytest.skip(f"{pid} not in the cached volumes")
    assert not _matches(index[pid]), f"{pid} is not machine-generated-text detection but counts as it"


# --- the noise floor ------------------------------------------------------------------------------
#
# Round fifty-seven measured that 13.8% of the detection corpus is a different detection problem —
# hallucination, fake news, toxicity — and that removing all of it moves no topic share by more than
# 1.7 points. That was a one-off script. Shipping it means anyone reproducing the survey gets the
# error term with the count, instead of a number carrying an implied precision it does not have.


def test_a_paper_about_another_detection_problem_is_counted_as_noise():
    corpus = [
        # Must pass DETECTION first, or it never reaches the noise check — real hallucination
        # papers in the corpus do, because they name LLMs. The first version of this fixture did
        # not, so it tested nothing.
        _paper("a.1", "Detecting Hallucinations in Domain-specific Question Answering",
               "An LLM hallucination detection method for question answering."),
        _paper("a.2", "Machine-generated text detection under paraphrase",
               "We detect AI-generated text after adversarial paraphrasing."),
    ]
    report = litreview.noise_floor(corpus)
    assert report["other_detection_problem"] == 1
    assert report["examples"] == ["a.1"]


def test_a_paper_naming_both_is_kept():
    """The exclusion this must not make. A genuine machine-generated-text paper that frames itself
    around misinformation is on topic, and dropping it is exactly the recall loss round thirty
    rejected — that filter dropped the Czech result disconfirming this project's own thesis."""
    corpus = [_paper("b.1", "Detecting machine-generated text in fake news pipelines",
                     "We study AI-generated text detection for misinformation.")]
    assert litreview.noise_floor(corpus)["other_detection_problem"] == 0


def test_the_report_gives_every_topic_share_both_ways():
    """A count with no error term invites being read as exact. Both columns, always."""
    corpus = [
        _paper("c.1", "Toxicity detection with a neural detector", "We detect toxic language."),
        _paper("c.2", "AI-generated text detection under paraphrase attack",
               "Adversarial paraphrasing evades the detector."),
    ]
    report = litreview.noise_floor(corpus)
    assert set(report["topics"]) == set(litreview.TOPICS)
    for row in report["topics"].values():
        assert "with" in row and "without" in row


def test_an_empty_corpus_does_not_divide_by_zero():
    report = litreview.noise_floor([])
    assert report["detection_papers"] == 0
    assert report["off_topic_share"] == 0.0


@needs_corpus
def test_the_shipped_measurement_reproduces_round_fifty_sevens_numbers():
    """The figures the ledger publishes: 80 of 578, and no share moving by more than 1.7 points. If
    the corpus or the patterns change, this fails and names the drift rather than letting a stale
    number stand."""
    report = litreview.noise_floor(litreview.load_abstracts(CACHE))
    assert report["other_detection_problem"] == 80, report["other_detection_problem"]
    assert report["detection_papers"] == 578, report["detection_papers"]
    assert report["largest_share_move"] <= 2.0, (
        f"a topic share moved {report['largest_share_move']} points when the off-topic papers were "
        f"removed — the noise is no longer flat across topics, and the ratio needs re-examining"
    )
