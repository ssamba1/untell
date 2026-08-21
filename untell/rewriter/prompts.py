"""Prompt construction for the hosted-LLM rewriter.

Turns a detector score result into a concrete, feedback-driven rewrite instruction following the
same rubric the skill uses (references/prompt-rubric.md + references/ai-tells.md): write plain,
naturally uneven human prose, inject NONE of the known AI tells, preserve meaning and every sentinel.

Named-signal rubric (build_rewrite_prompt):
The prompt now names the SPECIFIC tell categories detected in THIS document, derived from a live
``score_tells`` call on the text, rather than repeating a generic list of everything the catalogue
covers.  A document heavy in clichés gets a cliché-focused instruction; one heavy in repeated openers
gets that.  Categories that did not fire are not mentioned, so the model does not anchor on signals
that are not a problem for this text.

The caller may also pre-supply tells via ``score_result["by_category"]``.  When present, that dict is
used instead of re-running ``score_tells`` — handy if the loop already has it from the tie-break step.
``score_result`` without ``by_category`` triggers a fresh computation; exceptions inside it are caught
so a scoring failure never silences the whole prompt.
"""

from __future__ import annotations

_SENTINEL_NOTE = (
    "The text may contain opaque sentinels like ⟦HZ0003⟧. Carry every sentinel through UNCHANGED — "
    "never modify, translate, split, reorder the characters of, or drop one."
)

# The voices `--style` accepts, and the only place the ACCEPTED LIST is written down: `run.py`
# builds its argparse choices from this name, the REST field is built from it, and the MCP docstring
# reads it rather than restating it.
#
# It is not the only place the vocabulary appears. `structural._STYLE_PROFILES` is keyed by the same
# fourteen names and is an independent literal — a name here with no profile there is accepted by
# every surface and silently rewrites with the neutral profile, and a profile there with no name
# here is a style nobody can select. Both directions are asserted in
# `tests/test_the_result_names_the_style_that_ran.py`; the comment used to claim there was only one
# copy, which is the kind of statement nobody re-checks (see Result 189).
#
# It used to live inside build_rewrite_prompt() as a function-local dict, with the names duplicated
# by hand in run.py's argparse choices and again in the MCP tool docstring. The MCP copy had drifted
# to six entries out of fourteen — and that docstring is what an MCP client reads to learn the valid
# values, so eight of the styles were invisible to every MCP caller. Module-level, so the other two
# derive from it instead of restating it.
STYLES: dict[str, str] = {
    "casual": "Write casually — contractions, everyday words, a relaxed conversational voice.",
    "professional": "Write in a clear professional voice — direct, polished, no fluff.",
    "academic": "Keep an academic register — precise, measured, but not formulaic.",
    "blunt": "Be blunt and plain-spoken — short declaratives, no hedging.",
    "storytelling": "Use a narrative, storytelling voice — concrete scenes, a human throughline.",
    "journalistic": "Write like a journalist — lead with the point, concrete and specific.",
    "technical": "Write with technical precision — specific jargon is fine, keep it concise and factual.",
    "persuasive": "Write persuasively — confident claims, clear reasoning, a compelling through-line.",
    "empathetic": "Write with warmth and empathy — show you understand the reader's perspective.",
    "humorous": "Write with light humour — conversational, playful, natural asides.",
    "poetic": "Write with a lyrical, evocative quality — vivid imagery, rhythm, sensory language.",
    "instructional": "Write as a clear instructor — step by step, direct, no ambiguity.",
    "conversational": "Write like you're talking to a friend — natural back-and-forth rhythm, contractions.",
    "minimalist": "Write minimally — short sentences, only essential words, maximum signal.",
}

STYLE_NAMES: list[str] = list(STYLES)

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


# Per-category advice for the named-signal section of the rewrite prompt.
#
# Each entry maps the ``score_tells`` category key to a ONE-LINE instruction that is concrete enough
# for a rewriter to act on immediately.  Ordering matters: the rubric lists them from most-actionable
# to least, so the model reads the most important one first even if only one fires.
#
# Why NOT a generic list?  The current _RUBRIC already names the canonical tells so the model has the
# full context.  The named-signal block below is the TARGETED layer — it names only what THIS document
# actually contains, so the model's attention is directed at real defects rather than diffused across
# the whole catalogue.
_CATEGORY_ADVICE: dict[str, str] = {
    "cliche": (
        "clichés in this text (e.g. 'in today's fast-paced world', 'at its core', 'game-changer', "
        "'paradigm shift', 'dive into', 'shed light on') — cut or rephrase as a plain, specific statement"
    ),
    "formulaic_transition": (
        "formulaic sentence-opening transitions (e.g. 'Moreover', 'Furthermore', 'Additionally', "
        "'Overall', 'Ultimately', 'Thus', 'Therefore') — replace with a plain 'but', 'and', 'so', "
        "'though', or nothing; start with the actual point"
    ),
    "repeated_phrasing": (
        "repeated phrases — the same word-cluster appears several times; vary the wording, "
        "use pronouns, or cut a repetition"
    ),
    "repeated_sentence_openers": (
        "repeated sentence starters — multiple sentences open with the same word; "
        "vary how sentences begin"
    ),
    "ai_vocab": (
        "AI vocabulary in this text (e.g. 'delve', 'leverage', 'utilize', 'robust', 'seamless', "
        "'tapestry', 'testament', 'realm', 'landscape', 'pivotal', 'underscore', 'foster', "
        "'harness', 'multifaceted', 'meticulous', 'nuanced') — use a plain, specific word instead"
    ),
    "participial_trailer": (
        "participial-phrase trailers (, underscoring …, marking …, highlighting …, showcasing …) "
        "— cut the trailing clause or restate it as a separate sentence"
    ),
    "hedge_stacking": (
        "stacked hedges ('could potentially', 'may eventually', 'might possibly') "
        "— keep one hedge or drop it"
    ),
    "vague_attribution": (
        "vague attribution ('studies show', 'research suggests', 'experts argue') "
        "— name the actual source or cut the claim"
    ),
    "negated_contrast": (
        "negated-contrast constructions ('not just X, it's Y'; 'not only X but also Y') "
        "— state the positive claim directly"
    ),
    "sycophancy": (
        "sycophantic openers ('Certainly!', 'Absolutely!', 'Great question!') — cut them entirely"
    ),
    "meta_closer": (
        "chatbot sign-off phrases ('I hope this helps', 'Let me know if', 'Feel free to reach out') "
        "— cut; end on the actual content"
    ),
    "chatbot_artifact": (
        "chatbot artefacts ('As an AI language model', '[INSERT …]') — remove entirely"
    ),
    "inflated_copula": (
        "inflated copulas ('serves as', 'boasts', 'epitomizes') — use 'is' or 'has' instead"
    ),
    "em_dash": (
        "em-dashes (—) used for rhythm — replace with a comma, period, or short separate clause"
    ),
    "semicolon_crutch": (
        "semicolons used as a rhythm crutch — split into two sentences or use a comma"
    ),
    "filler_phrase": (
        "filler phrases ('due to the fact that', 'at this point in time', 'needless to say') "
        "— cut or rephrase directly"
    ),
    "aphorism": (
        "aphorism formulas ('X is the new Y', 'X is the backbone of Y') "
        "— state the idea plainly without the metaphor"
    ),
    "false_range": (
        "false-range breadth ('from X to Y', 'whether you're X or Y') "
        "— be specific or cut the sweep"
    ),
    "rule_of_three": (
        "staccato rule-of-three ('Fast. Simple. Effective.') "
        "— merge into a normal sentence or paragraph"
    ),
    "steering_opener": (
        "reader-steering adverbs at sentence start ('Interestingly,', 'Notably,', 'Importantly,') "
        "— cut the adverb and start with the claim"
    ),
    "rhetorical_opener": (
        "theatrical openers ('Honestly?', 'Look,', 'Here's the thing') "
        "— start with the actual point"
    ),
    "markdown_artifact": (
        "markdown artefacts (Key Takeaways:, TL;DR, emoji section headers) — remove"
    ),
    "cutoff_disclaimer": (
        "knowledge-cutoff disclaimers ('as of my last training', 'limited information is available') "
        "— cut, or state the gap as a plain fact about the subject"
    ),
    "challenges_section": (
        "generic challenges-section framing ('faces several challenges', 'future prospects') "
        "— be specific about what the challenge is"
    ),
    "notability_padding": (
        "notability padding ('has been widely covered', 'cited by multiple major outlets') "
        "— cut, or cite a specific real source"
    ),
}

# Maximum number of detected tell categories to name in the prompt. Beyond this the list becomes
# noise — a rewriter told about fifteen things at once is not better guided than one told about
# three. Cap keeps the prompt proportionate to the actual worst offenders.
_MAX_NAMED_SIGNALS = 5


def _detected_signals(text: str, score_result: dict) -> list[tuple[str, int]]:
    """Return tell categories detected in ``text``, sorted by count descending.

    Prefers ``score_result["by_category"]`` when present — the loop already computed tells for the
    tie-break, so we avoid a second pass.  Falls back to a fresh ``score_tells`` call.  Exceptions
    are swallowed so a scoring failure never silences the whole prompt.

    Returns a list of (category, count) pairs, highest-count first, capped at _MAX_NAMED_SIGNALS.
    Only categories present in ``_CATEGORY_ADVICE`` (i.e. actionable) are returned.
    """
    by_category: dict[str, int] = {}

    if "by_category" in score_result:
        by_category = score_result["by_category"] or {}
    else:
        try:
            from untell.scripts.tells import score_tells

            by_category = score_tells(text).get("by_category") or {}
        except Exception:
            pass  # a diagnostic must never break the prompt it describes

    actionable = [
        (name, count)
        for name, count in by_category.items()
        if name in _CATEGORY_ADVICE and isinstance(count, int) and count > 0
    ]
    actionable.sort(key=lambda kv: kv[1], reverse=True)
    return actionable[:_MAX_NAMED_SIGNALS]


def _worst_detectors(score_result: dict, k: int = 3) -> list[tuple[str, float]]:
    dets = score_result.get("detectors", {})
    numeric = [(n, v) for n, v in dets.items() if isinstance(v, (int, float)) and "__error" not in n]
    return sorted(numeric, key=lambda kv: kv[1], reverse=True)[:k]


def build_rewrite_prompt(text: str, score_result: dict, threshold: float = 0.30) -> str:
    """Build the rewrite instruction, naming the detectors + the exact sentences flagging the text.

    Named-signal section: derives the tell categories actually present in ``text`` (via
    ``_detected_signals``) and appends a bullet per detected category with a concrete action.
    A document heavy in clichés gets a cliché-focused instruction; one heavy in repeated openers
    gets that.  Categories that did not fire are not mentioned.
    """
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
    if style and style in STYLES:
        feedback += f"\n\nVoice: {STYLES[style]}"

    flagged_sentences = score_result.get("flagged_sentences") or []
    if flagged_sentences:
        listed = "\n".join(f"  - {s}" for s in flagged_sentences[:8])
        feedback += (
            "\n\nThese specific sentences read most as AI — REWRITE THESE the hardest into plain, "
            "uneven, natural prose; break any neat parallelism, tricolons, or aphorisms (do not add "
            f"facts the source didn't state):\n{listed}"
        )

    # Named-signal section: list ONLY the tell categories that actually fired in this text.
    # Derived from a live score_tells pass (or from score_result["by_category"] if pre-supplied).
    signals = _detected_signals(text, score_result)
    if signals:
        lines = "\n".join(
            f"  - {_CATEGORY_ADVICE[name]} (found {count} time{'s' if count != 1 else ''})"
            for name, count in signals
        )
        feedback += (
            "\n\nThis specific text contains these AI signals — address each:\n" + lines
        )

    return f"{_RUBRIC}\n\n{feedback}\n\n--- TEXT ---\n{text}"
