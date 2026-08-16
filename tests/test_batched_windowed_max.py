"""batched_windowed_max contracts — pure logic, no model loads.

The batched adapters (roberta_openai, hc3_roberta, fast_detectgpt, mage) score all
windows of a long document in a handful of model calls instead of one per window.
This file pins the packing/aggregation logic that is shared with ``windowed_max``:

* the windows fed to the batch scorer are exactly the windows ``windowed_max``
  would score one at a time (identical max on identical input),
* ``batch_size`` is honoured (never a larger chunk),
* None/NaN windows are dropped, exactly like the per-window path,
* text that fits one window is scored in a single batch of one, unchanged.

The per-window *score identity* between a 1-window batch and an N-window batch is a
model-level property and is pinned in tests/test_batched_detector_identity.py (slow,
full tier), because it needs a live forward pass.
"""

from __future__ import annotations

import math

from untell.detectors.base import WINDOW_WORDS, batched_windowed_max, windowed_max


def _long_text(n: int = 150) -> str:
    return " ".join(f"Sentence number {i} here with some more words." for i in range(n))


def _fake_scorer(window: str) -> float:
    return len(window.split()) / 1000.0


def test_batched_max_equals_windowed_max() -> None:
    text = _long_text()
    a = windowed_max(text, _fake_scorer, window_words=50)
    b = batched_windowed_max(text, lambda ws: [_fake_scorer(w) for w in ws], window_words=50)
    assert a == b


def test_batches_never_exceed_batch_size() -> None:
    text = _long_text()
    seen: list[int] = []

    def sb(ws):
        seen.append(len(ws))
        return [0.5] * len(ws)

    batched_windowed_max(text, sb, window_words=50, batch_size=4)
    assert len(seen) > 1, "expected several batches"
    assert max(seen) <= 4, f"a batch of {max(seen)} exceeded batch_size=4"


def test_none_and_nan_windows_are_dropped() -> None:
    text = _long_text()
    calls = {"n": 0}

    def sb(ws):
        out = []
        for w in ws:
            calls["n"] += 1
            if calls["n"] % 3 == 0:
                out.append(None)      # no signal
            elif calls["n"] % 3 == 1:
                out.append(float("nan"))  # failure signal — must not poison the max
            else:
                out.append(0.42)
        return out

    assert batched_windowed_max(text, sb, window_words=50) == 0.42


def test_short_text_is_one_batch_of_one() -> None:
    seen: list[list[str]] = []
    batched_windowed_max("Short text only.", lambda ws: seen.append(ws) or [0.5])
    assert seen == [["Short text only."]]


def test_all_none_returns_none() -> None:
    text = _long_text()
    assert batched_windowed_max(text, lambda ws: [None] * len(ws), window_words=50) is None


def test_single_window_batches_cover_all_windows() -> None:
    text = _long_text()
    covered: list[str] = []

    def sb(ws):
        covered.extend(ws)
        return [0.5] * len(ws)

    batched_windowed_max(text, sb, window_words=50, batch_size=7)
    joined = " ".join(covered)
    # windowing may re-join sentences with single spaces; content must be preserved
    assert "".join(joined.split()) == "".join(text.split()), "windowing lost or reordered words"
    assert len(covered) > 1


def test_single_call_path_preserves_newlines() -> None:
    # mirrors test_base_mutation_guards: text that fits one window is passed through
    # UNCHANGED (line structure intact), not re-joined with spaces.
    s1 = " ".join(f"w{i}." for i in range(WINDOW_WORDS // 2))
    s2 = " ".join(f"v{i}." for i in range(WINDOW_WORDS // 2))
    text = s1 + "\n\n" + s2
    assert len(text.split()) == WINDOW_WORDS
    seen: list[list[str]] = []

    def sb(ws):
        seen.append(ws)
        return [0.5] * len(ws)

    batched_windowed_max(text, sb)
    assert seen == [[text]]
    assert "\n" in seen[0][0]
