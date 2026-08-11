"""Two floors, two meanings — the structured warning reported only the weaker one.

``_voice_key`` returns a constant below ``_MIN_VOICE_SAMPLE_WORDS`` (20), so the tie-break does not
run at all. ``voice_report``'s ``MIN_SAMPLE_WORDS`` (150) is where the same-author/cross-author
AUROC of 0.680 was measured — below it the tie-break runs, on a weak profile.

MEASURED, before the fix: a 5-word sample and a 75-word sample returned the *same* ``voice_warning``
— "the voice tie-break is close to arbitrary" — though in the first case there was no tie-break to
be arbitrary. The stderr warning has always said "disabled for this run"; the structured field is
the only channel REST and MCP callers read, and it described the case that did not happen.
"""

from __future__ import annotations

import pytest

from untell.scripts.run import _MIN_VOICE_SAMPLE_WORDS, _voice_key, untell_text
from untell.scripts.voice import _WORD, MIN_SAMPLE_WORDS

DRAFT = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale and "
    "significantly improves overall efficiency and accuracy across the evaluated corpus."
)


def _warn(sample: str) -> str | None:
    result = untell_text(
        DRAFT, tier="lite", max_iters=1, rewriter="composite", threshold=0.0, voice_sample=sample
    )
    return result.get("voice_warning")


def test_the_two_floors_are_ordered() -> None:
    """The premise. If they ever coincide the branch below is untestable, not merely unused."""
    assert _MIN_VOICE_SAMPLE_WORDS < MIN_SAMPLE_WORDS


@pytest.mark.parametrize("n", [1, 5, 19])
def test_below_the_disable_floor_the_warning_says_disabled(n: int) -> None:
    sample = "word " * n
    assert len(_WORD.findall(sample)) < _MIN_VOICE_SAMPLE_WORDS
    warning = _warn(sample)
    assert warning and "DISABLED" in warning, warning
    assert "no effect on the output" in warning
    # The claim that used to be made here, and was false: nothing ran, so nothing was arbitrary.
    assert "arbitrary" not in warning


@pytest.mark.parametrize("n", [20, 75, 149])
def test_between_the_floors_the_warning_says_weak(n: int) -> None:
    sample = "word " * n
    assert _MIN_VOICE_SAMPLE_WORDS <= len(_WORD.findall(sample)) < MIN_SAMPLE_WORDS
    warning = _warn(sample)
    assert warning and "arbitrary" in warning, warning
    assert "DISABLED" not in warning, "the tie-break does run in this band"


def test_a_full_sample_warns_about_nothing() -> None:
    """Guards both branches above: a warning on every sample would satisfy them and mean nothing."""
    sample = "I write in short sentences. " * 50
    assert len(_WORD.findall(sample)) >= MIN_SAMPLE_WORDS
    assert _warn(sample) is None


def test_the_message_matches_what_the_tie_break_actually_did() -> None:
    """The warnings are claims about behaviour, so check the behaviour rather than the wording.

    Below the disable floor every candidate must key identically — that is what "no effect on the
    output" means. Above it they must not, or the second branch is describing a tie-break that is
    equally absent.
    """
    candidates = ["It works.", "The present analysis demonstrates substantive improvements.",
                  "I think this one is fine, honestly, though I'd tweak the ending."]
    thin = "word " * 5
    ok = "I write in short sentences. " * 15

    thin_keys = [_voice_key(c, thin) for c in candidates]
    assert len(set(thin_keys)) == 1, f"disabled tie-break still discriminated: {thin_keys}"

    live_keys = [_voice_key(c, ok) for c in candidates]
    assert len(set(live_keys)) == len(candidates), f"tie-break did not run: {live_keys}"
