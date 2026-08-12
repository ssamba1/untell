"""A comparison without a do-nothing arm cannot tell improvement from measurement noise.

Third of the eval tools to be given known-answers. `baselines.noop` and the `none (raw AI)` row in
`compare_humanizers` are controls: whatever else the table says, those must show a document that was
not touched.

MEASURED on a tell-dense probe paragraph, lite tier:

    noop            text unchanged True, iterations 0, pre max == post max (0.8667), similarity 1.0

    compare(), 2 texts, lite:
        none (raw AI)          ai_max 0.5703   tells/100w 28.68   sim 1.000   flagged 0.5
        synonym_swap           ai_max 0.5198   tells/100w 23.55   sim 0.947   flagged 0.5
        back_translation       ai_max 0.4434   tells/100w 19.16   sim 0.807   flagged 0.5
        ours_loop (surgical)   ai_max 0.5023   tells/100w 16.94   sim 0.815   flagged 0.5
        ours_loop (composite)  ai_max 0.2619   tells/100w 15.21   sim 0.833   flagged 0.0

Both correct. The control's `sim 1.000` is the load-bearing number: it is the only row that proves
the harness reports an untouched document as untouched, and every other row is read as a delta
against it.

`compare` itself is not executed here — `back_translation` pulls a Marian model — so its control arm
is asserted structurally, from the source. `noop` needs nothing and is exercised for real.
"""

from __future__ import annotations

import inspect
import logging

import pytest

from eval.baselines import noop, single_pass

PROBE = (
    "Moreover, the framework leverages a robust approach to deliver transformative outcomes at "
    "scale. Furthermore, it is important to note that this underscores the pivotal integration."
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.fixture(scope="module")
def noop_result():
    return noop(PROBE, tier="lite", threshold=0.3)


def test_noop_returns_the_text_it_was_given(noop_result) -> None:
    assert noop_result.text == PROBE
    assert noop_result.iterations == 0


def test_noop_scores_identically_before_and_after(noop_result) -> None:
    """The property the whole comparison rests on. If the control's own before and after disagree,
    every delta in the table is measuring the harness."""
    assert noop_result.pre["max"] == noop_result.post["max"]
    assert noop_result.similarity == 1.0


def test_noop_history_records_one_score(noop_result) -> None:
    """Zero iterations means one observation, not none — an empty history would make the control
    invisible in any plot or mean built from it."""
    assert noop_result.history == [noop_result.pre["max"]]


def test_a_real_strategy_is_distinguishable_from_the_control() -> None:
    """Guards the guard from the other side: if every strategy behaved like `noop`, the assertions
    above would pass while the comparison measured nothing at all."""
    result = single_pass(PROBE, tier="lite", threshold=0.3)
    assert result.text != PROBE or result.iterations > 0


def test_the_comparison_declares_a_control_arm() -> None:
    """Asserted from the source rather than by running it: `back_translation` pulls a Marian model,
    and a test that downloads 300MB to check a table has a header is a test nobody will keep.

    MEASURED once, by hand, and recorded in this file's docstring: the control reports sim 1.000
    against 0.807-0.947 for the strategies, so the row does behave as a control and not merely
    exist under that name."""
    import eval.compare_humanizers as mod

    source = inspect.getsource(mod)
    assert "none (raw AI)" in source, "the comparison lost its do-nothing arm"
