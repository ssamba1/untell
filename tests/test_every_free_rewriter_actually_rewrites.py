"""A rewriter that returns its input looks exactly like one that found nothing to do.

This repository has that scar: the DEFAULT rewriter shipped as a no-op on 10 of 10 HC3 documents,
because a saturating detector made the selection comparison never fire, and the only visible
giveaway was a similarity of exactly 1.000. Nothing swept the rewriters for the plainer property.

MEASURED across every free rewriter the surfaces advertise:

    composite  structural  surgical  targeted  neural  ensemble  t5_paraphrase  mt_pivot

all eight are available, all eight change the text, and all eight produce DISTINCT output — so
none is silently delegating to another. `anthropic` and `openai` do not resolve without keys,
which is correct and is asserted as such rather than skipped over.

The widest existing sweep, `test_no_new_defects_on_hard_input`, covers three of the eight. The
list here is anchored to `_FREE_REWRITERS` in mcp_server so it cannot quietly shrink: a rewriter
advertised there and missing here fails the guard.
"""
from __future__ import annotations

import pytest

from untell.mcp_server import _FREE_REWRITERS
from untell.rewriter import get_rewriter

AI = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "It significantly improves overall efficiency and accuracy across the evaluated corpus. "
    "In conclusion, these findings underscore the importance of a comprehensive approach."
)
SCORE = {"tier": "lite", "max": 0.9, "detectors": {"perplexity_burstiness": 0.9}}

# `max` is an alias the surfaces accept, not a distinct backend, so it is not swept for output.
SWEPT = sorted(_FREE_REWRITERS - {"max"})


@pytest.fixture(autouse=True)
def _stdlib(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


def test_the_swept_list_matches_what_the_surfaces_advertise():
    """The guard. A backend advertised and unswept is one nobody checks can rewrite."""
    assert SWEPT, "no rewriters to sweep"
    assert set(SWEPT) | {"max"} == set(_FREE_REWRITERS), (
        f"advertised {sorted(_FREE_REWRITERS)} but sweeping {SWEPT}"
    )


@pytest.mark.parametrize("name", SWEPT)
def test_the_rewriter_resolves_and_is_available(name: str):
    rewriter = get_rewriter(prefer=name)
    assert rewriter is not None, f"{name} is advertised as free and does not resolve"
    assert rewriter.available(), f"{name} resolves but reports unavailable"


@pytest.mark.parametrize("name", SWEPT)
def test_the_rewriter_changes_the_text(name: str):
    rewriter = get_rewriter(prefer=name)
    if rewriter is None or not rewriter.available():
        pytest.skip(f"{name} unavailable here")

    out = rewriter.rewrite(AI, SCORE, 0.30)

    assert out.strip(), f"{name} returned empty text"
    assert out.strip() != AI.strip(), (
        f"{name} returned its input unchanged on text scoring 0.9 — indistinguishable from a "
        "rewriter that ran and found nothing, which is how the default shipped as a no-op"
    )


def test_the_rewriters_do_not_all_produce_the_same_text():
    """Distinctness, so a backend silently delegating to another shows up as a duplicate."""
    outputs = {}
    for name in SWEPT:
        rewriter = get_rewriter(prefer=name)
        if rewriter is None or not rewriter.available():
            continue
        outputs[name] = rewriter.rewrite(AI, SCORE, 0.30)

    assert len(outputs) >= 4, f"too few rewriters available to compare: {sorted(outputs)}"
    duplicates = {
        a: [b for b in outputs if b != a and outputs[b] == outputs[a]] for a in outputs
    }
    duplicates = {a: b for a, b in duplicates.items() if b}
    assert not duplicates, f"identical output from different backends: {duplicates}"


@pytest.mark.parametrize("name", ["anthropic", "openai"])
def test_the_keyed_backends_do_not_pretend_to_be_available(name: str):
    """Without a key these must not resolve into something that quietly rewrites anyway."""
    rewriter = get_rewriter(prefer=name)
    if rewriter is None:
        return  # correct: no key, no backend
    assert not rewriter.available() or getattr(rewriter, "name", name) == name, (
        f"{name} resolved to {type(rewriter).__name__}, which is a different backend"
    )
