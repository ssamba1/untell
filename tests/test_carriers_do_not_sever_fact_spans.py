"""Invisible carriers between the COMPONENTS of a fact must not sever the fact.

preserve-lock's whole promise is that a fact survives a rewrite byte-for-byte. An
invisible carrier (bidi control, zero-width char) sitting between the components of
a fact is invisible to the number patterns' `\\s` connectors, so it severs the span:

    lock("The dose is 5\u200fmg ...")      ->  "5mg" locks NOTHING (unit fully rewritable)
    lock("...at 9:30\u200fAM tomorrow")    ->  locks "9:30" only, "AM" free (12-hour shift)
    lock("...rose to 42\u200b% ...")       ->  locks "42" only, "%" free
    lock("...and p\u200e<0.05 held")       ->  locks "<0.05" only, "p" free

The first two are the exact "worst possible outcome" this file documents: a sentinel
appears, so the span LOOKS protected, while the decision-bearing part (the unit, the
meridiem) stays mutable. The bidi controls survive scrub_hidden in RTL text — they
are load-bearing there — so this is reachable in the main pipeline for an
Arabic/Hebrew document containing a Latin fact: MEASURED, "الجرعة 5\u200fملغ والوقت
9:30\u200fمساءً" masked to "5ملغ" unmasked + "9:30" locked + "مساءً" free.

The carriers named here are the ones scrub_hidden removes as payload (RLM, LRM,
RLI, PDI, LRI, ALM, RLE, PDF, ZWSP, ZWNJ, ZWJ, WJ, BOM, invisible math operators,
variation selectors). Inside a fact none of them is load-bearing — a ZWJ between
"9:30" and "AM" is not joining emoji.
"""

from __future__ import annotations

import pytest

from untell.scripts.preserve import lock

CARRIERS = [
    ("RLM", "\u200f"),
    ("LRM", "\u200e"),
    ("RLI", "\u2067"),
    ("PDI", "\u2069"),
    ("LRI", "\u2066"),
    ("ALM", "\u061c"),
    ("ZWSP", "\u200b"),
    ("ZWNJ", "\u200c"),
    ("RLE", "\u202b"),
    ("PDF", "\u202c"),
    ("WJ", "\u2060"),
    ("BOM", "\ufeff"),
]


@pytest.mark.parametrize("name,carrier", CARRIERS, ids=[c[0] for c in CARRIERS])
def test_a_carrier_between_number_and_unit_does_not_sever_the_fact(name, carrier):
    masked, mapping = lock(f"The dose is 5{carrier}mg and the trial continued.")
    locked = "".join(mapping.values())
    assert "5" + carrier + "mg" in locked, (
        f"{name}: locked {mapping!r}, expected the whole '5{carrier}mg' fact"
    )


@pytest.mark.parametrize("name,carrier", CARRIERS, ids=[c[0] for c in CARRIERS])
def test_a_carrier_between_time_and_meridiem_does_not_sever_the_fact(name, carrier):
    masked, mapping = lock(f"The meeting is at 9:30{carrier}AM tomorrow.")
    locked = "".join(mapping.values())
    assert "9:30" + carrier + "AM" in locked, (
        f"{name}: locked {mapping!r}, expected '9:30{carrier}AM' whole"
    )


def test_a_carrier_between_number_and_percent_is_not_a_boundary():
    masked, mapping = lock("The rate rose to 42\u200b% of the total.")
    assert "42\u200b%" in "".join(mapping.values()), mapping


def test_a_carrier_between_p_and_comparison_is_not_a_boundary():
    masked, mapping = lock("The result was p\u200e<0.05, which is significant.")
    assert "p\u200e<0.05" in "".join(mapping.values()), mapping


def test_a_carrier_inside_a_range_does_not_sever_it():
    masked, mapping = lock("Temperatures of 5\u200f-10\u200f°C were recorded.")
    assert "5\u200f-10\u200f°C" in "".join(mapping.values()), mapping


def test_a_carrier_between_number_and_currency_sign_is_not_a_boundary():
    # The carrier sits BETWEEN the sign and the digits — "$50" must lock whole.
    masked, mapping = lock("The total was $\u200b50 and change.")
    assert "$\u200b50" in "".join(mapping.values()), mapping


def test_no_carrier_means_no_behaviour_change():
    """The control: the same sentences WITHOUT carriers lock exactly as before."""
    masked, mapping = lock("The dose is 5mg and the meeting is at 9:30AM tomorrow.")
    locked = "".join(mapping.values())
    assert "5mg" in locked and "9:30AM" in locked, mapping
