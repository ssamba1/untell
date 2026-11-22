"""The Liang et al. (2023) importer, on a miniature of the dataset's layout.

The real dataset is not vendored; these tests build its folder structure with a handful of
essays and pin the three things the importer must get right: scores align by TEXT (the score
files are not always in data.json's order), duplicate essays each get a score, and a score whose
recorded text matches no essay is dropped and counted rather than attached to the wrong one.
"""

from __future__ import annotations

import json

import pytest

from untell.bench import liang2023 as L


def _write(folder, essays, scores_by_detector):
    folder.mkdir(parents=True)
    (folder / "data.json").write_text(json.dumps([{"document": e} for e in essays]), encoding="utf-8")
    for stem, rows in scores_by_detector.items():
        (folder / f"{stem}.json").write_text(
            json.dumps([{"document": d, "score": s} for d, s in rows]), encoding="utf-8")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "GROUPS", {
        "Human_Data/TOEFL_real_91": ("toefl-non-native", "human"),
        "Human_Data/HewlettStudentEssay_real_88": ("us-8th-grade", "human"),
        "GPT_Data/CollegeEssay_gpt3_31": ("gpt3-college-essays", "ai"),
    })
    monkeypatch.setattr(L, "DETECTORS", {"GPTZero": "gptzero-2023"})
    base = tmp_path / "ChatGPT-Detector-Bias" / "Data_and_Results"
    toefl = ["I prefer to cook at home.", "Same essay twice.", "Same essay twice.", "Short one."]
    # Out of order, a duplicate scored twice, and one score for a placeholder text.
    _write(base / "Human_Data/TOEFL_real_91", toefl, {"GPTZero": [
        ("Short one.", 0.9), ("Same essay twice.", 0.8), ("I prefer to cook at home.", 0.7),
        ("Same essay twice.", 0.8)]})
    _write(base / "Human_Data/HewlettStudentEssay_real_88", ["Dear editor, computers.", "Placeholder"],
           {"GPTZero": [("Dear editor, computers.", 0.1), ("Project summaries unavailable", 0.99)]})
    _write(base / "GPT_Data/CollegeEssay_gpt3_31", ["Generated essay."], {"GPTZero": [("Generated essay.", 0.95)]})
    return tmp_path / "ChatGPT-Detector-Bias"


def test_scores_align_by_text_not_position(repo, tmp_path):
    out = tmp_path / "out"
    info = L.build(repo, out)
    rows = dict(line.split(",") for line in (out / "scores/gptzero-2023.csv").read_text().splitlines()[1:])
    assert rows["TOEFL_real_91/000"] == "0.7"  # "I prefer to cook" was third in the score file
    assert rows["TOEFL_real_91/003"] == "0.9"
    assert rows["TOEFL_real_91/001"] == rows["TOEFL_real_91/002"] == "0.8"  # both duplicates scored
    assert info["duplicate_texts"] == 1


def test_a_score_for_a_text_that_is_not_there_is_dropped_and_counted(repo, tmp_path):
    out = tmp_path / "out"
    info = L.build(repo, out)
    assert info["scores_matching_no_document"] == {"gptzero-2023": 1}
    sheet = (out / "scores/gptzero-2023.csv").read_text()
    assert "HewlettStudentEssay_real_88/001" not in sheet  # left unscored, not given 0.99


def test_cards_report_the_gap_between_groups(repo, tmp_path):
    out = tmp_path / "out"
    L.build(repo, out)
    cards = L.run_cards(out)
    g = cards[0]["false_positive_rate"]["by_group"]
    assert g["toefl-non-native"]["rate"] == 1.0 and g["us-8th-grade"]["rate"] == 0.0
    assert cards[0]["corpus"]["unscored"] == 1
    table = L.summary_table(cards)
    assert "toefl-non-native" in table and "**100%** (4/4" in table


def test_the_corpus_carries_its_source(repo, tmp_path):
    out = tmp_path / "out"
    L.build(repo, out)
    first = json.loads((out / "corpus.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert first["source"] == L.SOURCE and first["label"] == "human"


def test_published_cards_contain_no_essay_text():
    """The observatory ships scores and ids, never the essays themselves."""
    from pathlib import Path

    cards = sorted((Path(__file__).resolve().parents[1] / "docs/observatory/liang-2023/cards").glob("*.json"))
    assert len(cards) == 7
    for c in cards:
        data = json.loads(c.read_text(encoding="utf-8"))
        assert all(set(r) <= {"id", "label", "group", "author", "words", "score", "flagged"}
                   for r in data["documents"])


def test_trailing_space_summary_counts_flips_by_group():
    from untell.bench.trailing_space import summarise

    rows = [
        {"id": "a", "group": "toefl", "label": "human", "orig": 0.9, "trailing_space": 0.001},
        {"id": "b", "group": "toefl", "label": "human", "orig": 0.2, "trailing_space": 0.2},
        {"id": "c", "group": "gpt", "label": "ai", "orig": 0.95, "trailing_space": 0.01},
    ]
    s = summarise(rows)
    assert s["groups"]["toefl"]["verdict_flips"] == 1
    assert s["groups"]["toefl"]["flip_rate_among_flagged"] == 1.0
    assert s["auroc_original"] == 1.0 and s["auroc_both_with_trailing_space"] < 1.0


def test_the_published_trailing_space_data_has_no_text():
    from pathlib import Path

    data = json.loads((Path(__file__).resolve().parents[1]
                       / "docs/observatory/trailing-space/liang-2023.json").read_text(encoding="utf-8"))
    assert {"hc3_roberta", "roberta_openai"} <= set(data)
    for res in data.values():
        assert all("text" not in r for r in res["documents"])
