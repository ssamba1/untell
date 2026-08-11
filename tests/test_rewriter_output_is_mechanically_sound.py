"""A battery for breakage no metric in this repo can see.

Every gate the loop runs is blind to grammar. Cosine similarity, NLI entailment, the role check and
the tell catalogue all pass text that is not English: a stray capital mid-phrase, three discourse
markers stacked, a comma between a subject and its verb. Each of those shipped at some point, and
each was found by reading output rather than by a number moving.

So the reading becomes a battery. These run the real structural rewriter over real corpus text at
many seeds and assert the output does not contain shapes that are always wrong — not "scores
better", just *is not broken*. Corpus text, because the breakage found so far only appeared on real
sentences; hand-written probes are too clean to trigger it.
"""

from __future__ import annotations

import random
import re

import pytest

from untell.rewriter.structural import StructuralRewriter

SCORE: dict = {"tier": "full", "max": 1.0, "detectors": {}}

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _corpus(n: int = 12) -> list[str]:
    """Real AI-side documents. Skipped rather than failed when the corpus is unavailable."""
    try:
        from eval.datasets import load_pairs

        pairs = load_pairs("hc3", n=n, min_words=90)
    except Exception as exc:  # pragma: no cover - environment without the corpus
        pytest.skip(f"corpus unavailable: {exc}")
    if not pairs:  # pragma: no cover
        pytest.skip("corpus returned no pairs")
    return [ai for _, ai in pairs]


def _outputs() -> list[str]:
    out = []
    for i, text in enumerate(_corpus()):
        for intensity in (0.4, 0.7, 1.0):
            random.seed(1000 + i * 10 + int(intensity * 10))
            rw = StructuralRewriter(intensity=intensity)
            out.append(rw.rewrite(text, SCORE, 0.30, intensity=intensity))
    return out


# A comma between a bare subject pronoun and its verb: "even if it, is not specifically ranked".
_SUBJECT_VERB_COMMA = re.compile(
    r"\b(it|he|she|they|we|you|which|that|this)\s*,\s+"
    r"(is|are|was|were|has|have|had|will|would|can|could|does|do|did)\b",
    re.I,
)

# Three or more leading discourse markers: "Well, though, despite these potential downsides,".
_MARKER = (
    r"(?:actually|in practice|in short|put simply|also|now|basically|well|of course|"
    r"but|so|and|still|though|although|however|moreover|anyway|instead|despite)"
)
_STACKED_MARKERS = re.compile(rf"(?:^|(?<=[.!?])\s+){_MARKER},\s*{_MARKER},\s*{_MARKER}\b", re.I)

def _non_initial_caps(text: str) -> set[str]:
    """Capitalised words that are NOT the first word of their sentence.

    A positional pattern cannot do this job: the measured breakage was "New York Times Best
    seller", where the wrongly-capitalised word is preceded by other capitals, so any
    "lowercase-then-Capital" regex misses it. Comparing this set before and after asks the
    question directly — did the rewrite capitalise a word that was not capitalised before?
    """
    caps: set[str] = set()
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        for word in sentence.split()[1:]:
            token = word.strip(".,;:!?\"'()[]")
            if len(token) > 1 and token[0].isupper() and token[1:].islower():
                caps.add(token)
    return caps


def _sentence_initial_words(text: str) -> set[str]:
    """Words the source already capitalises at a sentence start — legitimately capitalisable."""
    out: set[str] = set()
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        words = sentence.split()
        if words:
            out.add(words[0].strip(".,;:!?\"'()[]"))
    return out

# A dangling sentinel fragment, e.g. an opener left attached to nothing.
_EMPTY_SENTENCE = re.compile(r"(?:^|[.!?])\s*[A-Z][a-z]*,\s*[.!?]")


def test_no_comma_between_a_subject_pronoun_and_its_verb():
    bad = [o for o in _outputs() if _SUBJECT_VERB_COMMA.search(o)]
    assert not bad, "\n\n".join(
        _SUBJECT_VERB_COMMA.search(o).group(0) + "  ||  " + o[:200] for o in bad[:3]
    )


def test_no_three_stacked_discourse_markers():
    bad = [o for o in _outputs() if _STACKED_MARKERS.search(o)]
    assert not bad, "\n\n".join(_STACKED_MARKERS.search(o).group(0) for o in bad[:3])


def test_no_capital_introduced_mid_phrase():
    """Compared against the INPUT: a capital already in the source is not this rewriter's doing.

    Words the source capitalises at a sentence start are excluded — prepending an opener moves
    such a word off the front legitimately ("The system ..." -> "Basically, the system ..."), and
    that is a case change this rewriter is entitled to make.
    """
    offenders = []
    for i, text in enumerate(_corpus()):
        allowed = _non_initial_caps(text) | _sentence_initial_words(text)
        for intensity in (0.4, 0.7, 1.0):
            random.seed(2000 + i * 10 + int(intensity * 10))
            rw = StructuralRewriter(intensity=intensity)
            out = rw.rewrite(text, SCORE, 0.30, intensity=intensity)
            new = _non_initial_caps(out) - allowed
            if new:
                offenders.append((sorted(new)[:3], out[:160]))
    assert not offenders, offenders[:3]


def test_no_capital_introduced_when_the_text_is_masked_first():
    """The path the real loop takes, and the only one that reproduces the measured bug.

    `run.py` locks entities before rewriting and restores them after. A sentence whose entity sits
    at the front then reaches the rewriter as "⟦HZ0001⟧ best seller list is ...", which is the
    shape that got the mid-phrase capital. Rewriting raw corpus text never produces a leading
    sentinel, so the unmasked test above cannot see this class at all.
    """
    try:
        from untell.scripts.preserve import lock, restore
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"preserve unavailable: {exc}")

    offenders = []
    for i, text in enumerate(_corpus()):
        allowed = _non_initial_caps(text) | _sentence_initial_words(text)
        masked, mapping = lock(text)
        if "⟦HZ" not in masked:
            continue
        for intensity in (0.4, 0.7, 1.0):
            random.seed(3000 + i * 10 + int(intensity * 10))
            rw = StructuralRewriter(intensity=intensity)
            out = restore(rw.rewrite(masked, SCORE, 0.30, intensity=intensity), mapping)
            new = _non_initial_caps(out) - allowed
            if new:
                offenders.append((sorted(new)[:3], out[:200]))
    assert not offenders, offenders[:3]


def test_no_sentence_is_left_as_a_bare_marker():
    bad = [o for o in _outputs() if _EMPTY_SENTENCE.search(o)]
    assert not bad, [_EMPTY_SENTENCE.search(o).group(0) for o in bad[:3]]


def test_the_battery_would_catch_the_shapes_it_names():
    """Guards the guard: a battery whose patterns never match anything protects nothing."""
    assert _SUBJECT_VERB_COMMA.search("even if it, is not specifically ranked as a best seller")
    assert _STACKED_MARKERS.search("Well, though, despite these potential downsides, many stay.")
    assert _EMPTY_SENTENCE.search("The result was clear. Basically, .")
    # The measured capitalisation bug, as the diff sees it.
    before = "The New York Times best seller list is a weekly list that ranks books."
    after = "The New York Times Best seller list is a weekly list that ranks books."
    allowed = _non_initial_caps(before) | _sentence_initial_words(before)
    assert _non_initial_caps(after) - allowed == {"Best"}
    # And the legitimate case it must NOT flag.
    plain = "The system handles every case."
    opened = "Basically, the system handles every case."
    allowed = _non_initial_caps(plain) | _sentence_initial_words(plain)
    assert not _non_initial_caps(opened) - allowed
