"""Humanness score — a unified 0-100 metric combininig AI-tells + detector scores.

A single number that answers "how human does this text read?" by fusing:

* **AI-tells density** (from ``score_tells``) — mechanical markers per 100 words.
* **Detector ensemble max** (from ``score_text``) — the hardest detector's P(AI).
* **Burstiness** — sentence-length coefficient of variation.

The formula::

    humanness = 100 - (w_tells * normalized_tells + w_detector * detector_max + w_bursty * bursty_penalty)

Where weights are calibrated so that clearly-human text scores ≥ 80 and
clearly-AI text scores ≤ 30.

Usage::

    from untell.humanness import humanness

    score = humanness("Your text here")  # e.g. 73
    print(f"Humanness: {score}/100")
"""

from __future__ import annotations

import logging

from untell.scripts.score import score_text
from untell.scripts.tells import score_tells

# Weights for the three signal components (sum ≈ 1.0).
_W_TELLS = 0.30       # AI-tells density contribution
_W_DETECTOR = 0.50    # Detector ensemble contribution (strongest weight)
_W_BURSTY = 0.20      # Burstiness / sentence-length variation

# Calibration constants.
_MAX_TELLS_PER_100W = 25.0  # Approximate ceiling for tells/100w
_BURSTY_IDEAL = 0.70        # Ideal burstiness CV (high variation = human)
_MAX_BURSTY_PENALTY = 0.30  # Max penalty from low burstiness


def humanness(text: str, tier: str = "full") -> float:
    """Return a humanness score in [0, 100] — higher = more human-like.

    Args:
        text: The text to evaluate.
        tier: Detector tier to use (default ``"full"``).

    Returns:
        Float in [0, 100]. Scores:
        - ≥ 80: clearly human-written
        - 50–80: mixed / plausible human
        - 30–50: likely AI-written
        - ≤ 30: clearly AI-generated
    """
    if not text or not text.strip():
        return 50.0  # Neutral for empty text

    # 1. AI-tells signal
    tells_result = score_tells(text)
    tells_per_100w = tells_result.get("tells_per_100w", 0.0)
    # Normalize to [0, 1] where 0 = no tells (human), 1 = max tells (AI).
    normalized_tells = min(tells_per_100w / _MAX_TELLS_PER_100W, 1.0)

    # 2. Detector ensemble signal
    detector_result = score_text(text, tier=tier)
    detector_max = detector_result.get("max", 0.5)  # P(AI) in [0, 1]

    # 3. Burstiness signal
    cv = tells_result.get("burstiness_cv")
    bursty_penalty = 0.0
    if cv is not None:
        # CV near 0.7 is ideal human prose; penalize both low (uniform) and
        # extremely high (erratic) burstiness, but low is the real tell.
        if cv < 0.35:
            bursty_penalty = _MAX_BURSTY_PENALTY  # uniform=AI tell
        elif cv < 0.50:
            bursty_penalty = _MAX_BURSTY_PENALTY * (0.50 - cv) / 0.15
        elif cv > 1.0:
            bursty_penalty = _MAX_BURSTY_PENALTY * 0.5  # erratic, but less penalized

    # 4. Composite
    ai_score = (
        _W_TELLS * normalized_tells
        + _W_DETECTOR * detector_max
        + _W_BURSTY * bursty_penalty
    )
    # Clamp to [0, 1] then scale to [0, 100].
    human_score = max(0.0, min(1.0, 1.0 - ai_score))
    return round(human_score * 100.0, 1)


def classification(score: float) -> str:
    """Return a human-readable classification for a humanness score."""
    if score >= 80:
        return "human"
    if score >= 55:
        return "mostly human"
    if score >= 35:
        return "mixed"
    if score >= 15:
        return "likely AI"
    return "AI"


def main(argv: list[str] | None = None) -> int:
    """CLI: ``untell humanness \"text\"`` → JSON with humanness score and classification."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    import argparse
    import json
    import sys

    from untell.scripts.io_utils import configure_utf8_io

    configure_utf8_io()
    parser = argparse.ArgumentParser(
        prog="untell-humanness",
        description="Score text 0-100: how human does it read? (combines tells + detectors)",
    )
    parser.add_argument("text", nargs="?", help="text to score")
    parser.add_argument("--file", "-f", help="read text from this file")
    parser.add_argument("--tier", default="full", choices=["lite", "full", "heavy"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.file:
        with open(args.file, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    elif args.text:
        text = args.text
    else:
        text = sys.stdin.read()
    if not text.strip():
        print(json.dumps({"error": "empty input"}))
        return 2

    score = humanness(text, tier=args.tier)
    cls = classification(score)
    result = {"score": score, "classification": cls}
    if args.json:
        print(json.dumps(result, ensure_ascii=True))
    else:
        print(f"Humanness: {score}/100  ({cls})")
    return 0
