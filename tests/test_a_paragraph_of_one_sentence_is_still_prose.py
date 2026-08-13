"""The transform that offsets duplicate openers was never called on a one-sentence paragraph.

FOUND by asking where else a per-block scope disagrees with a per-document property. `_rewrite_prose`
guards its sentence stages with `len(sents) >= 2`, and the comment on that guard already names the
transforms that need a PAIR — merge, restatement-drop, burstiness. Prepending a marker to one
sentence is not one of them. `_strip_transitions` had been moved out of that guard for exactly this
reason; `_vary_openers` was left inside, so the two halves of one job disagreed.

Instrumented, on three sentences:

    1 block of 3     _vary_openers called 1x
    3 blocks of 1    _vary_openers called 0x

So a transcript, a bullet list or a changelog had its transitions stripped — "Moreover," /
"Furthermore," / "Additionally," deleted — and nothing ever ran to vary what the deletion exposed.

**The first measurement of the damage was wrong, and re-measuring is what this file records.** A
synthetic document of eighteen sentences showed repeated openers going 12 in -> 14.00 out: the tool
adding the tell it exists to remove. That document was three verbatim copies of six sentences, so it
was repetitive by construction and the number was a property of the corpus, not the code.

MEASURED again on 12 real HC3 documents, 5 seeds, before and after — the same documents in both arms
and the layout the only other variable:

    arm      layout              n    dups in   dups out    delta
    before   as written         60      2.08      2.23      +0.15
    before   one sentence/para  55      2.09      2.18      +0.09
    after    as written         60      2.08      2.15      +0.07
    after    one sentence/para  58      2.09      2.00      -0.09

**The sign flips.** On one-sentence paragraphs the rewriter went from adding duplicate openers to
removing them, and the as-written case improved too, because `seen` lets a later paragraph know what
the earlier ones opened with. The effect is small in absolute terms — a fifth of a duplicate per
document — and the as-written arm is still slightly positive, which is the known budgeted cost this
suite records elsewhere (+13 openers created against 28 removed over 60 texts).
"""

from __future__ import annotations

import logging
import random

import pytest

import untell.rewriter.structural as structural
from untell.rewriter.structural import _vary_openers, structural_rewrite

THREE = [
    "Moreover, the framework leverages a robust approach to delivery at scale.",
    "Furthermore, it is important to note that this underscores the integration.",
    "Additionally, the platform empowers users to streamline their workflows.",
]


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.fixture
def calls(monkeypatch) -> list[int]:
    """Block sizes `_vary_openers` was actually handed."""
    seen: list[int] = []
    original = structural._vary_openers

    def spy(sentences, rate=0.3, **kwargs):
        seen.append(len(sentences))
        return original(sentences, rate, **kwargs)

    monkeypatch.setattr(structural, "_vary_openers", spy)
    return seen


def test_a_one_sentence_paragraph_reaches_the_transform(calls) -> None:
    """The defect, stated as reach. Instrumented it was 0 calls: the strip ran, the offset did not."""
    random.seed(0)
    structural_rewrite("\n\n".join(THREE))
    assert calls, "_vary_openers was never called on single-sentence blocks"


def test_a_multi_sentence_paragraph_still_reaches_it(calls) -> None:
    """Guards the guard. If the spy never fired for either layout the assertion above would pass
    for the wrong reason."""
    random.seed(0)
    structural_rewrite(" ".join(THREE))
    assert calls


def test_the_document_counts_make_a_lone_repeat_visible() -> None:
    """A block of one has no duplicate to find inside itself, so the counts have to come from the
    document. With a budget of one, the sentence whose opener repeats is the one that gets served."""
    sentences = [
        "The report was filed on time.",
        "Engineers reviewed the design again.",
        "Auditors confirmed the totals.",
        "Nobody objected to the schedule.",
    ]
    # "The" has been seen three times already in this document, so sentence 0 is the duplicate.
    served = None
    for seed in range(40):
        random.seed(seed)
        out = _vary_openers(list(sentences), rate=0.25, seen={"the": 3})
        changed = [i for i, (a, b) in enumerate(zip(sentences, out)) if a != b]
        if changed:
            served = changed[0]
            break
    assert served == 0, f"the repeated opener was not served first (served {served})"


def test_the_counter_accumulates_across_blocks() -> None:
    """`seen` is how one paragraph tells the next what it opened with. Without the accumulation
    every block would look unique to the one after it."""
    seen: dict[str, int] = {}
    random.seed(0)
    _vary_openers(["The report was filed on time."], rate=0.0, seen=seen)
    _vary_openers(["The auditors confirmed the totals."], rate=0.0, seen=seen)
    assert seen.get("the") == 2, seen


def test_it_still_works_with_no_counter() -> None:
    """Called directly — as every other caller and test does — the transform owns its own view."""
    random.seed(0)
    assert len(_vary_openers(list(THREE), rate=1.0)) == len(THREE)


def test_the_dose_stays_near_the_human_share() -> None:
    """The calibration this transform was given a budget for: humans open with these markers 3.13%
    of the time, and the output once sat at 36.54% — 12x. Reaching MORE sentences must not undo it.

    MEASURED across four layouts of the same 18 sentences: 4.08% to 5.28%, or 1.30x to 1.69x human.
    The bar is set well above that and far below the failure it guards.
    """
    from untell.text_split import split_sentences

    pool = list(structural._OPENERS)
    sentences = [
        "Moreover, the framework leverages a robust approach to delivery at scale.",
        "Furthermore, it is important to note that this underscores the integration.",
        "Additionally, the platform empowers users to streamline their workflows.",
        "In addition, the intricate design fosters a vibrant ecosystem for everyone.",
        "Consequently, stakeholders can leverage the myriad benefits of the solution.",
        "Notably, the system utilizes a comprehensive methodology across the teams.",
    ] * 3
    for size in (18, 3, 1):
        doc = "\n\n".join(
            " ".join(sentences[i : i + size]) for i in range(0, len(sentences), size)
        )
        opened = total = 0
        for seed in range(12):
            random.seed(seed)
            out = structural_rewrite(doc)
            found = [s for line in out.split("\n") for s in split_sentences(line) if s.strip()]
            opened += sum(1 for s in found if any(s.lstrip().startswith(o) for o in pool))
            total += len(found)
        share = 100 * opened / total
        assert share < 12.0, f"{size}-sentence blocks: {share:.2f}% of sentences open with a marker"


@pytest.mark.parametrize("size", [18, 3, 1])
def test_seeding_is_still_deterministic(size: int) -> None:
    """Shared mutable counts across blocks must not cost reproducibility."""
    doc = "\n\n".join(" ".join(THREE[i : i + size]) for i in range(0, len(THREE), size))
    assert structural_rewrite(doc, seed=5) == structural_rewrite(doc, seed=5)
