"""Contract tests for .claude/guard.py — the band-enforcement gate.

Pins the guard that every commit in this repo passes through:
  - RED files (docs/README) must be flagged red
  - test removal must be red (green by deletion is not green)
  - tuning constant changes must be red
  - same-count test renames are amber, not red

These are the rules that make the audit's findings trustworthy.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude"))
import guard as G  # noqa: E402


class _Drive:
    """Stub the guard's git helpers with controlled inputs."""

    def __init__(self, monkeypatch, files=(), diff="", deleted=()):
        monkeypatch.setattr(G, "changed_files", lambda rng=None: list(files))
        monkeypatch.setattr(G, "diff_text", lambda rng=None: diff)
        monkeypatch.setattr(G, "deleted_files", lambda rng=None: list(deleted))


class TestRedFiles:
    def test_docs_touch_is_red(self, monkeypatch) -> None:
        _Drive(monkeypatch, files=["docs/why-best-open-repo.md"])
        red, amber = G.check(None)
        assert any("RED file touched" in r for r in red), red

    def test_readme_touch_is_red(self, monkeypatch) -> None:
        _Drive(monkeypatch, files=["README.md"])
        red, amber = G.check(None)
        assert any("RED file touched" in r for r in red), red

    def test_source_touch_is_clean(self, monkeypatch) -> None:
        _Drive(monkeypatch, files=["untell/scripts/score.py"])
        red, amber = G.check(None)
        assert not red, red


class TestTestRemoval:
    def test_removed_test_is_red(self, monkeypatch) -> None:
        diff = "-def test_something_important():\n"
        _Drive(monkeypatch, files=["tests/test_x.py"], diff=diff)
        red, amber = G.check(None)
        assert any("test removed" in r for r in red), red

    def test_rename_is_amber_not_red(self, monkeypatch) -> None:
        diff = "-def test_old_name():\n+def test_new_name():\n"
        _Drive(monkeypatch, files=["tests/test_x.py"], diff=diff)
        red, amber = G.check(None)
        assert not red, red
        assert any("renamed" in a for a in amber), amber


class TestTuningConstants:
    def test_tuning_constant_change_is_red(self, monkeypatch) -> None:
        diff = "+_SENTENCE_ENTAILMENT_FLOOR = 0.61\n"
        _Drive(monkeypatch, files=["untell/scripts/score.py"], diff=diff)
        red, amber = G.check(None)
        assert any("tuning constant" in r for r in red), red

    def test_plain_code_change_is_clean(self, monkeypatch) -> None:
        diff = "+    return clamp01(x)\n"
        _Drive(monkeypatch, files=["untell/scripts/score.py"], diff=diff)
        red, amber = G.check(None)
        assert not red, red


class TestDeletedTestFile:
    def test_deleted_test_file_is_red(self, monkeypatch) -> None:
        _Drive(monkeypatch, deleted=["tests/test_removed.py"])
        red, amber = G.check(None)
        assert any("test file deleted" in r for r in red), red


class TestQueueDiscipline:
    """Survivors guard.py:145 — `amber and QUEUE not in files` -> `or` / `in`.

    AMBER work with the queue staged in the SAME commit is fine. The `or`
    mutation warns anyway; the `in` mutation warns precisely when the queue
    IS staged."""

    def test_amber_with_queued_entry_is_clean(self, monkeypatch) -> None:
        _Drive(
            monkeypatch,
            files=[".github/workflows/ci.yml", G.QUEUE],
        )
        red, amber = G.check(None)
        # amber work exists, queue staged -> no discipline warning
        assert not any("written down" in a for a in amber), amber

    def test_amber_without_queue_warns(self, monkeypatch) -> None:
        _Drive(monkeypatch, files=[".github/workflows/ci.yml"])
        red, amber = G.check(None)
        assert any("written down" in a for a in amber), amber
