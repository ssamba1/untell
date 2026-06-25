"""Prompt construction for the hosted-LLM rewriter.

Turns a detector score result into a concrete, feedback-driven rewrite instruction following the
same rubric the skill uses (references/prompt-rubric.md): raise burstiness + perplexity, vary
sentence architecture, drop formulaic transitions, preserve meaning and every sentinel.
"""

from __future__ import annotations

_SENTINEL_NOTE = (
    "The text may contain opaque sentinels like ⟦HZ0003⟧. Carry every sentinel through UNCHANGED — "
    "never modify, translate, split, reorder the characters of, or drop one."
)

_RUBRIC = (
    "Rewrite the text so it reads as natural human writing while preserving its exact meaning:\n"
    "- Vary sentence length aggressively (mix very short sentences with long, winding ones) to "
    "raise burstiness.\n"
    "- Replace predictable, formulaic phrasing with less expected, more specific word choices to "
    "raise perplexity.\n"
    "- Remove formulaic transitions (\"Moreover\", \"Furthermore\", \"Additionally\", \"Overall\", "
    "\"In conclusion\").\n"
    "- Vary sentence openings; avoid uniform structure.\n"
    "- Keep all facts, numbers, citations, and named entities intact.\n"
    f"- {_SENTINEL_NOTE}\n"
    "Return ONLY the rewritten text, with no preamble, commentary, or quotes."
)


def _worst_detectors(score_result: dict, k: int = 3) -> list[tuple[str, float]]:
    dets = score_result.get("detectors", {})
    numeric = [(n, v) for n, v in dets.items() if isinstance(v, (int, float)) and "__error" not in n]
    return sorted(numeric, key=lambda kv: kv[1], reverse=True)[:k]


def build_rewrite_prompt(text: str, score_result: dict, threshold: float = 0.30) -> str:
    """Build the rewrite instruction, naming the detectors + the exact sentences flagging the text."""
    worst = _worst_detectors(score_result)
    if worst:
        flagged = ", ".join(f"{name} (P(AI)={val:.2f})" for name, val in worst)
        feedback = (
            f"These local detectors still flag the text as AI-generated (target < {threshold:.2f}): "
            f"{flagged}. Focus your changes on the signals they measure — especially sentence-length "
            "variance (burstiness) and word predictability (perplexity)."
        )
    else:
        feedback = f"Lower the AI-detection probability below {threshold:.2f}."

    style = score_result.get("style")
    _STYLES = {
        "casual": "Write casually — contractions, everyday words, a relaxed conversational voice.",
        "professional": "Write in a clear professional voice — direct, polished, no fluff.",
        "academic": "Keep an academic register — precise, measured, but not formulaic.",
        "blunt": "Be blunt and plain-spoken — short declaratives, no hedging.",
        "storytelling": "Use a narrative, storytelling voice — concrete scenes, a human throughline.",
        "journalistic": "Write like a journalist — lead with the point, concrete and specific.",
    }
    if style and style in _STYLES:
        feedback += f"\n\nVoice: {_STYLES[style]}"

    flagged_sentences = score_result.get("flagged_sentences") or []
    if flagged_sentences:
        listed = "\n".join(f"  - {s}" for s in flagged_sentences[:8])
        feedback += (
            "\n\nThese specific sentences read most as AI — REWRITE THESE the hardest (vary their "
            f"structure, break neat parallelism/aphorisms, add concrete specifics):\n{listed}"
        )

    return f"{_RUBRIC}\n\n{feedback}\n\n--- TEXT ---\n{text}"
