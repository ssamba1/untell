"""The opener transform must not add a marker to a sentence that already has one.

`_insert_openers` guards against exactly this, and the guard was correct in intent — it just
consulted `_LEADING_MARKER_RE`, a list of coordinating markers that does not contain the
transform's own vocabulary. MEASURED: 8 of the 9 openers this rewriter inserts were invisible to
its own guard, so a sentence already given "Basically," could be given a second one.

The pool and the guard are now derived from one tuple, so an opener added later cannot be missing
from the check.
"""

from __future__ import annotations

import random
import re

import pytest

from untell.rewriter.structural import (
    _ANY_LEADING_MARKER_RE,
    _LEADING_MARKER_RE,
    _OPENERS,
    StructuralRewriter,
)
from untell.scripts.tells import score_tells

_STACKED = re.compile(
    r"(?:^|[.!?]\s+)(?:"
    + "|".join(re.escape(o.rstrip(",")) for o in _OPENERS)
    + r"|so|well|also),\s*(?:"
    + "|".join(re.escape(o.rstrip(",")) for o in _OPENERS)
    + r"),",
    re.IGNORECASE,
)


@pytest.mark.parametrize("opener", _OPENERS)
def test_the_guard_recognises_every_opener_the_pool_can_insert(opener: str) -> None:
    assert _ANY_LEADING_MARKER_RE.match(f"{opener} the result was clear.")


def test_the_old_guard_is_why_this_file_exists() -> None:
    """Pins the gap, so replacing the new guard with the old one fails here rather than silently."""
    missed = [o for o in _OPENERS if not _LEADING_MARKER_RE.match(f"{o} x y")]
    assert len(missed) >= 8, (
        "the coordinating-marker list now covers the opener pool; if that is deliberate, this "
        f"test should go — currently missed: {missed}"
    )


def test_the_guard_still_catches_coordinating_markers() -> None:
    """Deriving from `_OPENERS` must not drop what the original list covered."""
    for lead in ("However,", "Moreover,", "and", "But", "Therefore,", "Still,"):
        assert _ANY_LEADING_MARKER_RE.match(f"{lead} the result was clear.")


def test_a_plain_sentence_is_not_treated_as_marked() -> None:
    for plain in ("The result was clear.", "Airplanes are complex.", "Nobody expected it."):
        assert not _ANY_LEADING_MARKER_RE.match(plain)


@pytest.mark.parametrize("seed", range(25))
def test_no_stacked_openers_in_real_output(seed: int) -> None:
    text = (
        "Basically, the reason that airplane technology moves slowly is regulation. "
        "In short, the certification process is long. Airplanes are complex machines. "
        "The cost of a new airframe is enormous and the market is small."
    )
    random.seed(seed)
    out = StructuralRewriter().rewrite(text, score_tells(text))
    assert not _STACKED.search(out), f"stacked openers: {out}"
