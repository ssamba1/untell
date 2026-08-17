"""`references/thresholds.md` documents the loop's constants and nothing checked them.

The file ships with the skill and is the reference a user reads to understand what the numbers mean.
It is not in `audit.LIVE_DOCS`, so neither the claim check nor the attribution check touches it —
the five constants below are correct today by nobody's arrangement.

Deliberately not solved by adding the file to `LIVE_DOCS`. That list subjects every numeric claim in
a document to the attribution rule, and this one quotes 46 numbers, most of them measurements from
tables rather than constants. Pinning the five that are CONSTANTS is the part that can drift
silently: a value changed in code and left stale in the doc reads as authoritative and is wrong.
"""

from __future__ import annotations

import inspect
import pathlib
import re

import pytest

from untell.scripts.entailment import (
    DEFAULT_CONTRADICTION_BAR,
    DEFAULT_ENTAILMENT_FLOOR,
    RELAXED_SIM_BAR,
)
from untell.scripts.quality import method, recommended_bar
from untell.scripts.run import untell_text
@pytest.fixture(autouse=True)
def _embedding_path(monkeypatch):
    """These assertions pin EMBEDDING-based measurements (similarity bars, the
    documented method). Under UNTELL_LITE_NO_TORCH=1 quality.similarity falls back
    to token_overlap, which is harsher (a one-closer deletion scores 0.91 vs 0.98)
    and the bars were measured on embeddings. Pin the env unset for the file.
    """
    monkeypatch.delenv("UNTELL_LITE_NO_TORCH", raising=False)

DOC = pathlib.Path("untell/references/thresholds.md").read_text(encoding="utf-8")


def _quotes_near(value: str, anchor: str) -> bool:
    """Is `value` present on a line that also mentions `anchor`?

    "Somewhere in the document" is far too loose and was the first version of this. The file quotes
    46 numbers, so a constant moving to a coincidental value passes: checked, `0.35` and `0.007` both
    appear elsewhere in the doc, and a threshold that drifted to either would have been reported as
    documented. The number has to be in the row that names the thing.
    """
    pattern = re.compile(rf"(?<![\d.]){re.escape(value)}(?![\d])")
    return any(pattern.search(line) for line in DOC.splitlines() if anchor.lower() in line.lower())


@pytest.mark.parametrize(
    ("name", "value", "anchor"),
    [
        (
            "loop threshold",
            f"{inspect.signature(untell_text).parameters['threshold'].default:.2f}",
            "`threshold`",
        ),
        ("embedding similarity bar", f"{recommended_bar():.2f}", "similarity bar"),
        ("NLI contradiction bar", f"{DEFAULT_CONTRADICTION_BAR:.2f}", "meaning gate"),
        ("NLI entailment floor", f"{DEFAULT_ENTAILMENT_FLOOR:.3f}", "meaning gate"),
        ("relaxed similarity bar", f"{RELAXED_SIM_BAR:.2f}", "relaxed sim bar"),
    ],
    ids=lambda x: str(x)[:24],
)
def test_the_doc_quotes_the_value_the_code_uses(name: str, value: str, anchor: str) -> None:
    assert _quotes_near(value, anchor), (
        f"{name} is {value} in code, and no line of thresholds.md mentioning {anchor!r} contains "
        "that number — the doc is stale, or the constant moved without it"
    )


def test_the_doc_names_the_similarity_method_it_quotes() -> None:
    """The bar only means something alongside the method that produces it — 0.76 is the embedding
    bar, and the doc quotes 0.88 for BERTScore and 0.50 for token overlap in the same cell. A test
    on the number alone would pass if the default method changed underneath it."""
    assert method() in DOC, f"quality.method() is {method()!r} and the doc does not mention it"
    assert "0.76" in DOC and "0.88" in DOC and "0.50" in DOC


def test_the_check_can_fail() -> None:
    """Guards the guard, and this one earned its place.

    The first version asked only whether a value appeared ANYWHERE in the document, and its own
    non-vacuity probe exposed it: of three invented "moved constants", two — `0.35` and `0.007` —
    already appear elsewhere in the file, so a threshold drifting to either would have been reported
    as documented. Anchoring to the row that names the constant is what makes the check real.
    """
    assert not _quotes_near("0.4321", "`threshold`"), "a number not on that row was reported present"
    assert _quotes_near("0.30", "`threshold`"), "the value on that row was reported absent"
    # The specific weakness that was found: `0.007` is in the file and would have satisfied a
    # whole-document check. It must not satisfy the anchored one.
    #
    # The anchor for both NLI bars is "meaning gate", not "entailment": the word `entailment` also
    # appears in the QUANTITY-CHECK row's prose ("entailment `0.007` — clearing the floor by
    # `0.002`"), so anchoring on it matched a second row and let exactly the coincidence back in.
    # An anchor has to name the ROW, not a word the row happens to use.
    assert not _quotes_near("0.007", "meaning gate"), "an unrelated number matched the anchored row"


def test_a_substring_is_not_a_match() -> None:
    """`0.5` must not be satisfied by `0.50` appearing inside `0.505`, or the check drifts as
    quietly as the thing it is checking."""
    assert re.search(r"(?<![\d.])0\.30(?![\d])", "the bar is 0.30 today") is not None
    assert re.search(r"(?<![\d.])0\.30(?![\d])", "the bar is 0.305 today") is None


def test_relaxed_sim_bar_is_the_documented_0_30() -> None:
    """Pin the exact value. An accidental 0.30->0.20 swept into an audit commit (690b6ab)
    during a rebase silently loosened the NLI meaning gate; only the L9 experiment's
    anchor-refusal caught it. The value must equal what thresholds.md quotes."""
    assert RELAXED_SIM_BAR == 0.30
    assert _quotes_near(f"{RELAXED_SIM_BAR:.2f}", "relaxed sim bar")
