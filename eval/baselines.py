"""Rewriters for the benchmark.

The skill uses Claude as the rewriter; for a *headless, measurable* benchmark we need a
deterministic stand-in. These scripted rewriters mimic the rubric's mechanical moves (drop
formulaic transitions, vary word choice, vary sentence length) so we can compare strategies
without a human or an LLM in the seat:

  - ``noop``        — returns the text unchanged (control / baseline detector reading).
  - ``single_pass`` — one blind rewrite at fixed strength (mimics commercial single-pass tools).
  - ``full_loop``   — the closed loop: rewrite, score, escalate strength while still flagged and
                      similarity holds; stop under threshold or at the iteration cap.

The point of the harness is the *comparison*: ``full_loop`` should reach a lower max-proxy /
higher bypass rate than ``single_pass`` at equal-or-better similarity (the report's thesis).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from humanize.scripts.quality import similarity
from humanize.scripts.score import DEFAULT_THRESHOLD, score_text

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

# Formulaic transitions detectors love; strip when sentence-initial.
_TRANSITIONS = re.compile(
    r"^(Moreover|Furthermore|Additionally|Overall|In conclusion|In summary|"
    r"Notably|Importantly|Consequently|Therefore|Thus|Hence),?\s+",
    re.IGNORECASE,
)

# Light synonym swaps to perturb word predictability (perplexity). Deterministic.
_SWAPS = {
    "numerous": "many",
    "significant": "real",
    "significantly": "sharply",
    "fundamentally": "deeply",
    "various": "different",
    "crucial": "key",
    "essential": "needed",
    "represents": "is",
    "enables": "lets",
    "enabled": "let",
    "utilize": "use",
    "utilizing": "using",
    "increasingly": "more and more",
    "tend to": "often",
    "in recent years": "lately",
    "plays a crucial role": "matters",
    "vast amounts of": "huge piles of",
}


def _apply_swaps(text: str) -> str:
    out = text
    for src, dst in _SWAPS.items():
        out = re.sub(rf"\b{re.escape(src)}\b", dst, out, flags=re.IGNORECASE)
    return out


def _vary_lengths(sentences: list[str], strength: float) -> list[str]:
    """Raise sentence-length variance (burstiness): merge some pairs into long sentences and
    split others into short ones, proportional to ``strength``."""
    if len(sentences) < 2:
        return sentences
    out: list[str] = []
    i = 0
    # Merge roughly every other pair as strength rises.
    merge_period = 4 - int(round(2 * strength))  # strength 0 -> every 4th, 1 -> every 2nd
    merge_period = max(2, merge_period)
    while i < len(sentences):
        s = sentences[i].strip()
        if (
            strength > 0
            and i + 1 < len(sentences)
            and i % merge_period == 0
        ):
            nxt = sentences[i + 1].strip().rstrip(".")
            body = s.rstrip(".")
            out.append(f"{body}, and {nxt[0].lower() + nxt[1:] if nxt else nxt}.")
            i += 2
        else:
            out.append(s)
            i += 1
    return out


def rewrite(text: str, strength: float = 0.5) -> str:
    """One deterministic mechanical rewrite at the given ``strength`` in [0, 1]."""
    sentences = [s for s in _SENT_SPLIT.split(text.strip()) if s.strip()]
    # Drop formulaic openers proportional to strength (always at strength >= 0.5).
    cleaned = []
    for idx, s in enumerate(sentences):
        if strength >= 0.5 or idx % 2 == 0:
            s = _TRANSITIONS.sub("", s)
            if s and s[0].islower():
                s = s[0].upper() + s[1:]
        cleaned.append(s)
    varied = _vary_lengths(cleaned, strength)
    joined = " ".join(varied)
    if strength >= 0.34:
        joined = _apply_swaps(joined)
    return joined


@dataclass
class LoopResult:
    text: str
    iterations: int
    pre: dict
    post: dict
    similarity: float
    history: list[float] = field(default_factory=list)


def noop(text: str, **_kw) -> LoopResult:
    s = score_text(text, tier="lite")
    return LoopResult(text=text, iterations=0, pre=s, post=s, similarity=1.0, history=[s["max"]])


def single_pass(text: str, tier: str = "lite", threshold: float = DEFAULT_THRESHOLD, **_kw) -> LoopResult:
    pre = score_text(text, tier=tier, threshold=threshold)
    out = rewrite(text, strength=0.5)
    post = score_text(out, tier=tier, threshold=threshold)
    return LoopResult(
        text=out,
        iterations=1,
        pre=pre,
        post=post,
        similarity=similarity(text, out),
        history=[pre["max"], post["max"]],
    )


def full_loop(
    text: str,
    tier: str = "lite",
    threshold: float = DEFAULT_THRESHOLD,
    sim_bar: float = 0.76,
    max_iters: int = 5,
) -> LoopResult:
    """Closed-loop rewrite: escalate strength while flagged and similarity holds."""
    pre = score_text(text, tier=tier, threshold=threshold)
    best_text = text
    best_score = pre
    history = [pre["max"]]
    iters = 0
    for i in range(1, max_iters + 1):
        iters = i
        # Start at the single-pass strength (0.5), then escalate feedback pressure each round.
        strength = min(1.0, 0.5 + 0.125 * (i - 1))
        candidate = rewrite(text, strength=strength)
        cand_score = score_text(candidate, tier=tier, threshold=threshold)
        cand_sim = similarity(text, candidate)
        history.append(cand_score["max"])
        # Accept the candidate if it lowers the max proxy without breaking the quality gate.
        if cand_sim >= sim_bar and cand_score["max"] <= best_score["max"]:
            best_text, best_score = candidate, cand_score
        if not best_score["flagged"]:
            break
    return LoopResult(
        text=best_text,
        iterations=iters,
        pre=pre,
        post=best_score,
        similarity=similarity(text, best_text),
        history=history,
    )


STRATEGIES = {"noop": noop, "single_pass": single_pass, "full_loop": full_loop}
