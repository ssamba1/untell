"""Training-stack tests: multi-objective reward + loop distillation (offline, lite tier)."""

from __future__ import annotations

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
