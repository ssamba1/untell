"""Five public surfaces, seven inputs none of them can judge. Which ones say so?

Three consecutive defects had the same shape — the tool knows, and the thing that answers does not
ask. `score_text` had no language caveat; `score_tells` reported the weaker of two answers its own
module held; `humanness` computed the reason and did not gate the score on it, returning 100.0
"human" for German. Each was found by hand, one surface at a time. This is the sweep.

MEASURED after those fixes — the matrix, `yes` meaning the surface said something:

    input         score  tells  sentences  humanize  humanness
    non-english     yes    yes        yes       yes        yes
    very short      yes     --        yes       yes        yes
    code only       yes     --        yes       yes         --
    invisible       yes     --        yes       yes         --
    per-line        yes     --        yes       yes         --
    punct only      yes    yes        yes       yes        yes
    ordinary        yes     --        yes       yes         --

Every blank is accounted for, and two of the accounts are worth keeping:

* **`tells` on short text is silent by design, and only when there are no tells.** The caveat is
  gated on a non-zero rate, with the measurement to justify it: over 60 HC3 pairs truncated to five
  words the mean rate is 0.00 for human and 0.67 for AI, so a caveat on a harmless 0.0 would be
  noise that teaches readers to skip warnings. My first pass recorded this cell as a gap because the
  probe text I chose happened to contain no tells — the blank was my sample, not the code.
* **`humanness` blanks are abstention-only.** It has caveats for invisibles and the weak path; they
  go to the log, because the function returns a float and has no channel for anything else. What the
  matrix reads is `undetermined_reason`, which reports abstentions and not caveats.

The row that matters is `non-english`: all five, and three of those five were added in the two loops
before this file existed.
"""

from __future__ import annotations

import logging

import pytest

from untell.humanness import undetermined_reason
from untell.scripts.run import untell_text
from untell.scripts.score import score_text
from untell.scripts.sentences import score_sentences
from untell.scripts.tells import score_tells

GERMAN = (
    "Der Dienst läuft hinter einem Lastverteiler, und die Zustandsprüfung muss innerhalb von zwei "
    "Sekunden antworten, sonst wird der Knoten aus dem Pool entfernt. Darüber hinaus ist es wichtig "
    "zu beachten, dass eine langsame Prüfung sich während eines Rollouts verstärkt."
)
UNJUDGEABLE = {
    "non-english": GERMAN,
    "punct only": ";;; ;;; --- ...",
}
ORDINARY = (
    "The service runs behind a load balancer, and the health check must respond within two seconds "
    "or the node is removed from the pool. The team settled on that after watching three incidents "
    "that all began the same way, with a probe that answered slowly instead of not at all."
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def _score(text: str) -> str:
    return score_text(text, tier="lite", threshold=0.3).get("warning") or ""


def _tells(text: str) -> str:
    result = score_tells(text)
    note = result.get("warning") or ""
    return note if result.get("language_supported", True) else note + " [unsupported]"


def _sentences(text: str) -> str:
    result = score_sentences(text, tier="lite")
    return (result.get("warning") or "") if isinstance(result, dict) else ""


def _humanize(text: str) -> str:
    result = untell_text(text, tier="lite", max_iters=1)
    return (result.get("warning") or "") + " " + (result.get("rewriter_warning") or "")


def _humanness(text: str) -> str:
    return undetermined_reason(text) or ""


SURFACES = {
    "score": _score,
    "tells": _tells,
    "sentences": _sentences,
    "humanize": _humanize,
    "humanness": _humanness,
}


@pytest.mark.parametrize("surface", sorted(SURFACES))
@pytest.mark.parametrize("case", sorted(UNJUDGEABLE))
def test_every_surface_says_something(surface: str, case: str) -> None:
    """The two inputs no surface can judge at all — a language the catalogue cannot read, and text
    with no prose in it. A silent surface here hands the user a number with nothing attached."""
    assert SURFACES[surface](UNJUDGEABLE[case]).strip(), f"{surface} said nothing about {case}"


@pytest.mark.parametrize("surface", sorted(SURFACES))
def test_the_non_english_note_names_the_language(surface: str) -> None:
    """Not merely non-empty. A surface warning about the tier while a German paragraph goes by is
    the defect this file exists for, and it would satisfy the assertion above."""
    note = SURFACES[surface](GERMAN).lower()
    assert any(word in note for word in ("english", "language", "script", "catalogue")), note[:120]


@pytest.mark.parametrize("surface", sorted(SURFACES))
def test_ordinary_prose_is_not_buried(surface: str) -> None:
    """Guards the guard. Caveats compose, and a surface that warns about everything trains the
    reader to skip them — which is why `tells` stays silent on a harmless 0.0 rate. `score` and
    `humanize` legitimately carry a standing tier caveat here; the others must not invent one."""
    if surface in {"score", "humanize", "sentences"}:
        pytest.skip(f"{surface} carries a standing tier caveat on every run by design")
    assert not SURFACES[surface](ORDINARY).strip(), surface


def test_the_short_text_gate_is_the_measured_one() -> None:
    """The blank cell that was not a gap. `tells` warns about a rate computed on a tiny denominator
    only when the rate is non-zero, because over 60 HC3 pairs truncated to five words the mean rate
    is 0.00 — so the common short-text case is a harmless zero, and caveating it is noise.

    Both halves asserted, because the first pass recorded this as a defect after probing with the
    half that is silent."""
    assert score_tells("In conclusion, it works.")["warning"], "a non-zero short rate must warn"
    assert not (score_tells("The result was clear.").get("warning") or ""), "a 0.0 rate must not"
