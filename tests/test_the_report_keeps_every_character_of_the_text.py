"""Three ways the HTML report could be wrong today with every test green.

From round ninety-four's survivor list, in `untell/html_report.py`:

    line  88  if start < prev:        ->  >=      the overlapping-span guard
    line  99  if prev < len(text):    ->  >=      the trailing-text emit
    line 144  fill = round(100.0 - pct, 1)  ->  +  the score bar width

The middle one is a user-visible bug nobody tested: with `>=`, **every character after the last
locked span is silently dropped from the report.** A document whose final sentence is unlocked would
render without its ending, and the report is the artefact a person actually reads when deciding
whether an accusation is fair.

The first is the guard against overlapping spans. The third makes the score bar's overlay wider than
the bar itself for any non-zero score, which no assertion noticed because nothing checked the number
rather than the presence of the markup.

The property these tests are really pinning is conservation: **the report must contain every
character of the input**, whatever the spans do. That is stronger than any single mutant and it is
what a reader is entitled to assume.
"""

from __future__ import annotations

import html
import re

import pytest

from untell.html_report import _annotate_locked, _score_bar

TEXT = "Alpha beta gamma. Delta epsilon zeta. Eta theta iota."


def _visible(markup: str) -> str:
    """The text a reader sees, with tags stripped and entities resolved."""
    return html.unescape(re.sub(r"<[^>]+>", "", markup))


def test_text_after_the_last_locked_span_is_not_dropped():
    """Kills `prev < len(text)` -> `>=` at line 99. The tail is most of a document."""
    spans = [{"start": 0, "end": 5, "rules": ["citation"]}]
    rendered = _annotate_locked(TEXT, spans)
    assert "gamma" in _visible(rendered)
    assert _visible(rendered).endswith("theta iota.")


def test_every_character_survives_the_annotation():
    """The conservation property, over span layouts that exercise both ends and the middle."""
    layouts = [
        [],
        [{"start": 0, "end": 5, "rules": []}],
        [{"start": 18, "end": 23, "rules": ["a"]}],
        [{"start": 0, "end": len(TEXT), "rules": ["whole"]}],
        [{"start": 0, "end": 5, "rules": []}, {"start": 18, "end": 23, "rules": []}],
        [{"start": len(TEXT) - 5, "end": len(TEXT), "rules": []}],
    ]
    for spans in layouts:
        assert _visible(_annotate_locked(TEXT, spans)) == TEXT, spans


def test_a_span_reaching_the_very_end_emits_no_stray_tail():
    """The boundary the mutant sits on: prev == len(text) must emit nothing, not something."""
    spans = [{"start": 0, "end": len(TEXT), "rules": ["whole"]}]
    assert _visible(_annotate_locked(TEXT, spans)) == TEXT


def test_an_overlapping_span_is_skipped_rather_than_duplicating_text():
    """Kills `start < prev` -> `>=` at line 88.

    With `>=` the guard fires on every ADJACENT span too, so a document with two touching locked
    regions loses the second one. Both cases are asserted: overlapping is skipped, adjacent is kept.
    """
    overlapping = [{"start": 0, "end": 10, "rules": ["a"]}, {"start": 5, "end": 15, "rules": ["b"]}]
    assert _visible(_annotate_locked(TEXT, overlapping)) == TEXT[:10] + TEXT[10:]

    adjacent = [{"start": 0, "end": 5, "rules": ["a"]}, {"start": 5, "end": 10, "rules": ["b"]}]
    rendered = _annotate_locked(TEXT, adjacent)
    assert rendered.count("<mark") == 2, "an adjacent span is not an overlapping one"
    assert _visible(rendered) == TEXT


@pytest.mark.parametrize("score", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_the_score_bar_overlay_never_exceeds_the_bar(score: float):
    """Kills `100.0 - pct` -> `+` at line 144, which makes the overlay wider than the bar."""
    markup = _score_bar(score)
    widths = [float(w) for w in re.findall(r"width:([\d.]+)%", markup)]
    lefts = [float(w) for w in re.findall(r"left:([\d.]+)%", markup)]
    assert widths and lefts
    for width, left in zip(widths, lefts):
        assert 0.0 <= width <= 100.0, markup
        assert width + left == pytest.approx(100.0, abs=0.15), (
            "the overlay must start at the score and cover exactly the remainder"
        )


def test_the_score_bar_is_clamped_rather_than_trusting_its_caller():
    for score in (-1.0, 2.0):
        widths = [float(w) for w in re.findall(r"width:([\d.]+)%", _score_bar(score))]
        assert all(0.0 <= w <= 100.0 for w in widths), score
