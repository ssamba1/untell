"""Contract tests for .claude/corpus.py — the bucketed-corpus builder.

Pins BUCKETS (the length/human buckets the free-ceiling corpora are built
from) and build()'s selection behavior.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude"))
import corpus as C  # noqa: E402


class TestBuckets:
    def test_buckets_cover_short_medium_long_human(self) -> None:
        for name in ("short", "medium", "long", "human"):
            assert name in C.BUCKETS, f"missing bucket {name}"

    def test_length_buckets_are_word_ranges(self) -> None:
        for name, (low, high, _why) in C.BUCKETS.items():
            assert low < high, f"{name}: low {low} must be < high {high}"
            assert low >= 1

    def test_human_bucket_spans_full_range(self) -> None:
        low, high, _why = C.BUCKETS["human"]
        assert low <= 150, f"human bucket must include short texts (low={low})"
        assert high >= 10000


class TestBuild:
    def test_build_writes_files(self, tmp_path, monkeypatch) -> None:
        def _load_pairs(dataset, n, min_words):
            # 450 words fits the long bucket (380-10000)
            return [("human text here " * 450, "ai text here " * 450)] * 3

        monkeypatch.setattr(C, "OUT", tmp_path)
        monkeypatch.setattr(C, "ROOT", tmp_path)
        monkeypatch.setattr("eval.datasets.load_pairs", _load_pairs)
        rc = C.build("hc3", "long", 2)
        assert rc == 0, f"expected rc 0, got {rc}"
        files = list(tmp_path.iterdir())
        assert files, "build must write corpus files"
        content = (tmp_path / "hc3-long.txt").read_text(encoding="utf-8")
        assert "ai text here" in content, "long bucket takes the AI side of pairs"

    def test_empty_bucket_refuses(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(C, "OUT", tmp_path)
        monkeypatch.setattr("eval.datasets.load_pairs", lambda dataset, n, min_words: [])
        with pytest.raises(SystemExit):
            C.build("hc3", "long", 2)

    def test_out_of_range_text_rejected(self, tmp_path, monkeypatch, capsys) -> None:
        """Survivor corpus.py:50 — `not (low <= words < high) or text in seen` -> `and`.

        A text OUTSIDE the bucket range must be rejected even when it is not a
        duplicate. The mutation (`and`) keeps out-of-range non-duplicates."""

        def _load_pairs(dataset, n, min_words):
            # 20 words: below the long bucket's 380 floor
            return [("human " * 20, "ai " * 20)]

        monkeypatch.setattr(C, "OUT", tmp_path)
        monkeypatch.setattr(C, "ROOT", tmp_path)
        monkeypatch.setattr("eval.datasets.load_pairs", _load_pairs)
        with pytest.raises(SystemExit):
            C.build("hc3", "long", 1)

    def test_exact_low_bound_included(self, tmp_path, monkeypatch) -> None:
        """Survivor corpus.py:50 — `low <= words` -> `low < words`.

        A text at EXACTLY the bucket floor (380 words) is in range. The
        mutation rejects it."""

        def _load_pairs(dataset, n, min_words):
            return [("human " * 380, "ai " * 380)]  # exactly 380 words

        monkeypatch.setattr(C, "OUT", tmp_path)
        monkeypatch.setattr(C, "ROOT", tmp_path)
        monkeypatch.setattr("eval.datasets.load_pairs", _load_pairs)
        rc = C.build("hc3", "long", 1)
        assert rc == 0, f"exact-floor text must be accepted (rc={rc})"
