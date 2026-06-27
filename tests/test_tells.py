"""Tests for the mechanical AI-tells scorer."""

from __future__ import annotations

import json

from untell.scripts.tells import main, score_tells


def test_clean_human_text_has_few_tells():
    text = "The dog barked. I went outside to check and found nothing but a cat on the fence."
    r = score_tells(text)
    assert r["tells"] == 0
    assert r["tells_per_100w"] == 0.0


def test_catches_ai_vocabulary_cluster():
    r = score_tells("We leverage robust, seamless, and innovative solutions to delve into the realm.")
    assert r["by_category"].get("ai_vocab", 0) >= 5  # leverage, robust, seamless, innovative, delve, realm


def test_catches_formulaic_transition_openers():
    r = score_tells("Furthermore, this is true. Moreover, that is also true. Overall, it works.")
    assert r["by_category"].get("formulaic_transition", 0) >= 3


def test_transition_only_counts_as_opener_not_midsentence():
    # "moreover" mid-sentence is not a paragraph-scaffolding opener; only sentence-initial counts.
    r = score_tells("This is true and moreover useful in practice every single day of the week.")
    assert r["by_category"].get("formulaic_transition", 0) == 0


def test_catches_em_dash():
    r = score_tells("This is the thing — the one that matters most of all to everyone involved.")
    assert r["by_category"].get("em_dash", 0) >= 1


def test_catches_negated_contrast():
    r = score_tells("It's not about the money, it's about the principle of the whole matter here.")
    assert r["by_category"].get("negated_contrast", 0) >= 1


def test_catches_vague_attribution():
    r = score_tells("Studies show that this works. Research suggests it is effective in most cases.")
    assert r["by_category"].get("vague_attribution", 0) >= 2


def test_catches_cliches():
    r = score_tells("In today's fast-paced world, let's dive in and shed light on the game-changer.")
    assert r["by_category"].get("cliche", 0) >= 3


def test_catches_chatbot_artifact():
    r = score_tells("Here is the rewrite. As an AI language model, I cannot have personal opinions here.")
    assert r["by_category"].get("chatbot_artifact", 0) >= 1


def test_burstiness_cv_none_for_single_sentence():
    assert score_tells("Just one sentence here with several words in it indeed today").get("burstiness_cv") is None


def test_low_burstiness_flag_on_uniform_lengths():
    # Five sentences of near-identical length => uniform => flagged.
    text = "The cat sat on the mat today. The dog ran in the park now. The bird flew over the lake here. The fish swam in the pond well. The fox hid in the den again."
    r = score_tells(text)
    assert r["burstiness_cv"] is not None
    assert r["low_burstiness"] is True


def test_more_tells_means_higher_rate():
    ai = "Furthermore, we leverage robust solutions. Moreover, studies show it's pivotal and seamless."
    human = "We use solid tools that work. People who tried it found it helped them get more done."
    assert score_tells(ai)["tells_per_100w"] > score_tells(human)["tells_per_100w"]


def test_steering_opener_not_double_counted_as_transition():
    # "Notably," opens a sentence: it must count once (steering_opener), not also as a transition.
    r = score_tells("Notably, the results were strong. The team kept going for several more weeks.")
    assert r["by_category"].get("steering_opener", 0) == 1
    assert "formulaic_transition" not in r["by_category"]
    assert r["tells"] == 1  # exactly one tell, not two


def test_in_conclusion_counts_once_as_cliche():
    r = score_tells("In conclusion, the project worked out fine and everyone went home happy that day.")
    # counted as a cliche, and NOT additionally as a formulaic_transition
    assert r["by_category"].get("cliche", 0) >= 1
    assert "formulaic_transition" not in r["by_category"]


def test_em_dash_not_counted_in_digit_ranges():
    # "2020 - 2025" and "pp. 10 - 20" are ranges, not dashes — must not inflate the em_dash count.
    r = score_tells("The study ran 2020 - 2025 across pp. 10 - 20 of the report without any issue at all.")
    assert r["by_category"].get("em_dash", 0) == 0


def test_em_dash_spaced_hyphen_between_words_still_counts():
    r = score_tells("This is the point - the one that really matters more than anything else here today.")
    assert r["by_category"].get("em_dash", 0) == 1


def test_cli_json_ascii_safe(capsys):
    rc = main(["--json", "Furthermore, we leverage robust and seamless solutions here today now."])
    assert rc == 0
    out = capsys.readouterr().out
    out.encode("ascii")  # ensure_ascii -> portable on cp1252 stdout
    parsed = json.loads(out)
    assert parsed["tells"] >= 1 and "by_category" in parsed


def test_cli_empty_input_returns_2(capsys):
    assert main(["   "]) == 2
