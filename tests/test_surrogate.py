"""Surrogate + pluggable-reward tests (no torch needed — the loaders and reward routing only)."""

from __future__ import annotations

import pytest

from training import reward as reward_mod
from training.surrogate import _builtin_labeled, load_labeled


def test_builtin_labeled_balanced():
    data = _builtin_labeled(6)
    assert len(data) == 6
    assert any(lbl >= 0.5 for _, lbl in data)  # has AI
    assert any(lbl < 0.5 for _, lbl in data)   # has human
    for text, label in data:
        assert isinstance(text, str) and text
        assert label in (0.0, 1.0)


@pytest.mark.parametrize("n", [2, 4, 6, 8, 16, 32])
def test_builtin_labeled_is_balanced_at_every_even_n(n):
    """load_labeled documents its return as balanced; the builtin fallback was not.

    The classes were concatenated (all AI, then all human) and sliced to [:n], so with three of
    each n <= 3 produced zero human samples and the --smoke default of 16 gave 9 AI to 7 human.
    A single-class training set does not error — the model just learns to answer "AI".
    """
    data = _builtin_labeled(n)
    assert len(data) == n
    ai = sum(1 for _, lbl in data if lbl >= 0.5)
    assert ai == n // 2, f"n={n} gave {ai} AI and {n - ai} human"


def test_builtin_labeled_has_both_classes_at_the_smallest_useful_n():
    for n in (2, 3):
        data = _builtin_labeled(n)
        assert any(lbl >= 0.5 for _, lbl in data), n
        assert any(lbl < 0.5 for _, lbl in data), n


def test_builtin_labeled_zero_returns_nothing():
    assert _builtin_labeled(0) == []


def test_load_labeled_csv_n_zero_returns_no_rows(tmp_path):
    """`rows[:n] if n else rows` read 0 as "no limit" and handed back the whole CSV."""
    csv = tmp_path / "labels.csv"
    csv.write_text(
        "text,score\n"
        + "".join(f'"sample number {i} with plenty of words here",0.{i}\n' for i in range(5)),
        encoding="utf-8",
    )
    assert load_labeled(str(csv), n=0) == []
    assert len(load_labeled(str(csv), n=3)) == 3
    assert len(load_labeled(str(csv), n=99)) == 5  # capped by the file, not padded


def test_load_labeled_csv(tmp_path):
    csv = tmp_path / "labels.csv"
    csv.write_text(
        'text,score\n"some ai-sounding text that is plenty long",0.9\n"a person typed this one by hand",0.1\n',
        encoding="utf-8",
    )
    rows = load_labeled(str(csv))
    assert len(rows) == 2
    assert all(0.0 <= s <= 1.0 for _, s in rows)


def test_reward_uses_surrogate_when_env_set(monkeypatch):
    """With UNTELL_SURROGATE_DIR set, the reward target is the surrogate, not the local ensemble —
    this is the whole point: train against a GPTZero-mimicking model, not the non-transferring proxies."""

    class FakeSurrogate:
        def __init__(self, _dir):
            pass

        def score(self, _text):
            return 0.02  # surrogate says "human"

    import training.surrogate as surr

    monkeypatch.setattr(surr, "SurrogateDetector", FakeSurrogate)
    reward_mod._SURROGATE = None
    monkeypatch.setenv("UNTELL_SURROGATE_DIR", "out/whatever")
    try:
        assert reward_mod.target_ai_score("anything") == 0.02
    finally:
        reward_mod._SURROGATE = None


def test_reward_default_is_local_ensemble(monkeypatch):
    monkeypatch.delenv("UNTELL_SURROGATE_DIR", raising=False)
    reward_mod._SURROGATE = None
    s = reward_mod.target_ai_score("Furthermore, the system operates predictably and uniformly.", tier="lite")
    assert 0.0 <= s <= 1.0


def test_surrogate_no_signal_is_not_a_reward(monkeypatch):
    """The surrogate returns None for empty text (Detector protocol); float(None) would raise a
    bare TypeError from inside the reward loop, and any fabricated stand-in would be a reward for
    text nothing looked at."""

    class FakeSurrogate:
        def __init__(self, _dir):
            pass

        def score(self, _text):
            return None

    import training.surrogate as surr

    monkeypatch.setattr(surr, "SurrogateDetector", FakeSurrogate)
    reward_mod._SURROGATE = None
    monkeypatch.setenv("UNTELL_SURROGATE_DIR", "out/whatever")
    try:
        with pytest.raises(RuntimeError, match="no training signal"):
            reward_mod.target_ai_score("   ")
    finally:
        reward_mod._SURROGATE = None


def test_humanness_reward_still_works_lite(monkeypatch):
    monkeypatch.delenv("UNTELL_SURROGATE_DIR", raising=False)
    reward_mod._SURROGATE = None
    r = reward_mod.humanness_reward("The cat sat on the mat.", "A cat was sitting on the mat.", tier="lite")
    assert -1.0 <= r <= 1.0
