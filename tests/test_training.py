"""Training-stack tests: multi-objective reward + loop distillation (offline, lite tier)."""

from __future__ import annotations

import pytest

from training.distill import distill
from training.reward import fluency, humanness_reward


def test_fluency_penalizes_repetition():
    assert fluency("the quick brown fox jumps over the lazy dog") > fluency("spam spam spam spam spam spam")
    assert fluency("hi") == 1.0  # too short -> neutral


def test_reward_penalizes_degenerate_and_meaning_drift():
    src = "The committee approved the budget after a brief discussion on Tuesday afternoon."
    good = src  # sim 1.0, fluent -> reward >= 0
    degenerate = "budget budget budget budget budget budget budget budget budget budget budget"
    assert humanness_reward(src, good, tier="lite") > humanness_reward(src, degenerate, tier="lite")
    assert humanness_reward(src, "", tier="lite") == -1.0


def test_free_ensemble_score_in_range():
    from training.reward import free_ensemble_score

    s = free_ensemble_score("Furthermore, we leverage robust synergies to optimize outcomes.", tier="lite")
    assert 0.0 <= s <= 1.0


def test_hard_sim_gate_rejects_offtopic():
    # An off-topic rewrite (meaning destroyed) must earn -1.0 outright, no evasion credit.
    src = "The committee approved the annual budget on Tuesday afternoon."
    offtopic = "Photosynthesis converts sunlight into chemical energy inside plant chloroplasts."
    assert humanness_reward(src, offtopic, tier="lite") == -1.0


def test_hard_length_gate_rejects_content_deletion():
    # High word-overlap but <50% length (content deleted) -> gated to -1.0 even below the sim floor.
    src = "The committee approved the annual budget after a long discussion on Tuesday afternoon here."
    truncated = "The committee approved the annual"  # every token is in src, but far too short
    assert humanness_reward(src, truncated, tier="lite", sim_floor=0.3) == -1.0


def test_build_pairs_human_fallback_without_datasets(monkeypatch):
    # With `datasets` unavailable, the free HC3 pair builder must fall back to smoke pairs (no network)
    # and still return well-formed {prompt, chosen, rejected} rows.
    import sys

    import training.dpo_humanizer as dpo

    monkeypatch.setitem(sys.modules, "datasets", None)  # `from datasets import ...` -> ImportError
    pairs = dpo.build_pairs_human(n=4)
    assert isinstance(pairs, list) and len(pairs) >= 1
    assert set(pairs[0]) >= {"prompt", "chosen", "rejected"}


def test_distill_keeps_passing_samples(monkeypatch):
    import untell.scripts.run as run_mod

    monkeypatch.setattr(
        run_mod, "untell_text", lambda text, **k: {"final": "a human rewrite", "flagged": False, "similarity": 0.9}
    )
    out = distill("builtin", n=3, tier="lite")
    assert out["kept"] == 3
    assert len(out["rows"]) == 3
    assert all("source" in r and "humanized" in r and "prompt" in r for r in out["rows"])


def test_distill_drops_flagged_or_low_similarity(monkeypatch):
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "untell_text", lambda text, **k: {"final": "x", "flagged": True, "similarity": 0.9})
    assert distill("builtin", n=3, tier="lite")["kept"] == 0

    monkeypatch.setattr(run_mod, "untell_text", lambda text, **k: {"final": "x", "flagged": False, "similarity": 0.2})
    assert distill("builtin", n=3, tier="lite")["kept"] == 0


class TestDistillRunsTheStrongLoop:
    """This function's filter DISCARDS any sample the loop fails to clear.

    So a weak loop does not merely produce weaker rows — it silently drops every sample a proper
    loop would have kept, shrinking the training set and biasing it toward the easiest texts.
    untell_text's own defaults are rewriter=None (auto-select, which needs an API key and otherwise
    returns "no rewriter configured" for every sample) and best_of=1, measured at 33% still flagged
    against 0% at best_of=3. distill passed neither, so it inherited both.
    """

    def _capture(self, monkeypatch):
        import untell.scripts.run as run_mod

        seen: list[dict] = []

        def fake(text, **kw):
            seen.append(kw)
            return {"final": "a human rewrite", "flagged": False, "similarity": 0.99}

        monkeypatch.setattr(run_mod, "untell_text", fake)
        return seen

    def test_a_free_rewriter_is_resolved_and_passed(self, monkeypatch):
        seen = self._capture(monkeypatch)
        distill("builtin", n=2, tier="lite")
        assert seen and all(kw["rewriter"] is not None for kw in seen), (
            "rewriter=None means auto-select, which needs an API key"
        )

    def test_best_of_defaults_to_three(self, monkeypatch):
        seen = self._capture(monkeypatch)
        distill("builtin", n=2, tier="lite")
        assert all(kw["best_of"] == 3 for kw in seen)

    def test_threshold_and_margin_reach_the_loop(self, monkeypatch):
        seen = self._capture(monkeypatch)
        distill("builtin", n=2, tier="lite", threshold=0.12, margin=0.34)
        assert all(kw["threshold"] == 0.12 and kw["margin"] == 0.34 for kw in seen)

    def test_an_unavailable_rewriter_is_refused_not_auto_selected(self, monkeypatch):
        """Falling through to auto-select would put a PAID hosted rewriter on every sample."""
        import untell.rewriter as rw_mod

        monkeypatch.setattr(rw_mod, "get_rewriter", lambda prefer=None: None)
        with pytest.raises(RuntimeError, match="Refusing to fall back"):
            distill("builtin", n=1, tier="lite", rewriter="mt_pivot")

    def test_the_cli_exposes_every_gate_and_forwards_it(self, monkeypatch, tmp_path):
        """threshold and margin were parameters of distill() that main never exposed or passed."""
        import training.distill as d

        seen: dict = {}
        monkeypatch.setattr(d, "distill", lambda **kw: seen.update(kw) or {
            "kept": 0, "total": 0, "requested": 0, "rows": []
        })
        d.main([
            "--n", "5", "--tier", "lite", "--threshold", "0.2", "--margin", "0.07",
            "--best-of", "4", "--rewriter", "surgical", "--out", str(tmp_path / "sft.jsonl"),
        ])
        assert seen["threshold"] == 0.2
        assert seen["margin"] == 0.07
        assert seen["best_of"] == 4
        assert seen["rewriter"] == "surgical"

    def test_the_cli_defaults_match_untell_humanize(self):
        from training.distill import build_parser

        defaults = {a.dest: a.default for a in build_parser()._actions}
        assert defaults["best_of"] == 3
        assert defaults["rewriter"] == "composite"
        assert defaults["tier"] == "full"


def test_dpo_build_pairs(monkeypatch):
    import training.distill as d

    monkeypatch.setattr(
        d, "distill", lambda *a, **k: {"rows": [{"prompt": "p", "source": "ai text", "humanized": "human text"}], "kept": 1, "total": 1}
    )
    from training.dpo_humanizer import build_pairs

    out = build_pairs("builtin", n=1, tier="lite")
    assert out["pairs"][0]["chosen"] == "human text"
    assert out["pairs"][0]["rejected"] == "ai text"


def test_dpo_smoke_pairs_are_valid():
    from training.dpo_humanizer import _smoke_pairs

    pairs = _smoke_pairs(3)
    assert len(pairs) == 3
    for p in pairs:
        assert p["chosen"] != p["rejected"] and "prompt" in p


def test_rl_build_dataset_n():
    from training.rl_humanizer import build_dataset

    rows = build_dataset("builtin", n=4)
    assert len(rows) == 4
    assert all("prompt" in r and "source" in r for r in rows)


def test_load_model_passthrough_without_4bit():
    # 4-bit off must return the model-id string (no torch/GPU needed) so trl loads it itself.
    from training.model_utils import load_model

    assert load_model("Qwen/Qwen2.5-3B-Instruct", load_4bit=False) == "Qwen/Qwen2.5-3B-Instruct"
