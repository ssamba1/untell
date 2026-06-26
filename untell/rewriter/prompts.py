"""Prompt construction for the hosted-LLM rewriter.

Turns a detector score result into a concrete, feedback-driven rewrite instruction following the
same rubric the skill uses (references/prompt-rubric.md + references/ai-tells.md): write plain,
naturally uneven human prose, inject NONE of the known AI tells, preserve meaning and every sentinel.
"""

from __future__ import annotations

_SENTINEL_NOTE = (
    "The text may contain opaque sentinels like ⟦HZ0003⟧. Carry every sentinel through UNCHANGED — "
    "never modify, translate, split, reorder the characters of, or drop one."
)

_RUBRIC = (
    "Rewrite the text so it reads like an actual, slightly-careless person wrote it, while keeping "
    "its exact meaning, every fact, and every sentinel.\n"
    "Write naturally uneven prose: mostly plain short sentences, the occasional longer one a person "
    "wouldn't bother to trim. Do NOT engineer sentence-length variation or reach for fancier words to "
    "move a score — manufactured burstiness and thesaurus swaps are themselves AI tells.\n"
    "Introduce NONE of these AI tells (add none that were not already in the text):\n"
    "- em-dashes (—), or semicolons used for rhythm;\n"
    "- formulaic transitions (Moreover, Furthermore, Additionally, However, Notably, Overall, "
    "Ultimately, In conclusion) — use plain but/and/so/though, or nothing;\n"
    "- AI vocabulary (delve, leverage, utilize, robust, seamless, tapestry, testament, realm, "
    "landscape, pivotal, underscore, foster, harness, multifaceted, meticulous, nuanced) — plain word;\n"
    "- tricolons / rule-of-three, negated contrast (\"not X, it's Y\"; \"not only X but also Y\"), "
    "participial trailers that restate the sentence (\"…, underscoring its importance\");\n"
    "- inflated copula (serves as, marks, boasts, represents) for plain is/has; significance "
    "inflation; aphoristic closers; vague attribution (\"studies show\"); chatbot preambles/sign-offs.\n"
    "Match the source's format, register, and language exactly — add no headings, bullets, bold, or "
    "emoji it did not have. If a plainer phrasing reads more human but scores marginally higher, pick "
    "the plainer phrasing.\n"
    "Keep all facts, numbers, citations, and named entities intact.\n"
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
            f"{flagged}. Rewrite the flagged spans to read like plain, natural human prose — not by "
            "gaming any score. Do not add em-dashes, fancier words, or staccato fragments to chase the "
            "number; plainer and more ordinary is more human."
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
            "\n\nThese specific sentences read most as AI — REWRITE THESE the hardest into plain, "
            "uneven, natural prose; break any neat parallelism, tricolons, or aphorisms (do not add "
            f"facts the source didn't state):\n{listed}"
        )

    return f"{_RUBRIC}\n\n{feedback}\n\n--- TEXT ---\n{text}"
