"""A document longer than the scoring cap must come back whole.

`score.py` truncates at `_MAX_INPUT_CHARS` (50,000) so detectors do not OOM. That is a bound on
what gets SCORED. If it leaked into the rewrite path, a long document would return shorter than it
went in and the user would lose the tail with nothing said — the quietest possible data loss, since
the result still looks like a successful run.

It does not leak. MEASURED on real HC3 documents with the cap lowered to half the document length,
so every one is truncated for scoring:

    doc   cap    in     out    rewritten   tail survived
    0     574   1149   1149    no          yes
    1     591   1183   1183    no          yes
    2     412    824    813    yes         yes

doc2 is the one that matters: the loop rewrote it (6 draws, `changed=True`) and the marker at the
very end still came back, with the 1.3% length change coming from the rewrite rather than from a
cut.

The cap is lowered rather than the document lengthened, deliberately: rewriting 50,000 characters
takes longer than any reasonable test, and the cap's VALUE is not what is in question — whether
truncation reaches the returned text is.

The only existing coverage of this constant is the REST layer rejecting oversized bodies, which is
a different guarantee: that one is about refusing input, this one is about not silently keeping
half of it.
"""
from __future__ import annotations

import pytest

import untell.scripts.score as score_module
from untell.scripts.run import untell_text

TAIL = "ZZTAILMARKERZZ ends this document."


@pytest.fixture(autouse=True)
def _stdlib(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


@pytest.fixture
def small_cap(monkeypatch):
    """Lower the cap instead of growing the document — same mechanism, affordable runtime."""

    def _apply(value: int) -> None:
        monkeypatch.setattr(score_module, "_MAX_INPUT_CHARS", value)

    return _apply


LONG = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "It significantly improves overall efficiency and accuracy across the evaluated corpus. "
    "Furthermore, organizations increasingly adopt these transformative technologies to "
    "optimize operational workflows across numerous sectors and regions. In conclusion, these "
    "findings underscore the importance of a comprehensive approach to adoption. "
) + TAIL


def test_the_fixture_exceeds_the_cap(small_cap):
    """The premise. Below the cap nothing is truncated and the test proves nothing."""
    small_cap(200)
    assert len(LONG) > score_module._MAX_INPUT_CHARS


def test_the_tail_survives_a_run(small_cap):
    small_cap(200)
    result = untell_text(LONG, tier="lite", threshold=0.0, max_iters=2,
                         rewriter="composite", seed=5)

    assert TAIL.split()[0] in result["final"], (
        "text past the scoring cap was dropped from the returned document — the cap bounds what "
        f"is scored, not what is returned:\n{result['final'][-200:]}"
    )


def test_the_output_is_not_cut_to_the_cap(small_cap):
    """Length is the blunt check: a truncated result would be about the cap size."""
    small_cap(200)
    result = untell_text(LONG, tier="lite", threshold=0.0, max_iters=2,
                         rewriter="composite", seed=5)

    # Against the INPUT, not against a multiple of the cap. A rewrite legitimately shortens the
    # text — measured 1.3% on corpus documents — so "much bigger than the cap" was the wrong way to
    # say "not cut to the cap", and it failed on a fixture only twice the cap to begin with.
    kept = len(result["final"]) / len(LONG)
    assert kept > 0.8, (
        f"output kept {kept:.1%} of the input against a cap at "
        f"{score_module._MAX_INPUT_CHARS / len(LONG):.1%} of it — that is a truncation, not a rewrite"
    )


def test_the_scorer_still_truncates(small_cap):
    """The cap must keep doing its own job, or this file is guarding a bound that stopped existing."""
    small_cap(200)
    assert len(score_module._truncate(LONG)) == 200


def test_a_rewritten_document_keeps_its_tail(small_cap):
    """The case that matters: survival through a run that actually changed the text.

    A document the loop declines to rewrite comes back byte-identical, so its tail survives
    trivially — which is how the first version of this probe reported success on three runs that
    had rewritten nothing.
    """
    small_cap(200)
    changed = None
    for seed in range(6):
        result = untell_text(LONG, tier="lite", threshold=0.0, max_iters=2,
                             rewriter="composite", seed=seed)
        if result.get("changed"):
            changed = result
            break

    if changed is None:
        pytest.skip("the loop declined to rewrite this fixture at every seed")

    assert TAIL.split()[0] in changed["final"], changed["final"][-200:]
