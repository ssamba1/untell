"""Tests for the mechanical AI-tells scorer."""

from __future__ import annotations

import json

import pytest

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


def test_catches_hedge_stacking():
    r = score_tells("This could potentially work and it might eventually help in many real cases.")
    assert r["by_category"].get("hedge_stacking", 0) >= 2


def test_catches_false_range():
    r = score_tells("Whether you're a beginner or a seasoned pro, the tool fits your workflow nicely.")
    assert r["by_category"].get("false_range", 0) >= 1


def test_catches_rule_of_three_staccato():
    r = score_tells("The launch went well. Fast. Simple. Effective. Everyone on the team was pleased.")
    assert r["by_category"].get("rule_of_three", 0) == 1


def test_rule_of_three_needs_three_in_a_row():
    # Only two short sentences in a row must NOT trigger the tricolon tell.
    r = score_tells("Fast. Simple. The rest of this sentence is comfortably long and ordinary prose.")
    assert "rule_of_three" not in r["by_category"]


def test_catches_markdown_artifact():
    r = score_tells("## Key Takeaways\nThe project shipped on time and under budget this past quarter.")
    assert r["by_category"].get("markdown_artifact", 0) >= 1


def test_semicolon_crutch_needs_two():
    one = score_tells("He ran fast; then he stopped to catch his breath near the old wooden bridge.")
    two = score_tells("He ran fast; she ran faster; they both made it home before the rain came down.")
    assert "semicolon_crutch" not in one["by_category"]  # a single semicolon is ordinary
    assert two["by_category"].get("semicolon_crutch", 0) == 2


def test_new_vocabulary_terms():
    r = score_tells("Our world-class, cutting-edge, state-of-the-art platform showcasing next-level wins.")
    assert r["by_category"].get("ai_vocab", 0) >= 5


def test_no_new_category_double_counts_clean_text():
    # A plain human sentence must still score zero across ALL categories (no new false positives).
    assert score_tells("The cat knocked a mug off the table and then stared at me without any guilt.")["tells"] == 0


def test_cli_json_ascii_safe(capsys):
    rc = main(["--json", "Furthermore, we leverage robust and seamless solutions here today now."])
    assert rc == 0
    out = capsys.readouterr().out
    out.encode("ascii")  # ensure_ascii -> portable on cp1252 stdout
    parsed = json.loads(out)
    assert parsed["tells"] >= 1 and "by_category" in parsed


def test_cli_empty_input_returns_2(capsys):
    assert main(["   "]) == 2


def test_no_token_counts_in_two_categories():
    """The module's stated invariant: "a single phrase must count in exactly one category, never
    two". "boasts" is in _AI_VOCAB and _INFLATED_COPULA_RE; "showcasing" is in _AI_VOCAB and
    _PARTICIPIAL_TRAILER_RE — both used to fire twice for one token."""
    r = score_tells("The park boasts a clear path.")
    assert r["tells"] == 1, r["by_category"]

    r = score_tells("The campaign concluded, showcasing our strengths.")
    assert r["tells"] == 1, r["by_category"]


def test_longest_span_claims_the_tell():
    """_CATEGORIES is ordered for readability, not specificity (ai_vocab is first), so the richer
    multi-word construction must win on span length rather than list position."""
    r = score_tells("The campaign concluded, showcasing our strengths.")
    assert r["by_category"].get("participial_trailer") == 1
    assert "ai_vocab" not in r["by_category"]


def test_standalone_vocab_still_counts_when_no_richer_pattern_matches():
    """Dedup must not silently delete tells: "showcasing" with no comma is not a participial
    trailer, so it must still be counted as AI vocabulary."""
    r = score_tells("Our platform showcasing next-level wins.")
    assert r["by_category"].get("ai_vocab", 0) >= 1


NEGATED_CONTRAST_FIRES = [
    "It is not just a tool, it is a philosophy.",
    "It's not just a tool, it's a philosophy.",
    "That's not a bug, that's a feature.",
    "This is not merely an upgrade — it is a rethink.",
    "It isn't about speed; it's about consistency.",
    "The change is not only faster but also cheaper.",
    "Not just a refactor, but a rewrite.",
    "It was not simply a delay, it was a failure.",
]

NEGATED_CONTRAST_QUIET = [
    "It is not clear whether the change helped.",
    "That is not what I meant at all.",
    "The build did not just fail once.",
    "I could not find the file, so I made a new one.",
    "It was not raining when we left the house.",
    "This is not the version we shipped last week.",
    "Not everyone agreed with the decision.",
    "It is not about to change any time soon.",
]


@pytest.mark.parametrize("text", NEGATED_CONTRAST_FIRES)
def test_negated_contrast_is_counted(text):
    """The pattern used to require a contraction ("it's not X, it's Y") and a literal "but", so the
    uncontracted and punctuated forms - which models write at least as often - matched nothing."""
    assert score_tells(text)["by_category"].get("negated_contrast"), (
        f"negated contrast not counted in {text!r}"
    )


@pytest.mark.parametrize("text", NEGATED_CONTRAST_QUIET)
def test_ordinary_negation_is_not_a_tell(text):
    """A plain negated sentence is not the rhetorical construction. Widening the pattern must not
    turn every "not" into a tell, or the tie-break starts steering rewrites away from normal prose."""
    assert not score_tells(text)["by_category"].get("negated_contrast"), (
        f"ordinary negation falsely counted in {text!r}"
    )


class TestSignpostingCliche:
    """"It is important to note that ..." — the most common signpost in AI prose — scored as
    perfectly clean text.

    The cliche list had `it'?s (?:important|worth) (?:to note|noting)`, which matches "it's" and
    "its" but not "it is". A one-character gap in one alternation, and the whole "it is important
    to note" family walked through it. Found while investigating why single-sentence scoring was
    inverted, since tells is the signal that actually discriminates at sentence length.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "It is important to note that this matters.",
            "It should be noted that results vary.",
            "It is essential to note that timing differs.",
            "It is necessary to note the delay.",
            "It’s important to note that curly apostrophes appear constantly in AI output.",
            "it's worth noting that the old straight-quote form still works.",
        ],
        ids=["it-is-important", "should-be-noted", "essential", "necessary", "curly", "regression-its"],
    )
    def test_signpost_forms_are_counted(self, text):
        assert score_tells(text)["tells"] >= 1, f"signpost not counted: {text!r}"

    @pytest.mark.parametrize(
        "text",
        [
            "It is important that you show up on time.",
            "I noted the time and moved on.",
            "She noted the error in the log.",
            "It is worth the wait.",
            "We tried it twice and it still didn't work.",
        ],
        ids=["important-not-note", "noted-verb", "noted-error", "worth-the-wait", "plain"],
    )
    def test_ordinary_prose_is_not_flagged(self, text):
        """The pattern needs 'to note'/'noting' — 'it is important that' is ordinary English and
        flagging it would tax normal writing."""
        assert score_tells(text)["tells"] == 0, f"false positive on: {text!r}"

    def test_counted_once_not_twice(self):
        """Overlapping patterns must not double-count — the span resolver keeps the longest match."""
        r = score_tells("It is important to note that this matters.")
        assert r["tells"] == 1


class TestEveryCategoryIsReachable:
    """Every registered category must fire on a known positive.

    MEASURED FAILURE this guards against: six categories shipped with a stray control character
    where a ``\b`` word boundary was intended, so their patterns could never match anything. They
    scored zero false positives on 200 real human texts — because they matched no text at all. A
    zero is not evidence of precision unless the pattern is known to fire somewhere.
    """

    POSITIVES = {
        "ai_vocab": "We leverage a robust and seamless framework.",
        "formulaic_transition": "Moreover, the results were clear.",
        "steering_opener": "Interestingly, nobody had checked.",
        "negated_contrast": "It is not just a tool, it is a philosophy.",
        "participial_trailer": "Sales rose again, underscoring the shift.",
        "vague_attribution": "Industry reports suggest the trend will hold.",
        "cliche": "It is important to note that timing matters.",
        "sycophancy": "Great question! Let me explain.",
        # NOT "In conclusion" — that is a cliche. meta_closer is the assistant sign-off.
        "meta_closer": "I hope this helps! Let me know if you have questions.",
        "chatbot_artifact": "As an AI language model, I cannot browse the web.",
        # NOT "boasts" — it is in _AI_VOCAB too, and the span resolver awards it there.
        "inflated_copula": "The report serves as a foundation for the review.",
        "hedge_stacking": "It may perhaps possibly be somewhat useful.",
        "false_range": "Everything from marketing to quantum physics benefits.",
        "markdown_artifact": "## Key Takeaways\nThe project shipped.",
        "filler_phrase": "Due to the fact that costs rose, we paused.",
        "aphorism": "Data is the new oil for modern business.",
        "rhetorical_opener": "Here's the thing: nobody read the spec.",
        "cutoff_disclaimer": "As of my last training update, the figure was unclear.",
        "challenges_section": "The project faces several challenges going forward.",
        "notability_padding": "It has received independent coverage in national media outlets.",
    }

    def test_every_registered_category_has_a_positive_example(self):
        """The map above must cover _CATEGORIES exactly, so a new category cannot skip this test."""
        from untell.scripts.tells import _CATEGORIES

        registered = {name for name, _ in _CATEGORIES}
        assert registered == set(self.POSITIVES), (
            f"missing example for {registered - set(self.POSITIVES)}; "
            f"stale example for {set(self.POSITIVES) - registered}"
        )

    @pytest.mark.parametrize("category", sorted(POSITIVES))
    def test_category_fires_on_its_positive(self, category):
        text = self.POSITIVES[category]
        got = score_tells(text)["by_category"].get(category, 0)
        assert got, f"{category} matched nothing in {text!r} — pattern is dead"

    def test_no_stray_control_characters_in_source(self):
        """A ``\b`` written into a non-raw string becomes U+0008 and silently kills the pattern."""
        from pathlib import Path

        import untell.scripts.tells as mod

        raw = Path(mod.__file__).read_bytes()
        for ctrl in (8, 11, 12):
            assert bytes([ctrl]) not in raw, f"control byte {ctrl} in tells.py"
