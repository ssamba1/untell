"""Replace any one structural transform with identity and the output must change.

FOUND by asking the question Result 186 raised about the suite rather than the code: how many tests
assert "the output changed" as a proxy for "the transform ran"? A transform that silently became a
no-op would satisfy those, and this repository has shipped exactly that — a saturating detector made
`cand < best` unreachable and the DEFAULT rewriter went out as a no-op on 10 of 10 HC3 documents.

MEASURED by stubbing each transform to identity and running the suites. The first sweep, over six
files, reported three transforms whose removal broke nothing:

    _split_long_sentences   79 passed
    _target_burstiness      79 passed
    _flatten_copula         79 passed

All three were artifacts of the file selection. Against the wider structural suites:

    _split_long_sentences   5 failed
    _target_burstiness      4 failed
    _flatten_copula         3 failed

**All eight transforms are covered.** No gap — but that coverage is spread across 27 files and 670
tests, and nobody could state it without running this sweep.

This file makes the property local and cheap. `test_every_knob_has_an_effect.py` asks the same
question of the documented KNOBS and never stubs anything (0 monkeypatch calls); the two are
complementary — a knob can be wired correctly to a transform that does nothing.

Seeds, not a seed: every one of these transforms is probabilistic, so a single seed showing no
difference is evidence about the seed.
"""

from __future__ import annotations

import logging
import random

import pytest

import untell.rewriter.structural as structural
from untell.rewriter.structural import structural_rewrite

# Transforms taking a list of sentences, and those taking a whole string. The stub has to match, or
# the "no effect" it reports is a TypeError swallowed somewhere upstream.
SENTENCE_LEVEL = (
    "_merge_sentences",
    "_split_long_sentences",
    "_vary_openers",
    "_target_burstiness",
    "_strip_transitions",
    "_drop_restatements",
)
TEXT_LEVEL = (
    "_flatten_cliches",
    "_plain_register",
    "_flatten_copula",
    "_flatten_participial_trailers",
)
# The fixture has to be able to exercise every transform, or "no effect" is a fact about the
# fixture. The first version was 15-20 words a sentence with nothing restated, and it reported
# `_split_long_sentences` and `_drop_restatements` dead — both simply had nothing to act on: the
# splitter needs a sentence over 28 words, and the restatement drop needs one sentence to restate
# another. Same shape as the zero denominators in Results 184 and 186.
TELL_HEAVY = (
    "Moreover, the framework leverages a robust approach to delivery at scale across the whole "
    "programme this year. Furthermore, it is important to note that this underscores the pivotal "
    "integration for every team involved. The system utilizes a comprehensive methodology "
    "throughout the year, which is designed to be scalable. Additionally, the platform empowers "
    "users to streamline their daily workflows considerably. The intricate design fosters a "
    "vibrant ecosystem, delivering value for everyone in the landscape. "
    # over 28 words, with a comma near the midpoint — reaches `_split_long_sentences`
    "The reporting layer aggregates every metric the platform collects across all of its regions "
    "and business units, and it then presents the resulting figures to the finance team in a "
    "single consolidated dashboard each morning without any manual intervention at all. "
    # a restatement of the sentence above it — reaches `_drop_restatements`
    "The reporting layer aggregates the metrics and shows them to the finance team. "
    "In conclusion, organizations must harness these seamless solutions today without delay."
)
SEEDS = (1, 3, 7, 11, 17)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def _rewrites() -> list[str]:
    out = []
    for seed in SEEDS:
        random.seed(seed)
        out.append(structural_rewrite(TELL_HEAVY))
    return out


def test_the_baseline_actually_rewrites() -> None:
    """The premise. If the pipeline left this text alone, every assertion below would be comparing
    the input against itself and passing for it."""
    assert any(r != TELL_HEAVY for r in _rewrites())


# Transforms this fixture can show CHANGING the output. The other three are conditional on input
# this one does not provide — `_target_burstiness` acts only when sentence-length variance is below
# its target, `_drop_restatements` needs a pair its similarity bar actually flags, and
# `_flatten_copula` is rate-gated on top of needing a copula. Their coverage is real and was
# measured by stubbing them against the wider structural suites (5, 3 and 4 failures respectively);
# what this file adds for them is that they are REACHED, which is the half a fixture can settle.
EFFECTFUL = (
    "_merge_sentences",
    "_split_long_sentences",
    "_vary_openers",
    "_strip_transitions",
    "_flatten_cliches",
    "_plain_register",
)
REACHED_ONLY = ("_target_burstiness", "_drop_restatements", "_flatten_copula")


def _stub_for(name: str):
    if name in SENTENCE_LEVEL:
        return lambda sentences, *a, **k: list(sentences)
    return lambda text, *a, **k: text


@pytest.mark.parametrize("name", EFFECTFUL)
def test_the_transform_changes_the_output(name: str, monkeypatch) -> None:
    baseline = _rewrites()
    monkeypatch.setattr(structural, name, _stub_for(name))
    assert _rewrites() != baseline, f"{name} can be replaced by identity with no visible effect"


@pytest.mark.parametrize("name", REACHED_ONLY + EFFECTFUL)
def test_the_transform_is_reached(name: str, monkeypatch) -> None:
    """Weaker and worth asserting separately: a transform that is never CALLED is dead however good
    its own tests are, and that is the shape of the no-op default rewriter this repo shipped."""
    calls = []
    original = getattr(structural, name)

    def spy(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(structural, name, spy)
    _rewrites()
    assert calls, f"{name} is never called on the shipped path"


def test_the_stub_shapes_match_the_transforms() -> None:
    """Guards the guard. A sentence-level transform stubbed with a text-level lambda raises inside
    the pipeline, and an exception swallowed upstream would read as 'no effect' — the failure this
    file would otherwise report as a defect."""
    import inspect

    for name in SENTENCE_LEVEL:
        first = next(iter(inspect.signature(getattr(structural, name)).parameters))
        assert first == "sentences", (name, first)
    for name in TEXT_LEVEL:
        first = next(iter(inspect.signature(getattr(structural, name)).parameters))
        assert first == "text", (name, first)
