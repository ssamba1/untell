"""The rewriter must not damage the text mechanically, and nothing was checking.

Every other suite in this repo asks whether the output evades a detector or preserves meaning.
None of them asks whether it is *well-formed English*, and `score_tells` cannot: a sentence
fragment, an unbalanced quotation and a dangling coordinator are all perfectly clean to a tell
catalogue. Six real defects were found in one session by reading rewritten corpus text by hand:

    "There are other options for melting ice on roads. Such as using chemicals ..."
    "In this paper, we show EdgeFlow. A new way to interactive segmentation ..."
    "... in combination with other techniques, but. Salt is often the most effective ..."
    'He said "the result is robust.' / 'It replicates", which the reviewers accepted.'
    "The authors, Smith, Jones, and Patel." / "Reported that the effect held ..."
    "Because the encoder is small it runs fast, the model works well and."

This file turns that reading into a battery. Every check is scored on the OUTPUT and on the
SOURCE, and only a positive delta is a failure — the corpora contain their own artefacts and the
rewriter must not be blamed for those.

Deliberately corpus-free: the fixtures are constructed to carry the shapes that broke, so the
battery runs in CI with no download. The corpus version lives in the session scratchpad and is
what produced the numbers quoted above.
"""

from __future__ import annotations

import random
import re

import pytest

from untell.rewriter.structural import structural_rewrite
from untell.text_split import split_sentences

# Each check is (name, pattern). A match is damage.
_CHECKS: dict[str, re.Pattern[str]] = {
    "double_space": re.compile(r"[^\s]  +[^\s]"),
    "space_before_punctuation": re.compile(r"\s+[,.;:!?]"),
    "doubled_punctuation": re.compile(r"[,.;:]{2,}|\.\s*\."),
    "comma_then_period": re.compile(r",\s*\."),
    "empty_parentheses": re.compile(r"\(\s*\)"),
    "lowercase_after_full_stop": re.compile(r"[.!?]\s+[a-z]"),
    "doubled_word": re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE),
    "a_before_vowel": re.compile(r"\ba\s+[aeiouAEIOU]\w"),
    "an_before_consonant": re.compile(r"\ban\s+[bcdfgjklmnpqrstvwxyz]\w", re.IGNORECASE),
    "dangling_coordinator": re.compile(r"\b(and|but|or|so|because|while|which)\s*[.!?]"),
    "doubled_particle": re.compile(r"\b(to|of|in|on|for|with|through)\s+\1\b", re.IGNORECASE),
}

# Leads that cannot open an independent clause, so a sentence starting with one is a fragment.
# Openers the rewriter legitimately prepends are stripped before judging — "Of course, in this
# paper." must be blamed on the fragment, not on the opener, and an early version of this battery
# counted every "Of course," as damage for exactly that reason.
_OUR_OPENERS = (
    "actually", "in practice", "in short", "put simply",
    "also", "now", "basically", "well", "of course",
)
_FRAGMENT_LEADS = {"such", "which", "who", "whom", "including", "of", "as", "than", "can"}

# Paragraphs carrying every shape that has broken: exemplifier and appositive commas, a serial
# list, a quotation containing a coordinator, a trailing subordinate clause, a proper noun that
# must not be lowercased, an abbreviation, and a number with a comma in it.
_FIXTURES = [
    "There are other options for melting ice and snow on roads, such as using chemicals like"
    " calcium chloride or magnesium chloride, or using mechanical methods like plows and sand."
    " However, salt is often the most effective and affordable option for most municipalities."
    " The ice melts on the road surface because salt lowers the freezing point of the water.",

    "In this paper, we present EdgeFlow, a novel approach to interactive image segmentation that"
    " leverages edge-guided flow to reach practical accuracy on a tight annotation budget."
    " Existing methods are often limited by their heavy reliance on repeated iterative user"
    " input, which can be extremely time-consuming for a working analyst in the field."
    " Moreover, the authors, Smith, Jones, and Patel, reported that the effect held at every site.",

    'He said "the result is robust, and it replicates", which the reviewers accepted without'
    " further argument. The study enrolled 3,000 participants across twelve separate sites, and"
    " the follow-up ran for two full years afterwards. Revenue rose in Q1, Q2, and Q3, but the"
    " fourth quarter fell short of the target by a considerable margin overall.",

    "NASA confirmed the result because the second probe returned matching data from orbit."
    " Dr. Smith published the findings in a journal that is read widely across the discipline."
    " The system leverages robust methodologies to optimize operational efficiency, and it is"
    " crucial to underscore the pivotal role of comprehensive frameworks in this domain.",
]


def _strip_our_opener(sentence: str) -> str:
    low = sentence.strip()
    for opener in _OUR_OPENERS:
        if low.lower().startswith(opener + ","):
            return low[len(opener) + 1:].strip()
    return low


def _damage(text: str) -> dict[str, int]:
    found = {name: len(pat.findall(text)) for name, pat in _CHECKS.items()}
    fragments = 0
    for sentence in split_sentences(text):
        body = _strip_our_opener(sentence)
        words = body.split()
        if not words:
            continue
        if words[0].rstrip(",.;:").lower() in _FRAGMENT_LEADS:
            fragments += 1
    found["fragment_lead"] = fragments
    found["unbalanced_quotes"] = 1 if text.count('"') % 2 else 0
    # A sentence under four words is a stranded opener or a list item, not a sentence. Counted
    # here rather than only in the corpus sweep, where it is the one check still showing a
    # positive delta (+1 across 60 texts, down from +4). The fixtures below must not add any.
    found["stub_sentence"] = sum(
        1 for s in split_sentences(text) if 0 < len(_strip_our_opener(s).split()) < 4
    )
    return found


@pytest.mark.parametrize("source", _FIXTURES)
@pytest.mark.parametrize("intensity", [0.5, 1.0])
def test_the_rewriter_introduces_no_mechanical_damage(source, intensity):
    """Scored against the SOURCE, so an artefact already in the input is not a failure."""
    baseline = _damage(source)
    for seed in range(25):
        random.seed(seed)
        out = structural_rewrite(source, intensity=intensity)
        after = _damage(out)
        worse = {k: (baseline[k], after[k]) for k in after if after[k] > baseline[k]}
        assert not worse, (
            f"seed {seed}, intensity {intensity}: {worse}\n--- source ---\n{source}\n"
            f"--- output ---\n{out}"
        )


@pytest.mark.parametrize("source", _FIXTURES)
def test_the_rewriter_actually_changes_these_fixtures(source):
    """Anti-vacuity. A rewriter that returned its input unchanged would pass every check above,
    and "too conservative to do anything" is a failure mode this pipeline has hit five times."""
    changed = False
    for seed in range(25):
        random.seed(seed)
        if structural_rewrite(source, intensity=1.0).strip() != source.strip():
            changed = True
            break
    assert changed, "the rewriter left the fixture untouched, so the battery proves nothing"


def test_every_check_can_actually_fire():
    """A pattern that matches nothing is dead coverage that looks alive — this repo has shipped
    six of those before (`\\b` written into a non-raw string became U+0008)."""
    probes = {
        "double_space": "the  cat sat",
        "space_before_punctuation": "the cat , sat",
        "doubled_punctuation": "the cat sat,, and",
        "comma_then_period": "the cat sat, .",
        "empty_parentheses": "the cat () sat",
        "lowercase_after_full_stop": "The cat sat. the dog",
        "doubled_word": "the the cat",
        "a_before_vowel": "a apple",
        "an_before_consonant": "an cat",
        "dangling_coordinator": "the cat sat and.",
        "doubled_particle": "walk to to the shop",
    }
    assert set(probes) == set(_CHECKS), "a check has no probe, or a probe has no check"
    for name, probe in probes.items():
        assert _CHECKS[name].search(probe), f"{name} cannot match its own example"
