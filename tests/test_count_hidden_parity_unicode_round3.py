"""count_hidden and scrub_hidden agree on the unicode-round-3 classes.

The invariant that matters: ``count_hidden`` says a character is hidden EXACTLY
when ``scrub_hidden`` changes it. The emoji tag sequences (England/Scotland/Wales
flags) became legitimate content in the same round the bidi controls became
splittable carriers, so both sides of the pair need pinning on the new classes:

    England flag 🏴󠁧󠁢󠁥󠁮󠁧󠁿   count 0, scrub unchanged  (it is a real flag)
    keycap 1️⃣              count 0, scrub unchanged  (it is a real emoji)
    US flag 🇺🇸             count 0, scrub unchanged  (regional indicators)
    lone tag char           count 1, scrub removes    (still a carrier)
    bidi control in Latin   count 1, scrub removes    (still a carrier)
    RLM beside Arabic       count 0, scrub unchanged  (load-bearing layout)
"""

from __future__ import annotations

import pytest

from untell.attacks.unicode_tricks import count_hidden, scrub_hidden

ENGLAND = "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F"
KEYCAP = "1\uFE0F\u20E3"
US_FLAG = "\U0001F1FA\U0001F1F8"

LEGITIMATE = [
    ("england flag", f"Team {ENGLAND} won"),
    ("keycap", f"Press {KEYCAP} to continue"),
    ("us flag", f"Go {US_FLAG} go"),
    ("arabic with RLM", "\u0645\u0631\u062D\u0628\u0627 \u200F\u0639\u0627\u0644\u0645"),
    ("accented latin", "Café naïvely résumé"),
]

CARRIERS = [
    ("lone tag char", "\U000E0061"),
    ("RLM in latin", "\u200F"),
    ("RLI in latin", "\u2067"),
    ("ALM in latin", "\u061C"),
    ("ZWSP", "\u200B"),
]


@pytest.mark.parametrize("name,text", LEGITIMATE, ids=[t[0] for t in LEGITIMATE])
def test_legitimate_classes_report_zero_and_survive(name, text):
    assert count_hidden(text) == 0, f"{name}: count_hidden={count_hidden(text)}"
    assert scrub_hidden(text) == text, f"{name}: scrub changed it"


@pytest.mark.parametrize("name,carrier", CARRIERS, ids=[t[0] for t in CARRIERS])
def test_carrier_classes_count_one_and_are_removed(name, carrier):
    text = f"The build{carrier} succeeded on the first try."
    assert count_hidden(text) == 1, f"{name}: count_hidden={count_hidden(text)}"
    assert carrier not in scrub_hidden(text), f"{name}: survived the scrub"


@pytest.mark.parametrize("name,text", LEGITIMATE + CARRIERS, ids=[t[0] for t in LEGITIMATE + CARRIERS])
def test_count_is_zero_exactly_when_scrub_is_a_no_op(name, text):
    if len(text) == 1:  # bare carrier probe
        text = f"The build{text} succeeded on the first try."
    assert (count_hidden(text) == 0) == (scrub_hidden(text) == text), name
