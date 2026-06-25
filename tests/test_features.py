"""Tests for the 'do everything' batch: ai_percent, doc reader, MCP, training reward, loop scrub/style."""

from __future__ import annotations

import importlib

from humanize.scripts.score import score_text


def test_score_has_ai_percent():
    r = score_text("Furthermore, the system operates predictably.", tier="lite")
    assert "ai_percent" in r
    assert abs(r["ai_percent"] - r["max"] * 100) < 0.11


def test_io_reads_plain_text(tmp_path):
    from humanize.scripts.io_utils import read_file

    p = tmp_path / "a.txt"
    p.write_text("hello world", encoding="utf-8")
    assert read_file(str(p)) == "hello world"


def test_mcp_module_imports_without_mcp_installed():
    m = importlib.import_module("humanize.mcp_server")
    assert callable(m.main)  # module imports even when `mcp` is absent (lazy import inside _server)


def test_training_reward_penalizes_meaning_drift():
    # Deterministic regardless of which detector "lite" resolves to: a meaning-preserving rewrite
    # (sim 1.0, no penalty, reward >= 0) must beat a meaning-broken one (low sim, big penalty, < 0).
    from training.reward import batch_rewards, humanness_reward

    src = "The cat sat on the mat in the warm afternoon sun, perfectly content."
    faithful = src
    broken = "Quantum chromodynamics governs the strong nuclear interaction between quarks and gluons."
    assert humanness_reward(src, faithful, tier="lite") > humanness_reward(src, broken, tier="lite")
    assert humanness_reward("x", "", tier="lite") == -1.0
    assert len(batch_rewards(src, [faithful, broken], tier="lite")) == 2


def test_loop_scrubs_hidden_chars(monkeypatch):
    import humanize.scripts.run as run_mod
    from humanize.scripts.run import humanize_text

    class _NoopRW:
        def rewrite(self, text, score_result, threshold=0.30):
            return text

    monkeypatch.setattr(run_mod, "get_rewriter", lambda prefer=None: _NoopRW())
    dirty = "hel​lo wor﻿ld this is enough text to pass."  # zero-width chars embedded
    res = humanize_text(dirty, tier="lite", scrub=True, max_iters=1)
    assert "​" not in res["final"] and "﻿" not in res["final"]


def test_style_appears_in_rewrite_prompt():
    from humanize.rewriter import build_rewrite_prompt

    p = build_rewrite_prompt("text", {"detectors": {"mage": 0.8}, "max": 0.8, "style": "blunt"}, 0.30)
    assert "Voice:" in p and "blunt" in p.lower()
