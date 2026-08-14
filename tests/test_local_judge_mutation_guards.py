"""Killing tests for local_judge.py mutation survivors (2026-08-14 sweep).

  line 178  boundary: >= -> >      percentage-vs-P(AI) disambiguation at exactly 2.0.

Killed here. The other 13 survivors (96/127/128/138/145/158 x2/160 x2/166/167/173/174)
need a live model or are decode/kwargs constants — annotated in survivors.md.
"""

from __future__ import annotations

import pytest

from untell.detectors.local_judge import LocalJudgeDetector


class _FakeTok:
    pad_token_id = 0

    def apply_chat_template(self, *a, **k):
        return "fake-input"

    def __call__(self, *a, **k):
        import numpy as np

        class _Enc(dict):
            def to(self, *a, **k):
                return self

        enc = _Enc()
        enc["input_ids"] = np.array([[1, 2, 3]])
        return enc

    def decode(self, ids, **k):
        return "2.0"  # exactly at the 2.0 boundary: 2.0% => 0.02 P(AI)


class _FakeParam:
    device = "cpu"


class _FakeModel:
    def generate(self, **k):
        return [_FakeOut()]

    def to(self, *a, **k):
        return self

    def eval(self):
        return self

    def parameters(self):
        return iter([_FakeParam()])

    def __call__(self, **k):
        return self


class _FakeOut:
    shape = (1, 4)

    def __getitem__(self, sl):
        # simulate a token tensor: slicing yields something indexable
        if isinstance(sl, slice):
            return _FakeOut()
        return _FakeOut()

    def __len__(self):
        return 4


class TestPercentageBoundary:
    """Survivor local_judge.py:178 — `val >= 2.0` mutated to `>`.

    A judge reply of exactly "2.0" is a percentage (2.0% => 0.02 P(AI)), not a
    P(AI) of 2.0. The mutation would clamp 2.0 to 1.0 — a perfectly ordinary
    percentage read as certainty."""

    def test_exactly_two_point_zero_is_percent(self, monkeypatch) -> None:
        d = LocalJudgeDetector()
        monkeypatch.setenv("UNTELL_ENABLE_LOCAL_JUDGE", "1")
        monkeypatch.setattr(LocalJudgeDetector, "_load", lambda self: (_FakeTok(), _FakeModel()))
        # _NUM finds "2.0"; val=2.0 >= 2.0 -> divide by 100 -> 0.02
        result = d.score("some text to judge")
        assert result is not None
        assert result == pytest.approx(0.02), f"expected 0.02, got {result}"
