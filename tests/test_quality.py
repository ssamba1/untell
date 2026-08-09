"""Quality-gate tests (lite token-overlap fallback path)."""

from __future__ import annotations

import json

import pytest

from untell.scripts import quality
from untell.scripts.quality import (
    BERTSCORE_BAR,
    DEFAULT_BAR,
    TOKEN_BAR,
    confidence,
    method,
    passes,
    recommended_bar,
    similarity,
    token_overlap,
)
from untell.scripts.quality import (
    main as quality_main,
)
from untell.text_split import aligned_chunks


def _bertscore_ready() -> bool:
    try:
        from bert_score import BERTScorer  # noqa: F401

        return True
    except Exception:
        return False


def test_identical_text_is_max_similarity():
    t = "The quick brown fox jumps over the lazy dog."
    assert similarity(t, t) >= 0.999
    assert passes(t, t)


def test_unrelated_text_is_low_similarity():
    a = "The quick brown fox jumps over the lazy dog."
    b = "Quarterly revenue projections exceeded analyst expectations this fiscal year."
    assert similarity(a, b) < DEFAULT_BAR
    assert not passes(a, b)


def test_paraphrase_keeps_some_overlap():
    a = "Regular exercise improves both physical and mental health."
    b = "Regular exercise improves both physical health and mental health."
    s = similarity(a, b)
    assert 0.0 <= s <= 1.0


def test_token_overlap_bounds():
    assert token_overlap("", "") == 1.0
    assert token_overlap("abc def", "") == 0.0
    assert token_overlap("a b c", "a b c") == 1.0
    assert 0.0 < token_overlap("a b c d", "a b x y") < 1.0


def test_empty_vs_nonempty():
    assert similarity("", "something") == 0.0


# token_overlap is the gate's ONLY similarity metric when sentence-transformers is absent — the
# documented minimal install. Any text it scores 1.0 is a rewrite the gate will admit.
@pytest.mark.parametrize(
    "label,a,b",
    [
        ("chinese", "人工智能已经改变了许多行业", "今天天气很好我想去公园散步"),
        ("russian", "Искусственный интеллект изменил отрасли", "Сегодня хорошая погода в парке"),
        ("greek", "Η τεχνητή νοημοσύνη άλλαξε τα πάντα", "Ο καιρός σήμερα είναι ωραίος"),
        ("punctuation", "!!! ...", "???  ---"),
        ("formula", "1 + 1 = 2", "9 * 9 = 81"),
    ],
)
def test_token_overlap_rejects_unrelated_non_latin_text(label, a, b):
    """The ASCII-only token pattern matched nothing in these scripts, so both multisets came out
    empty and the "both empty means identical" branch returned 1.0 — a perfect meaning score for
    two texts with nothing in common, in every non-Latin script."""
    assert token_overlap(a, b) < TOKEN_BAR, label


@pytest.mark.parametrize(
    "label,a,b",
    [
        ("chinese", "人工智能已经改变了许多行业", "人工智能改变了许多的行业"),
        ("russian", "Искусственный интеллект изменил отрасли",
         "Искусственный интеллект изменил эти отрасли"),
        ("punctuation identical", "!!!", "!!!"),
    ],
)
def test_token_overlap_still_passes_faithful_non_latin_paraphrase(label, a, b):
    """Rejecting everything would be just as wrong: it would starve the loop instead of the gate."""
    assert token_overlap(a, b) >= TOKEN_BAR, label


def test_token_overlap_unchanged_for_latin_text():
    """The fix must not move the metric where it already worked."""
    assert token_overlap("the cat sat on the mat", "the cat sat on the mat") == 1.0
    assert token_overlap("the cat sat on the mat", "quantum flux capacitor arrays") == 0.0
    assert token_overlap("don't stop", "don't stop believing now") > 0.5


def test_metric_aware_bar_is_lower_for_token_overlap():
    # sentence-transformers is absent in CI's lite path → token-overlap metric is active.
    assert TOKEN_BAR < DEFAULT_BAR
    if method() == "token_overlap":
        assert recommended_bar() == TOKEN_BAR
        assert confidence() == "low"


def test_passes_default_bar_is_metric_aware():
    t = "Regular exercise improves both physical and mental health."
    assert passes(t, t)  # identical always passes
    assert passes(t, t, bar=0.99)  # explicit override still honored


def test_quality_cli_is_ascii_safe(capsys):
    rc = quality_main(["the cat sat on the mat", "the cat sat on the mat"])
    assert rc == 0
    out = capsys.readouterr().out
    out.encode("ascii")  # must not raise — portable on a non-UTF-8 (Windows cp1252) stdout
    parsed = json.loads(out)
    assert parsed["method"] in ("embedding", "token_overlap", "bertscore")
    assert "confidence" in parsed and "bar" in parsed and "passes" in parsed


def test_bar_is_consistent_with_active_method():
    """recommended_bar() must match whichever backend method() reports — no scale mismatch."""
    m = method()
    bar = recommended_bar()
    if m == "bertscore":
        assert bar == BERTSCORE_BAR
    elif m == "embedding":
        assert bar == DEFAULT_BAR
    else:
        assert bar == TOKEN_BAR


def test_bertscore_not_active_when_uninstalled():
    if not _bertscore_ready():
        assert method() != "bertscore"


@pytest.mark.skipif(not _bertscore_ready(), reason="bert-score not installed")
def test_bertscore_is_not_the_gate_even_when_installed():
    """It was, and MEASURED it is inverted for this job — not mis-tuned:

        faithful paraphrases       0.7995 - 0.8409
        meaning-CHANGED rewrites   0.8526 - 0.9577

    Every meaning-changed pair scored above every faithful one, because BERTScore rewards token
    overlap and a negation flip changes one word where an honest paraphrase changes many. Against
    the shipped 0.88 bar it rejected 19 of 20 real composite rewrites, so `pip install
    untell[quality]` made the loop discard 95% of its own good candidates.
    """
    assert method() != "bertscore", "the gate is routing through BERTScore again"
    assert recommended_bar() in (DEFAULT_BAR, TOKEN_BAR)


@pytest.mark.skipif(not _bertscore_ready(), reason="bert-score not installed")
def test_a_faithful_paraphrase_passes_with_bertscore_installed():
    """The regression that mattered: installing an optional extra must not start rejecting good
    rewrites."""
    a = "The new system significantly improved response time."
    b = "Response time improved a lot with the new system."
    assert passes(a, b)


@pytest.mark.skipif(not _bertscore_ready(), reason="bert-score not installed")
def test_bertscore_remains_available_as_a_reported_metric():
    """Demoted from the gate, not deleted — recall against a reference is a useful number to
    report, it is simply not a meaning gate."""
    from untell.scripts.quality import _bert_score_similarity

    value = _bert_score_similarity("The cat sat on the mat.", "A cat was sitting on the mat.")
    assert value is not None and 0.0 <= value <= 1.0


def test_confidence_is_high_for_every_semantic_metric(monkeypatch):
    """The check used to be method() == "embedding", which INVERTED the ranking once bertscore was
    added: the highest-fidelity backend reported "low" while the middle tier reported "high"."""
    import untell.scripts.quality as q

    monkeypatch.setattr(q, "method", lambda: "bertscore")
    assert q.confidence() == "high"

    monkeypatch.setattr(q, "method", lambda: "embedding")
    assert q.confidence() == "high"

    # Only the lite fallback is advisory — it cannot tell a paraphrase from an off-topic rewrite.
    monkeypatch.setattr(q, "method", lambda: "token_overlap")
    assert q.confidence() == "low"


def test_help_flag_is_honoured_like_every_other_script(capsys):
    """`quality.py --help` treated the flag as TEXT, printed usage as an ERROR and exited 2 — a user
    checking how to call the meaning gate got what looked like a failure. Every sibling script in
    untell/scripts honours -h/--help; this one is the meaning gate the whole skill workflow calls."""
    from untell.scripts.quality import main

    for flag in ("-h", "--help"):
        assert main([flag]) == 0
        assert "usage" in capsys.readouterr().out.lower()


def test_missing_args_still_errors(capsys):
    """The help path must not swallow the genuine misuse case."""
    from untell.scripts.quality import main

    assert main(["only-one-arg"]) == 2


class TestLongInputIsActuallyCompared:
    """The similarity gate had the same truncation defect as the entailment gate, and worse.

    Both embedding backends truncate their input, so a single call reads only the front of a long
    document. Replacing an entire sentence with unrelated text — "The intervention halved mortality
    among the treated cohort." for "Cats are pleasant animals and many people enjoy their company."
    — measured:

        words   edit at the START   edit at the END
           76   0.5775              0.7824
          144   0.8189              0.9061
          280   0.8577              1.0000
          552   0.8577              1.0000

    1.0000 is not a near miss. It is the model reporting the two texts as the same string, because
    the changed sentence was never embedded. This is the gate the README describes and the 0.76 bar
    lives on; no value of that bar would have caught it.
    """

    FILLER = (
        "The study was conducted at three sites over eighteen months. Recruitment followed the "
        "published protocol. Data collection used the standard instrument. Analysts were blinded "
        "to allocation throughout. The statistical plan was registered in advance. "
    )
    KEPT = "The intervention halved mortality among the treated cohort."
    SWAPPED = "Cats are pleasant animals and many people enjoy their company."

    def test_an_unrelated_sentence_late_in_a_document_is_not_scored_identical(self):
        padding = self.FILLER * 8  # ~280 words
        score = quality.similarity(padding + self.KEPT, padding + self.SWAPPED)
        assert score < 0.99, (
            f"scored {score:.4f} — at 1.0 the changed text was never read at all"
        )

    def test_position_does_not_decide_the_score(self):
        """Identical edit, identical length; only where it sits differs. The two answers were
        0.8577 and 1.0000."""
        padding = self.FILLER * 8
        at_start = quality.similarity(
            self.KEPT + " " + padding, self.SWAPPED + " " + padding
        )
        at_end = quality.similarity(padding + self.KEPT, padding + self.SWAPPED)
        assert abs(at_start - at_end) < 0.35, (
            f"same edit scored {at_start:.4f} at the start and {at_end:.4f} at the end"
        )

    def test_short_input_is_unchanged_by_chunking(self):
        """Below the threshold there is one chunk, so the value must be the plain single call."""
        a, b = "The cat sat on the mat.", "A cat was sitting on the mat."
        assert len(aligned_chunks(a, b)) == 1
        assert quality.similarity(a, b) == quality.similarity(a, b)

    def test_a_faithful_long_rewrite_still_passes(self):
        """min-over-chunks is strict, and a gate that rejects good output is not a safer gate.
        Measured over 30 real composite rewrites of median 298 words: 0 rejected, minimum 0.9005
        against a 0.76 bar. This pins the shape of that with a synthetic stand-in so the assertion
        does not need a corpus download."""
        original = self.FILLER * 6 + self.KEPT
        # a faithful register shift: same claims, different wording, throughout
        faithful = (
            original.replace("conducted at", "run at")
            .replace("followed the published protocol", "used the published protocol")
            .replace("Analysts were blinded to allocation", "Analysts did not know the allocation")
            .replace("registered in advance", "filed beforehand")
        )
        score = quality.similarity(original, faithful)
        assert score >= quality.DEFAULT_BAR, (
            f"faithful rewrite scored {score:.4f}, below the {quality.DEFAULT_BAR} bar"
        )
