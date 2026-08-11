"""`targeted` compared candidates on `max` alone, and threw away 15 of 19 real improvements.

This is the defect `composite._selection_key` was written for, still live one module over. `max` is a
single detector's number and `roberta_openai` returns 0.9992 on nearly every sentence of HC3's
genre, so `after < before` is false on text that genuinely improved. MEASURED over 8 HC3 AI answers,
per sentence:

    max improved (adopted)        4
    max worse (rejected)          0
    max TIED, mean improved      15   <- every one discarded
    max TIED, mean not improved   0

Not one tie was neutral or worse. End to end on the same 8 documents, seeded identically:

    BEFORE (max only)    3/8 texts changed
    AFTER  (max, mean)   7/8 texts changed, every one lowering the ensemble mean
                         similarity min 0.966, meaning gates 7/7

The selector moved to `untell/rewriter/base.py` rather than being copied, because two selectors
ordering the same candidates differently is the failure this repo keeps re-finding.

The adopted deltas are not uniformly larger — one document improved by 0.0314 under `max` alone and
by less afterwards, since adopting a different sentence changes what the rest of the pass sees. The
claim is more documents improved, not every document improved more.
"""

from __future__ import annotations

import logging

import pytest

import untell.rewriter.targeted as targeted_module
import untell.scripts.score as score_module
from untell.rewriter.base import selection_key
from untell.rewriter.targeted import TargetedRewriter

SATURATED = 0.9992

BODY = (
    "The system reads the file before anything else happens. "
    "The parser splits it into records and hands each one onward."
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


class _Inner:
    """Stands in for the real inner rewriter: returns a fixed, different sentence."""

    def rewrite(self, text: str, score_result: dict, threshold: float) -> str:
        return text.replace("The ", "A ").replace("the ", "a ")


def _scorer(mean_for_rewritten: float):
    """`max` pinned at saturation for every input; only `mean` distinguishes them."""

    def score(text: str, tier: str = "full") -> dict:
        rewritten = text.startswith("A ") or " a " in text
        return {
            "max": SATURATED,
            "mean": mean_for_rewritten if rewritten else 0.8000,
            "detectors": {"roberta_openai": SATURATED},
        }

    return score


def test_a_tie_on_max_with_a_better_mean_is_adopted(monkeypatch) -> None:
    """The 15 discards, as one deterministic case."""
    monkeypatch.setattr(score_module, "score_text", _scorer(0.6000))
    rw = TargetedRewriter()
    rw._inner = _Inner()
    out = rw.rewrite(BODY, {"max": SATURATED}, 0.30)
    assert out != BODY
    assert "A system" in out


def test_a_tie_on_both_is_not_adopted(monkeypatch) -> None:
    """Guards the guard, and it is the line between this and the reverted "consolation rewrite":
    changing the text is not itself worth anything. A candidate that ties on max AND on mean loses
    to the original."""
    monkeypatch.setattr(score_module, "score_text", _scorer(0.8000))
    rw = TargetedRewriter()
    rw._inner = _Inner()
    assert rw.rewrite(BODY, {"max": SATURATED}, 0.30) == BODY


def test_a_worse_mean_is_not_adopted(monkeypatch) -> None:
    monkeypatch.setattr(score_module, "score_text", _scorer(0.9000))
    rw = TargetedRewriter()
    rw._inner = _Inner()
    assert rw.rewrite(BODY, {"max": SATURATED}, 0.30) == BODY


def test_the_minimum_score_gate_still_reads_the_max(monkeypatch) -> None:
    """`min_score` is about how AI a sentence reads, which is the max's job, so it reads element 0
    of the tuple. With every sentence below the bar nothing is targetable, and the documented
    behaviour is a whole-text fallback rather than a silent no-op — that must survive too.

    My first version of this asserted the input came back unchanged, which is the behaviour this
    module deliberately stopped having."""
    monkeypatch.setattr(
        score_module,
        "score_text",
        lambda text, tier="full": {
            "max": 0.01,
            "mean": 0.01,
            "detectors": {"roberta_openai": 0.01},
        },
    )
    rw = TargetedRewriter()
    rw._inner = _Inner()
    assert rw.rewrite(BODY, {"max": 0.01}, 0.30) == _Inner().rewrite(BODY, {}, 0.30)


def test_both_rewriters_read_the_same_selector() -> None:
    """The reason the function moved to `base` instead of being copied."""
    from untell.rewriter.composite import _selection_key

    assert _selection_key is selection_key
    assert targeted_module.selection_key is selection_key
