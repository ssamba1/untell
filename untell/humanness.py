"""Humanness score — a unified 0-100 metric combining AI-tells + detector scores.

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

logger = logging.getLogger(__name__)

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
        Float in [0, 100]. The bands are the ones :func:`classification` actually implements —
        they used to be documented here as 80 / 50-80 / 30-50 / 30, which matched nothing:
        - ≥ 80: human
        - 55–80: mostly human
        - 35–55: mixed
        - 15–35: likely AI
        - < 15: AI
    """
    if not text or not text.strip():
        return 50.0  # Neutral for empty text

    # 1. AI-tells signal
    tells_result = score_tells(text)
    tells_per_100w = tells_result.get("tells_per_100w", 0.0)
    # Normalize to [0, 1] where 0 = no tells (human), 1 = max tells (AI).
    normalized_tells = min(tells_per_100w / _MAX_TELLS_PER_100W, 1.0)

    # 2. Detector ensemble signal.
    #
    # `.get("max", 0.5)` could never fire: score_text ALWAYS returns a "max" key, and when nothing
    # scored that key is a 0.0 PLACEHOLDER — which reads as "no detector thinks this is AI" and,
    # at weight 0.50, lifted the humanness score by fifty points. A broken ML stack therefore
    # reported ordinary AI text as clearly human. score_text sets `scored: False` and a warning
    # for exactly this case; the fix is to read them.
    detector_result = score_text(text, tier=tier)
    detector_scored = detector_result.get("scored") is not False
    detector_max = float(detector_result.get("max", 0.0)) if detector_scored else None
    if not detector_scored:
        logger.warning(
            "no detector produced a score, so the humanness number reflects only the mechanical "
            "signals (tells + burstiness) — treat it as weaker evidence, not a clean verdict."
        )

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

    # 4. Composite. With no detector signal, its weight is REDISTRIBUTED across the signals that
    # did produce something rather than being scored as 0 — dropping a term whose weight is half
    # the total is not the same as that term reporting "human".
    weights = {"tells": _W_TELLS, "detector": _W_DETECTOR, "bursty": _W_BURSTY}
    parts = {"tells": normalized_tells, "bursty": bursty_penalty}
    if detector_max is not None:
        parts["detector"] = detector_max
    live = sum(weights[k] for k in parts) or 1.0
    ai_score = sum(weights[k] * v for k, v in parts.items()) / live
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
