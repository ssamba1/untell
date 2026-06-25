"""Detector protocol + tier-aware registry.

Every detector exposes the same surface:

    name      -> short stable identifier used as a JSON key
    tier      -> one of "lite" | "full" | "heavy"
    available() -> bool   # are this detector's dependencies importable / models loadable?
    score(text) -> float  # P(text is AI-generated), clamped to [0, 1]

The registry (`load_detectors`) returns the *available* detectors for a requested tier,
so a machine with no ML stack transparently degrades to the lite heuristic. Adapters must
keep heavy imports inside `available()`/`score()` — never at module top level — so that
importing this package stays cheap and dependency-free.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

# Tier ordering: a request for "full" also includes "lite" detectors, etc.
Tier = str  # "lite" | "full" | "heavy"
_TIER_RANK = {"lite": 0, "full": 1, "heavy": 2}


def clamp01(x: float) -> float:
    """Clamp a probability into [0, 1] (guards against numerical drift)."""
    if x != x:  # NaN
        return 0.5
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else float(x)


@runtime_checkable
class Detector(Protocol):
    """Structural type every detector adapter satisfies."""

    name: str
    tier: Tier

    def available(self) -> bool:
        """True when this detector can actually score (deps importable, models loadable)."""
        ...

    def score(self, text: str) -> float:
        """Return P(AI-generated) in [0, 1]."""
        ...


def _tier_at_most(detector_tier: Tier, requested: Tier) -> bool:
    return _TIER_RANK.get(detector_tier, 99) <= _TIER_RANK.get(requested, 0)


def all_detectors() -> list[Detector]:
    """Instantiate every known adapter (cheap; no heavy imports happen here)."""
    from .binoculars import BinocularsDetector
    from .fast_detectgpt import FastDetectGPTDetector
    from .mage import MageDetector
    from .perplexity_burstiness import PerplexityBurstinessDetector
    from .roberta_openai import RobertaOpenAIDetector

    return [
        PerplexityBurstinessDetector(),
        RobertaOpenAIDetector(),
        MageDetector(),
        FastDetectGPTDetector(),
        BinocularsDetector(),
    ]


def load_detectors(tier: Tier = "full") -> list[Detector]:
    """Return the available detectors at or below ``tier``.

    Falls back to the lite heuristic if nothing else is installed, so the returned list is
    never empty (the lite detector has no dependencies and is always available).
    """
    selected = [
        d
        for d in all_detectors()
        if _tier_at_most(d.tier, tier) and d.available()
    ]
    return selected


def resolved_tier(detectors: list[Detector]) -> Tier:
    """The effective tier actually running = the highest tier present among `detectors`."""
    if not detectors:
        return "lite"
    return max((d.tier for d in detectors), key=lambda t: _TIER_RANK.get(t, 0))
