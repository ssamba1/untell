"""Per-sentence scoring tests (lite tier)."""

from __future__ import annotations

import json

from humanize.scripts.sentences import main, score_sentences, split_sentences


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
