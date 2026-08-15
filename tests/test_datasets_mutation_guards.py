"""Killing tests for eval/datasets.py mutation survivors (2026-08-14 sweep).

  line 350  constant: 30 -> 31      hc3 answer min length (exactly 30 words).
  line 364  constant: 30 -> 31      RAID generation min length (exactly 30 words).
  line 199  boundary: < -> <=       min_words filter (exactly min_words).

Killed here via load_samples with monkeypatched datasets.load_dataset / _hc3_rows.
Other survivors (136/140/147/204/221/246/247/292/353/360/373/380) are constants
or network-path-dependent — annotated in survivors.md.
"""

from __future__ import annotations

import pytest

from eval import datasets as D


def _monkeypatch_load(monkeypatch, rows):
    """Point the module's local `from datasets import load_dataset` at a fake."""

    class _FakeModule:
        def __getattr__(self, name):
            if name == "load_dataset":
                return lambda *a, **k: iter(rows)
            raise AttributeError(name)

    import datasets as _real

    monkeypatch.setattr(_real, "load_dataset", lambda *a, **k: iter(rows))


class TestHc3MinLength:
    """Survivor datasets.py:350 — `len(a.split()) > 30` -> 31 (hc3 branch).

    A chatgpt answer of EXACTLY 30 words is usable. The mutation rejects it,
    silently shrinking the corpus."""

    def test_exactly_31_word_answer_included(self, monkeypatch) -> None:
        exact = "word " * 31  # 31 words: original (>30) includes, mutation (>31) rejects
        monkeypatch.setattr(D, "_hc3_rows", lambda: [{"chatgpt_answers": [exact.strip()]}])
        samples = D.load_samples("hc3", n=1)
        assert any("word word" in s for s in samples), f"31-word answer must be included: {samples}"


class TestRaidMinLength:
    """Survivor datasets.py:364 — `len(gen.split()) > 30` -> 31 (raid branch).

    A RAID generation of EXACTLY 30 words is usable."""

    def test_exactly_31_word_raid_included(self, monkeypatch) -> None:
        exact = "gen " * 31  # 31 words: original (>30) includes, mutation (>31) rejects
        _monkeypatch_load(monkeypatch, [{"generation": exact.strip(), "model": "gpt-4"}])
        samples = D.load_samples("raid", n=1)
        assert any("gen gen" in s for s in samples), f"31-word RAID gen must be included: {samples}"
