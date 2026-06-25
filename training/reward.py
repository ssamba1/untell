"""Reward function for RL-against-ensemble training (StealthRL / AuthorMist style).

reward = (1 - max P(AI) across our detector ensemble) - meaning-drift penalty

Pure-python over our own detectors + semantic similarity, so it is testable on the lite tier with no
GPU. The RL trainer (rl_humanizer.py) calls this to score generated paraphrases; train against the
``full`` tier (or ``commercial`` with keys) to learn a humanize-by-default policy.
"""

from __future__ import annotations

from humanize.scripts.quality import similarity
from humanize.scripts.score import score_text


def humanness_reward(original: str, candidate: str, *, tier: str = "full", sim_floor: float = 0.76) -> float:
    """Higher = more human + meaning preserved. Evasion minus a penalty for dropping below the sim floor."""
    if not candidate.strip():
        return -1.0
    ai = float(score_text(candidate, tier=tier)["max"])
    sim = similarity(original, candidate)
    evade = 1.0 - ai
    penalty = 0.0 if sim >= sim_floor else (sim_floor - sim) * 2.0
    return round(evade - penalty, 4)


def batch_rewards(original: str, candidates: list[str], *, tier: str = "full", sim_floor: float = 0.76) -> list[float]:
    """Rewards for several candidate rewrites of one source (GRPO scores a group per prompt)."""
    return [humanness_reward(original, c, tier=tier, sim_floor=sim_floor) for c in candidates]
