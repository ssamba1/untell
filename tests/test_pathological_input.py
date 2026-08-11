"""Every public entry point must survive input nobody designed for.

Probed by hand first, across 15 pathological inputs: empty, whitespace, a single character, digits
only, 400 characters with no space, a bare URL, a code fence, a markdown table, emoji, mixed
script, 300 repetitions of one word, and a string carrying NUL and SOH. Nothing raised and nothing
returned nonsense — so this file is a guard on a property the code already has, not a bug report.

That is the point of writing it down. "It happens to work today" and "it is required to work" look
identical until someone adds a transform that assumes at least one sentence, and the difference is
whether a test fails or a user sees a traceback.

Kept to the contract — does not raise, returns the documented type, never silently produces None —
rather than to specific outputs. Asserting what the rewriter *does* to a code fence would freeze a
judgement call; asserting it does not crash on one freezes the thing that matters.
"""

from __future__ import annotations

import pytest

from untell.humanness import humanness
from untell.scripts.score import score_text
from untell.scripts.tells import score_tells

PATHOLOGICAL = {
    "empty": "",
    "whitespace_only": "   \n\t  ",
    "one_char": "a",
    "one_word": "Hello",
    "punctuation_only": "!!! ??? ...",
    "digits_only": "1 2 3 4 5 6 7 8 9 10 11 12 13 14 15",
    "no_spaces": "a" * 400,
    "url_only": "https://example.com/a/b?c=d&e=f",
    "code_fence": "```python\ndef f(x):\n    return x + 1\n```",
    "markdown_table": "| a | b |\n|---|---|\n| 1 | 2 |",
    "emoji": "The results were great 🎉🎉🎉 and everyone agreed 👍 it was a huge success overall.",
    "mixed_script": "The framework 框架 leverages 强大 a robust approach to deliver outcomes at scale.",
    "one_repeated_word": "and " * 300,
    "newlines_only": "\n\n\n\n\n",
    "control_chars": "\x00\x01 text after control chars",
}

IDS = sorted(PATHOLOGICAL)
CASES = [(name, PATHOLOGICAL[name]) for name in IDS]


def test_the_battery_is_not_empty() -> None:
    """A refactor that emptied the dict would make every parametrised test below vacuous."""
    assert len(CASES) >= 12


@pytest.mark.parametrize("name,text", CASES, ids=IDS)
def test_score_tells_survives(name: str, text: str) -> None:
    result = score_tells(text)
    assert isinstance(result["tells"], int) and result["tells"] >= 0
    assert isinstance(result["words"], int) and result["words"] >= 0
    assert isinstance(result["tells_per_100w"], (int, float))
    # A rate computed from zero words is a division by zero waiting to happen.
    if result["words"] == 0:
        assert result["tells_per_100w"] == 0


@pytest.mark.parametrize("name,text", CASES, ids=IDS)
def test_humanness_survives_and_stays_in_range(name: str, text: str) -> None:
    value = humanness(text, tier="lite")
    assert isinstance(value, float)
    assert 0.0 <= value <= 100.0, f"{name}: humanness returned {value}, outside 0-100"


@pytest.mark.parametrize("name,text", CASES, ids=IDS)
def test_score_text_survives(name: str, text: str) -> None:
    result = score_text(text, tier="lite")
    assert 0.0 <= result["max"] <= 1.0, f"{name}: max={result['max']}"
    assert isinstance(result["flagged"], bool)


@pytest.mark.parametrize("name,text", CASES, ids=IDS)
def test_the_loop_survives_and_never_returns_none(name: str, text: str) -> None:
    """The loop may decline to change anything — that is a legitimate answer for a code fence or an
    empty string. What it may not do is raise, or hand back something that is not a string."""
    from untell.rewriter import get_rewriter
    from untell.scripts.run import untell_text

    result = untell_text(text, tier="lite", max_iters=1, best_of=2, rewriter=get_rewriter("composite"))
    assert isinstance(result, dict)
    assert isinstance(result.get("final"), str), f"{name}: final is {type(result.get('final'))}"
    # An error is an acceptable outcome, but then the text must come back untouched rather than
    # half-rewritten — a partially transformed string paired with an error is the worst of both.
    if "error" in result:
        assert result["final"] == text


def test_locking_round_trips_on_every_pathological_input() -> None:
    """Restore must be exact even when there is nothing to lock, or nothing but markup."""
    from untell.scripts.preserve import lock, restore

    for name, text in CASES:
        masked, spans = lock(text)
        assert restore(masked, spans) == text, f"{name}: lock/restore is not a round trip"


# --- scoring must not depend on which space character was typed ---------------------------------
# A non-breaking space is visually identical to a space and is what copying out of Word, a web page
# or a PDF produces. MEASURED on 10 HC3 pairs at full tier, replacing every space with U+00A0:
# human text went 5/10 -> 9/10 flagged, mean P(AI) 0.4322 -> 0.7801, hc3_roberta alone moving by
# 0.9990. AI text was unaffected, so the entire effect was false accusations of human writers.
#
# `scrub_hidden` already normalised these, so the rewrite loop was safe. `score_text` — behind
# `untell score`, `/score` and the MCP `score` tool — was not.

UNICODE_SPACES = {
    "nbsp": "\u00a0",
    "narrow_nbsp": "\u202f",
    "en_space": "\u2002",
    "em_space": "\u2003",
    "ideographic": "\u3000",
    "medium_math": "\u205f",
}

_PROSE = (
    "The committee met on Tuesday and nobody could agree about the budget. "
    "I left early because the room was too warm and the coffee had run out. "
    "We are supposed to reconvene next month, assuming anyone remembers."
)


@pytest.mark.parametrize("name", sorted(UNICODE_SPACES), ids=sorted(UNICODE_SPACES))
def test_score_is_unchanged_by_a_unicode_space(name: str) -> None:
    from untell.scripts.score import score_text

    plain = score_text(_PROSE, tier="lite")
    swapped = score_text(_PROSE.replace(" ", UNICODE_SPACES[name]), tier="lite")
    assert swapped["max"] == pytest.approx(plain["max"], abs=1e-9), (
        f"{name} changed P(AI) from {plain['max']:.4f} to {swapped['max']:.4f} on identical words"
    )
    assert swapped["flagged"] == plain["flagged"]


def test_normalisation_leaves_ordinary_prose_alone() -> None:
    """Guards the guard. Folding everything to one space would pass the tests above and would also
    destroy the spacing signal the detectors are calibrated on."""
    from untell.scripts.score import _normalise_ws

    assert _normalise_ws(_PROSE) == _PROSE


def test_a_single_space_run_is_still_collapsed() -> None:
    """The behaviour that was already there, kept: runs of two or more collapse to one."""
    from untell.scripts.score import _normalise_ws

    assert _normalise_ws("a  b") == "a b"
    assert _normalise_ws("a\t\tb") == "a b"


@pytest.mark.parametrize("name", sorted(UNICODE_SPACES), ids=sorted(UNICODE_SPACES))
def test_the_tell_catalogue_is_unchanged_by_a_unicode_space(name: str) -> None:
    """Every multi-word pattern is written with a literal space, so a non-breaking space defeats
    it: "in conclusion" does not match "in\u00a0conclusion". MEASURED on this paragraph, 5 tells
    became 3 and humanness moved 37.4 -> 43.9 — an under-report for anyone pasting out of Word, and
    a one-keystroke evasion of our own catalogue for anyone who notices."""
    from untell.scripts.tells import score_tells

    ai_prose = (
        "Moreover, the framework leverages a robust approach to deliver outcomes at scale. "
        "Furthermore, it is important to note that this significantly enhances overall efficiency. "
        "In conclusion, this represents a substantial advancement in the field of study today."
    )
    plain = score_tells(ai_prose)
    assert plain["tells"] >= 4, "fixture no longer carries enough tells to detect a loss"
    swapped = score_tells(ai_prose.replace(" ", UNICODE_SPACES[name]))
    assert swapped["tells"] == plain["tells"], (
        f"{name} hid {plain['tells'] - swapped['tells']} of {plain['tells']} tells"
    )
    assert swapped["words"] == plain["words"]


def test_one_folding_rule_serves_both_callers() -> None:
    """Scoring and the tell catalogue both need this, and both got it wrong independently. The rule
    lives in one module so the next caller inherits it instead of re-deriving a narrower version —
    which is exactly how `_normalise_ws` came to be scoped to `[ \t]{2,}` while meaning to cover
    spacing in general."""
    from untell.scripts import tells as tells_mod
    from untell.scripts.score import fold_unicode_spaces as from_score
    from untell.text_split import fold_unicode_spaces as canonical

    assert from_score is canonical
    assert tells_mod.fold_unicode_spaces is canonical


# --- a sentinel hides tells, and only ever hides them -------------------------------------------
# The loop's tells tie-break used to count on the MASKED candidate while its detector score counted
# on the restored one. MEASURED over 120 HC3+RAID texts, 91 of which lock at least one span: the
# two views disagree on 44%, by a mean of 3.33 tells and up to 27 — and the minimum delta is +0, so
# masking never over-counts. The texts that lock spans are the ones carrying citations and numbers,
# which is the academic register this repo targets.


def test_masking_never_invents_tells_and_sometimes_hides_them() -> None:
    """Both halves matter. If masking could ADD a tell the fix would be a trade rather than a
    correction, and if it never hid one there would be nothing to correct."""
    from untell.scripts.preserve import lock, restore
    from untell.scripts.tells import score_tells

    paper = (
        "Moreover, the framework leverages a robust approach to deliver outcomes at scale "
        "(Smith 2020). Furthermore, it is important to note that accuracy improved by 12.4% "
        "over the baseline of Jones (2019). In conclusion, this represents a substantial "
        "advancement, delving into the rich tapestry of the field as reported by 47 studies."
    )
    masked, mapping = lock(paper)
    assert mapping, "fixture no longer locks anything, so it cannot exercise the difference"
    hidden = score_tells(restore(masked, mapping))["tells"] - score_tells(masked)["tells"]
    assert hidden >= 0, (
        f"masking INVENTED {-hidden} tells — the tie-break would then be trading one error for "
        "another rather than correcting one"
    )


def test_the_loop_counts_tells_on_restored_text() -> None:
    """The fix itself. Reading the source is brittle, but the alternative is asserting on a
    tie-break that only fires among candidates within _TELLS_EPS of each other — measured as no
    observable output change on 14 RAID texts, so there is no behaviour to assert on."""
    import inspect

    from untell.scripts import run

    source = inspect.getsource(run)
    assert "score_tells(restore(candidate, mapping))" in source, (
        "the tells tie-break no longer counts on the restored candidate; a sentinel hides tells "
        "and never adds them, so counting on the masked text systematically under-reads"
    )


# --- invisible characters: stripped for the tell count, warned about for the score ---------------
# A zero-width space or soft hyphen between every character shatters the word count. MEASURED on a
# 209-word HC3 answer: 889 words and 436 tells against 209 and 23, with 433 of the extra tells
# coming from repeated_phrasing, because single-character fragments repeat constantly.
#
# The two surfaces take opposite decisions on purpose. A tell count describes the WRITING, and
# "889 words" is a false description, so score_tells strips. score_text describes what a DETECTOR
# would say about the exact string being submitted, and a real detector sees those characters too,
# so it warns instead of silently scoring a document that does not exist.

INVISIBLES = {
    "zero_width_space": "\u200b",
    "zero_width_non_joiner": "\u200c",
    "word_joiner": "\u2060",
    "soft_hyphen": "\u00ad",
    "bom": "\ufeff",
}


def _inject(text: str, ch: str) -> str:
    return " ".join(ch.join(w) for w in text.split(" "))


@pytest.mark.parametrize("name", sorted(INVISIBLES), ids=sorted(INVISIBLES))
def test_the_tell_count_ignores_invisible_characters(name: str) -> None:
    from untell.scripts.tells import score_tells

    plain = score_tells(_PROSE)
    injected = score_tells(_inject(_PROSE, INVISIBLES[name]))
    assert injected["words"] == plain["words"], (
        f"{name} changed the word count from {plain['words']} to {injected['words']} — every "
        "number in the result is derived from it"
    )
    assert injected["tells"] == plain["tells"]


def test_a_soft_hyphen_is_not_an_attack() -> None:
    """Justified PDF text is full of them, so this is the ordinary case rather than the adversarial
    one, and it is the reason the fix is not gated behind an opt-in."""
    from untell.scripts.tells import score_tells

    assert score_tells(_inject(_PROSE, "\u00ad"))["words"] == score_tells(_PROSE)["words"]


@pytest.mark.parametrize("name", sorted(INVISIBLES), ids=sorted(INVISIBLES))
def test_the_score_warns_rather_than_stripping(name: str) -> None:
    """The opposite decision, and the test says so: the score must still reflect the real string."""
    from untell.scripts.score import score_text

    warning = score_text(_inject(_PROSE, INVISIBLES[name]), tier="lite").get("warning") or ""
    assert "invisible character" in warning, warning


def test_clean_prose_gets_no_invisible_warning() -> None:
    """Guards the guard: warning on everything would pass the test above and mean nothing."""
    from untell.scripts.score import _invisible_char_warning

    assert _invisible_char_warning(_PROSE) is None


def test_the_invisible_warning_names_the_direction_and_the_remedy() -> None:
    """A caveat that only says "this affects the score" leaves the reader unable to act.

    MEASURED on 20 HC3 pairs with a zero-width space between every character: AI text moved
    -0.1943 and its verdict flipped to CLEAN on 14 of 20; human text moved -0.0600. The effect is
    overwhelmingly to make AI text look human, so a clean result on such input is not evidence —
    and that is the opposite direction from the non-breaking space in Result 51, which produced
    false accusations of humans.
    """
    from untell.scripts.score import _invisible_char_warning

    warning = _invisible_char_warning("a\u200bb") or ""
    # The score impact these once described is GONE — the detectors were fixed to normalise
    # these characters (0.0000 movement at both tiers), so a caveat claiming the score moves
    # would now be a false claim. What remains true, and is what the caveat must say: the
    # characters are still in the user's text and will travel with it.
    assert "still IN YOUR TEXT" in warning, warning
    assert "untell scrub" in warning, "the caveat must name the command that fixes it"


def test_humanness_surfaces_the_invisible_caveat(caplog: pytest.LogCaptureFixture) -> None:
    """`humanness` returns a bare float, so every caveat score_text produced is discarded. This one
    cannot be: it shifts the number with nothing visible to the reader."""
    import logging

    import untell.humanness as mod

    mod._WARNED_INVISIBLE = False
    with caplog.at_level(logging.WARNING, logger=mod.logger.name):
        mod.humanness(_inject(_PROSE, "\u200b"), tier="lite")
    assert "invisible characters" in caplog.text, caplog.text


def test_humanness_is_quiet_on_clean_text(caplog: pytest.LogCaptureFixture) -> None:
    """Guards the guard: warning on everything would pass the test above."""
    import logging

    import untell.humanness as mod

    mod._WARNED_INVISIBLE = False
    with caplog.at_level(logging.WARNING, logger=mod.logger.name):
        mod.humanness(_PROSE, tier="lite")
    assert "invisible characters" not in caplog.text


# --- homoglyphs: the strongest evasion measured, and invisible to a reader ------------------------
# MEASURED on 15 HC3 pairs, mapping a/e/o/p/c to Cyrillic lookalikes: AI text moved -0.2884 and its
# verdict flipped to CLEAN on 13 of 15. `score_tells` is already immune because it scrubs, and
# scrubbing maps these back to ASCII — a fix written for invisible characters that turned out to
# cover this too. `score_text` deliberately does not scrub, so it warns.

_HOMOGLYPHS = {"a": "\u0430", "e": "\u0435", "o": "\u043e", "p": "\u0440", "c": "\u0441"}


def _homoglyph(text: str) -> str:
    return "".join(_HOMOGLYPHS.get(ch, ch) for ch in text)


def test_homoglyph_substitution_is_warned_about() -> None:
    from untell.scripts.score import score_text

    warning = score_text(_homoglyph(_PROSE), tier="lite").get("warning") or ""
    assert "homoglyph" in warning, warning
    assert "still in your text" in warning.lower(), (
        "the score impact is gone; what remains is that the substitution travels with the text"
    )


def test_the_tell_count_is_immune_to_homoglyphs() -> None:
    """Not a separate fix — scrubbing for invisible characters covered this for free."""
    from untell.scripts.tells import score_tells

    assert score_tells(_homoglyph(_PROSE))["tells"] == score_tells(_PROSE)["tells"]
    assert score_tells(_homoglyph(_PROSE))["words"] == score_tells(_PROSE)["words"]


def test_real_cyrillic_text_is_not_flagged_as_homoglyphs() -> None:
    """The discrimination that makes this usable. Legitimate multilingual text puts whole words in
    another script; homoglyph substitution puts one letter inside an English word. Warning on the
    former would fire on every quotation of Russian."""
    from untell.scripts.score import _homoglyph_warning

    assert _homoglyph_warning("The sign said привет which means hello, and we moved on.") is None
    assert _homoglyph_warning(_PROSE) is None


# --- verify is the verdict surface, so it is where an evasion does the most damage ---------------


def test_verify_carries_the_evasion_caveats() -> None:
    """`verify` produces a pass/fail and an exit code — exactly what the evasions flip. It was
    reporting PASS on injected text in silence while `score_text` warned about the same input."""
    from untell.scripts.verify import verify

    assert verify(_PROSE, tier="lite").get("warning") is None
    assert "invisible" in (verify(_inject(_PROSE, "\u200b"), tier="lite").get("warning") or "")
    assert "homoglyph" in (verify(_homoglyph(_PROSE), tier="lite").get("warning") or "")


def test_the_verify_caveat_is_printed_after_the_verdict() -> None:
    """Before it would be skimmed past. The verdict is what the reader came for, and a PASS
    obtained this way is the one to distrust."""
    from untell.scripts.verify import _render, verify

    lines = [ln for ln in _render(verify(_inject(_PROSE, "\u200b"), tier="lite")).splitlines() if ln]
    assert "WARNING" in lines[-1], lines[-3:]
    assert any("CHECKER" in ln or "FAILS" in ln for ln in lines[:-1]), lines


# --- scrub=False keeps the payload in the OUTPUT, and used to say nothing ------------------------


def test_no_scrub_reports_the_payload_it_carries() -> None:
    """`scrub=False` is a legitimate request, but it is not obvious that the OUTPUT still carries
    the characters. MEASURED on one HC3 answer with a zero-width space between every character:
    701 survive into `final`, and the result dict said nothing at all. Those characters flip an AI
    verdict to clean on 14 of 20 texts, so a caller shipping this output is shipping an evasion
    payload they may not know is there."""
    from untell.rewriter import get_rewriter
    from untell.scripts.run import untell_text

    rw = get_rewriter("composite")
    injected = _inject(_PROSE, "\u200b")
    kept = untell_text(injected, tier="lite", max_iters=1, best_of=2, rewriter=rw, scrub=False)
    assert "\u200b" in kept["final"], "fixture no longer carries the payload through"
    assert "scrub=False" in (kept.get("warning") or ""), kept.get("warning")


def test_scrubbing_removes_it_and_says_nothing() -> None:
    """The default path has nothing to report — the characters are gone. A warning here would be
    noise about a problem that no longer exists."""
    from untell.rewriter import get_rewriter
    from untell.scripts.run import untell_text

    rw = get_rewriter("composite")
    scrubbed = untell_text(
        _inject(_PROSE, "\u200b"), tier="lite", max_iters=1, best_of=2, rewriter=rw, scrub=True
    )
    assert "\u200b" not in scrubbed["final"]
    # The SCRUB caveat specifically, not the field. `warning` now merges every caveat a run
    # produced \u2014 the score-level "lite tier on the stdlib path" note lands here too \u2014 so `is None`
    # stopped meaning "nothing to report about scrubbing" and started meaning "nothing to report
    # about anything", which is a different and much stronger claim than this test is making.
    said = (scrubbed.get("warning") or "").lower()
    assert "hidden" not in said, scrubbed.get("warning")
    assert "scrub" not in said, scrubbed.get("warning")


def test_clean_text_with_no_scrub_is_not_warned_about() -> None:
    """Guards the guard: warning whenever scrub is off would fire on every such run."""
    from untell.rewriter import get_rewriter
    from untell.scripts.run import untell_text

    rw = get_rewriter("composite")
    out = untell_text(_PROSE, tier="lite", max_iters=1, best_of=2, rewriter=rw, scrub=False)
    # As above: assert the absence of the carried-payload caveat, not the absence of all caveats.
    assert "hidden" not in (out.get("warning") or "").lower(), out.get("warning")
    assert "scrub" not in (out.get("warning") or "").lower(), out.get("warning")
