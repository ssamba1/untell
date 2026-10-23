"""The skill path and the hosted-rewriter path must name the same tells (issue #46).

Two vocabularies do the same job. `build_rewrite_prompt` names the categories it advises on from
`prompts._CATEGORY_ADVICE`, and only the Anthropic and OpenAI rewriters call it. The Claude Code
skill never builds that prompt: `SKILL.md` has the running model read `references/ai-tells.md` and
`references/prompt-rubric.md` instead. The free rewriters take no prompt at all.

Checked 2026-10-22, every one of the 25 advised categories is covered by the skill's docs, in their
own prose rather than by identifier. Nothing kept it that way. This repository has been bitten by two
definitions of one thing before (Results 115, 140, 157), so the correspondence is pinned here: a
category added to the prompt with no anchor in the docs, or an anchor deleted from the docs, fails.
"""

from __future__ import annotations

import pathlib

from untell.rewriter.prompts import _CATEGORY_ADVICE

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DOCS = ("untell/references/ai-tells.md", "untell/references/prompt-rubric.md")

# One phrase per category, copied from the skill docs, that a reader of those docs would recognise as
# the same tell the prompt names. Lower-cased; matched as a substring of both docs together.
ANCHORS = {
    "ai_vocab": "delve",
    "aphorism": "aphori",
    "challenges_section": "challenges",
    "chatbot_artifact": "great question",
    "cliche": "cliché",
    "cutoff_disclaimer": "training-cutoff disclaimers",
    "em_dash": "em-dash",
    "false_range": "false-range constructions",
    "filler_phrase": "filler",
    "formulaic_transition": "furthermore",
    "hedge_stacking": "hedge",
    "inflated_copula": "serves as",
    "markdown_artifact": "markdown",
    "meta_closer": "hope this helps",
    "negated_contrast": "it's not",
    "notability_padding": "notab",
    "participial_trailer": "-ing",
    "repeated_phrasing": "repeat",
    "repeated_sentence_openers": "opener",
    "rhetorical_opener": "here's the thing",
    "rule_of_three": "tricolon",
    "semicolon_crutch": "semicolon",
    "steering_opener": "let's",
    "sycophancy": "sycophan",
    "vague_attribution": "weasel",
}


def _skill_text() -> str:
    return "\n".join((ROOT / p).read_text(encoding="utf-8") for p in SKILL_DOCS).lower()


def test_every_category_the_prompt_advises_on_has_an_anchor() -> None:
    """A new category in the prompt needs its counterpart in the skill docs, and an anchor here."""
    assert set(ANCHORS) == set(_CATEGORY_ADVICE), (
        f"prompt-only: {sorted(set(_CATEGORY_ADVICE) - set(ANCHORS))}; "
        f"stale anchors: {sorted(set(ANCHORS) - set(_CATEGORY_ADVICE))}"
    )


def test_the_skill_docs_still_cover_every_category() -> None:
    text = _skill_text()
    missing = {cat: phrase for cat, phrase in ANCHORS.items() if phrase not in text}
    assert not missing, (
        f"the skill docs ({', '.join(SKILL_DOCS)}) no longer describe these tells the prompt names: "
        f"{missing}"
    )


def test_the_skill_does_not_build_the_prompt() -> None:
    """The premise, so the file says something true: SKILL.md drives the docs, not the builder."""
    skill = (ROOT / "untell" / "SKILL.md").read_text(encoding="utf-8")
    assert "build_rewrite_prompt" not in skill
    assert "references/prompt-rubric.md" in skill and "references/ai-tells.md" in skill
