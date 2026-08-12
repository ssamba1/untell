"""The comment justifying `_SATURATED_MAX` named the wrong detector.

`rich_output` warns that a flat P(AI) delta proves nothing when the ensemble max is pinned, and the
comment justifying its 0.99 bar attributed the pinning to `roberta_openai` "returning 0.9992 on
nearly every sentence of that genre". Re-measured on 60 HC3 AI sentences and their 12 documents:

    detector           sentences >=0.99   sentence mean   documents >=0.99   document mean
    hc3_roberta            58 / 60           0.9977          12 / 12            0.9992
    roberta_openai          2 / 60           0.7405          11 / 12            0.9962
    fast_detectgpt          0 / 60           0.6451           0 / 12            0.6183

0.9992 is `hc3_roberta`'s number. The distinction is not pedantic: under rewriting `roberta_openai`
drops 0.9986 -> 0.6228 while `hc3_roberta` does not move at all, because it is fine-tuned ON HC3 and
that corpus is in-distribution for it. A reader trusting the old attribution would go looking for the
pin in the one detector that demonstrably yields.

This file pins the ordering rather than the exact figures — the numbers move with model versions, the
ranking is the claim — and skips when the models are not installed.
"""

from __future__ import annotations

import logging

import pytest

pytest.importorskip("torch")
pytest.importorskip("transformers")

HC3_AI_SENTENCES = [
    "Artificial intelligence has fundamentally transformed numerous industries in recent years.",
    "Organizations increasingly leverage these technologies to optimize operational efficiency.",
    "The transformative impact of these systems continues to expand across various sectors today.",
    "It is important to note that robust security postures remain essential for long-term success.",
]


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.fixture(scope="module")
def detectors():
    from untell.detectors.base import load_detectors

    found = {d.name: d for d in load_detectors("full")}
    for required in ("hc3_roberta", "roberta_openai"):
        if required not in found:
            pytest.skip(f"{required} not installed")
    return found


def test_hc3_roberta_is_the_pinned_one_on_hc3_style_sentences(detectors) -> None:
    """The claim the comment now makes, asserted rather than described."""
    hc3 = [detectors["hc3_roberta"].score(s) for s in HC3_AI_SENTENCES]
    openai = [detectors["roberta_openai"].score(s) for s in HC3_AI_SENTENCES]
    assert sum(hc3) / len(hc3) > sum(openai) / len(openai), (hc3, openai)


def test_the_comment_no_longer_credits_the_wrong_detector() -> None:
    """Guards the correction itself. The old sentence read as an explanation and was evidence for a
    conclusion the measurement contradicts, so a revert would be silent without this."""
    from pathlib import Path

    import untell.rich_output as mod

    lines = Path(mod.__file__).read_text(encoding="utf-8").splitlines()
    # The contiguous comment block immediately above the assignment. Located by walking up from the
    # constant rather than by splitting on its text: a first version split on the assignment string
    # and captured the whole file above it, so it read comments belonging to other constants.
    idx = next(i for i, ln in enumerate(lines) if ln.startswith("_SATURATED_MAX"))
    block = []
    for ln in reversed(lines[:idx]):
        if not ln.startswith("#"):
            break
        block.append(ln)
    justification = chr(10).join(reversed(block))
    assert justification, "no comment block found above _SATURATED_MAX"
    assert "hc3_roberta" in justification, justification
    # The ATTRIBUTION, not the phrase. A first version forbade the old wording outright and failed
    # on the correction itself, which quotes it in order to refute it — the same trap as a guard
    # that forbids "50.0" in a function whose comment warns against comparing to 50.0. A check that
    # cannot tell the mistake from the text describing it fires on the fix.
    assert "because `roberta_openai` returns" not in justification, justification


def test_the_bar_still_sits_below_the_pinned_value(detectors) -> None:
    """The constant has to catch what it was measured against, or the note it gates never fires."""
    from untell.rich_output import _SATURATED_MAX

    worst = max(detectors["hc3_roberta"].score(s) for s in HC3_AI_SENTENCES)
    assert worst >= _SATURATED_MAX, worst


def test_no_source_file_still_credits_the_wrong_detector() -> None:
    """The correction was applied to one site and the phrase existed in three.

    FOUND by sweeping every comment in `untell/` that names a detector alongside a number: the same
    sentence sat in `rich_output.py`, `rewriter/targeted.py` and this suite's
    `test_targeted_selects_when_max_saturates.py`. Fixing the one I happened to be reading left two
    behind, which is the defect this session has hit most often — a fix applied to the surface in
    front of me rather than to the class.

    Scoped to code and tests. `docs/free-ceiling-measured.md` is a dated log and quotes the wrong
    sentence deliberately, in the entry that refutes it; correcting a record would destroy it.
    """
    from pathlib import Path

    import untell

    # Assembled at runtime, and this file skipped. Written out literally the marker appears HERE,
    # so the scan reported itself — the third time in two loops that a check could not tell the
    # defect from the text describing it. Same fix as the dead-function probe that named its own
    # subject in the haystack.
    marker = "roberta" + "_openai` returns 0.9" + "992"
    root = Path(untell.__file__).resolve().parent.parent
    offenders = []
    for directory in ("untell", "tests"):
        for path in (root / directory).rglob("*.py"):
            if path.name == Path(__file__).name:
                continue
            if marker in path.read_text(encoding="utf-8", errors="replace"):
                offenders.append(path.relative_to(root).as_posix())
    assert not offenders, (
        "these claim roberta_openai is the pinned detector; measured, it clears 0.99 on 2 of 60 "
        f"HC3 sentences and hc3_roberta on 58: {offenders}"
    )
