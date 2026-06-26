"""Per-sentence scoring tests (lite tier)."""

from __future__ import annotations

import json

from untell.scripts.sentences import main, score_sentences, split_sentences


def test_split_sentences():
    assert split_sentences("One. Two! Three? Done.") == ["One.", "Two!", "Three?", "Done."]
    assert split_sentences("") == []


def test_score_sentences_shape():
    r = score_sentences(
        "Furthermore, the system operates predictably and uniformly. It broke. Twice.",
        tier="lite",
        threshold=0.30,
    )
    assert len(r["sentences"]) >= 2
    for row in r["sentences"]:
        assert 0.0 <= row["ai"] <= 1.0
        assert isinstance(row["flagged"], bool)
        assert row["text"]
    assert isinstance(r["flagged"], list)
    assert all(isinstance(s, str) for s in r["flagged"])


def test_cli_json(capsys):
    rc = main(["Furthermore, the formulaic system operates predictably throughout.", "--tier", "lite", "--json"])
    assert rc == 0
    parsed = json.loads(capsys.readouterr().out)
    assert "sentences" in parsed and "flagged" in parsed


def test_cli_empty_returns_2(capsys):
    assert main(["   "]) == 2


def test_flagging_is_relative_not_a_flood():
    # Regression: per-sentence targeting must not flag EVERY sentence on short text (the old
    # absolute-threshold + single-sentence burstiness degeneracy). It caps to the worst ~third.
    text = "One. Two. Three. Four. Five. Six. Seven. Eight. Nine."
    r = score_sentences(text, tier="lite", threshold=0.30)
    n = len(r["sentences"])
    assert n == 9
    assert len(r["flagged"]) <= (n + 2) // 3  # at most the worst third
    assert "note" in r


def test_top_caps_flagged_count():
    text = "Moreover, the system performs. Furthermore, it operates. Additionally, it functions. Also, it runs."
    r = score_sentences(text, tier="lite", threshold=0.0, top=1)  # threshold 0 => all eligible
    assert len(r["flagged"]) <= 1


def test_single_short_sentence_not_auto_max():
    # A single short sentence has undefined burstiness; it must not be auto-scored ~AI.
    from untell.detectors.perplexity_burstiness import lite_score

    assert lite_score("The cat sat.") < 0.9
