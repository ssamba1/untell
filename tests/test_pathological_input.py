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
