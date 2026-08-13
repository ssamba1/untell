"""What must be true of any output, checked against the input rather than against zero.

Results 215-218 each started from a suspicion and found the defect that suspicion pointed at.
Result 219 started from "what must be true of any output" and found one in a different subsystem, of
a different kind, in the corpus the others were blind to. This file is that sweep, kept.

MEASURED at the time of writing, 50 halves per corpus, `tier=lite`, `max_iters=2`:

    HC3    62% of documents changed, 14 invariants   ->  0 new violations
    RAID   64% of documents changed, 14 invariants   ->  0 new violations   (2 before the fix)

Three things make the table trustworthy, and all three are asserted here rather than assumed:

* **Counted against the SOURCE.** Real prose has a background rate. HC3 arrives with 8 unbalanced
  brackets, 9 doubled punctuation marks and 584 spaces before punctuation of its own; an
  uncontrolled count reports those as damage and attributes them to the rewriter.
* **The change rate is part of the result.** "No new violations" from a transform that did nothing
  is not a result, and a rewriter that silently became inert is a defect this repository has
  actually shipped — see the saturating-detector result, where the DEFAULT rewriter was a no-op on
  10 of 10 documents and every quality number looked fine.
* **More than one corpus.** The defect Result 219 found is 2 of 50 on RAID and 0 of 50 on HC3,
  because forum prose does not write "e.g." at all.

The sample here is smaller than the measurement above so the file can run alongside the rest of the
suite; it is marked slow and skips when the corpora are not installed.
"""

from __future__ import annotations

import logging
import re

import pytest

from untell.scripts.run import untell_text

pytestmark = pytest.mark.slow

DOCS_PER_CORPUS = 12
# A rewriter that changes nothing satisfies every invariant below. Measured at 62-64%; the bar is
# set well under that so ordinary variation does not fail the suite, and an inert rewriter does.
MIN_CHANGE_RATE = 0.30

INVARIANTS = {
    # A sentence boundary inside a bracket. The sentence continues after the close, so a clause in
    # there can never stand alone however well-formed it looks.
    "sentence break inside a bracket": lambda t: len(re.findall(r"\([^()]*[.!?]\s+[A-Z][^()]*\)", t)),
    "unbalanced brackets": lambda t: abs(t.count("(") - t.count(")")),
    "unbalanced double quotes": lambda t: t.count('"') % 2,
    "unbalanced curly quotes": lambda t: abs(t.count("“") - t.count("”")),
    "doubled punctuation": lambda t: len(re.findall(r"[.!?,;:]\s*[.!?,;:]", t)),
    "lowercase sentence start": lambda t: len(re.findall(r"(?:^|[.!?]\s+)[a-z]", t)),
    "doubled word": lambda t: len(re.findall(r"\b(\w+)\s+\1\b", t, re.I)),
    "empty bracket": lambda t: len(re.findall(r"\(\s*\)", t)),
    "comma before a close": lambda t: len(re.findall(r",\s*[)\]]", t)),
    "double space": lambda t: len(re.findall(r"\S  +\S", t)),
    # "... and." — a sentence ended on the word that was meant to join it to the next one.
    "stranded conjunction": lambda t: len(
        re.findall(r"\b(?:and|but|or|because|which|that)\s*[.!?]", t, re.I)
    ),
    "period next to a comma": lambda t: len(re.findall(r"\.\s*,|,\s*\.", t)),
    "sentinel left in the output": lambda t: len(re.findall(r"⟦|⟧|HZ\d{4}", t)),
    "space before punctuation added": lambda t: len(re.findall(r"\s[.,;:!?]", t)),
}


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.fixture(scope="module", params=["hc3", "raid"])
def rewritten(request) -> list[tuple[str, str]]:
    """(source, output) pairs. Module-scoped: the rewrite is the expensive part and every assertion
    below reads the same pairs."""
    pytest.importorskip("datasets")
    from eval.datasets import load_pairs

    try:
        pairs = load_pairs(request.param, n=DOCS_PER_CORPUS * 2, min_words=60)
    except Exception as exc:  # noqa: BLE001 - corpus availability is environmental
        pytest.skip(f"{request.param} unavailable: {exc}")
    texts = [t for pair in pairs for t in pair][:DOCS_PER_CORPUS]
    if len(texts) < 4:
        pytest.skip(f"{request.param} returned too few texts")
    return [(t, untell_text(t, tier="lite", max_iters=2)["final"]) for t in texts]


def test_the_rewriter_actually_changed_something(rewritten) -> None:
    """The guard that keeps every other assertion in this file from being vacuous. It is first on
    purpose: if this fails, the rest of the file is reporting the cleanliness of a no-op."""
    changed = sum(1 for src, out in rewritten if out.strip() != src.strip())
    rate = changed / len(rewritten)
    assert rate >= MIN_CHANGE_RATE, f"{changed}/{len(rewritten)} changed"


@pytest.mark.parametrize("name", sorted(INVARIANTS))
def test_no_new_violations(name: str, rewritten) -> None:
    """Each invariant, counted as NEW occurrences only. A document that arrives with the defect
    keeps it — this asks what the rewriter added, which is the only part it is answerable for."""
    measure = INVARIANTS[name]
    offenders = []
    for src, out in rewritten:
        before, after = measure(src), measure(out)
        if after > before:
            offenders.append((after - before, out[:120]))
    assert not offenders, offenders[:2]


# One text that violates each invariant, so a sweep that reports zero is reporting a measurement
# rather than a dead pattern. This repository has shipped a counting regex that matched nothing —
# a literal 0x08 where `\b` was meant — and read as a clean zero in 2526 tests.
KNOWN_POSITIVES = {
    "sentence break inside a bracket": "The plan passed (the vote was close. Two members abstained).",
    "unbalanced brackets": "The plan passed (the vote was close and two members abstained.",
    "unbalanced double quotes": 'The report said "value for money and the committee agreed.',
    "unbalanced curly quotes": "The report said “value for money and the committee agreed.",
    "doubled punctuation": "The plan passed,. and the committee agreed to it.",
    "lowercase sentence start": "The plan passed. the committee agreed to it.",
    "doubled word": "The the plan passed and the committee agreed.",
    "empty bracket": "The plan passed () and the committee agreed.",
    "comma before a close": "The plan passed (the vote was close,) and the committee agreed.",
    "double space": "The plan  passed and the committee agreed.",
    "stranded conjunction": "The plan passed and. The committee agreed to it.",
    "period next to a comma": "The plan passed ., and the committee agreed.",
    "sentinel left in the output": "The plan ⟦HZ0000⟧ passed and the committee agreed.",
    "space before punctuation added": "The plan passed , and the committee agreed.",
}


@pytest.mark.parametrize("name", sorted(INVARIANTS))
def test_each_invariant_fires_on_a_known_positive(name: str) -> None:
    """Guards the guard, and it is the failure mode that costs the most: an invariant that cannot
    detect its own defect passes on every document forever and reads as evidence of health."""
    clean = "The plan passed and the committee agreed to it without any further discussion."
    assert INVARIANTS[name](KNOWN_POSITIVES[name]) > 0, name
    assert INVARIANTS[name](clean) == 0, name


def test_the_meaning_survives_the_sweep(rewritten) -> None:
    """Not an invariant of form but of size, and the cheapest possible check that the rewriter is
    not simply deleting the hard parts — which would satisfy every pattern above perfectly."""
    for src, out in rewritten:
        assert len(out.split()) >= 0.6 * len(src.split()), out[:120]
