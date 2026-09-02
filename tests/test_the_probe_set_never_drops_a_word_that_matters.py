"""The rewriter's biggest untested branch cluster, closed by the invariant it claims.

Round ninety-seven's paired sweep found **206 comparison sites where both mutants survived** — a
branch inversion and an off-by-one both unnoticed, meaning no test reaches the branch at all. They
are not spread evenly. The single largest concentration is **14 in one function**,
`word_importance._tell_probe_words`.

Writing fourteen branch tests would be the obvious response and the wrong one. The function is a
performance optimisation whose forty-line docstring argues a single property:

    "It returns a SUPERSET of every word whose probe could report a positive gain, so skipping the
     rest never changes a ranking decision."

**That claim is checkable, and nothing checked it.** If the probe set ever omits a word whose
substitution really does change the tells count, the ranking silently changes and the only symptom
is a worse rewrite — no error, no failing assertion, no way to notice. The docstring even enumerates
which categories can and cannot matter, which is an argument, not a measurement.

So this tests the property directly: for every word in a document, substitute its first occurrence,
recount the tells, and if the count moved, require the word to be in the probe set. That is one
assertion over a real corpus rather than fourteen assertions over branches, it kills the mutants as
a side effect, and — unlike branch tests — it stays true if the branches are rewritten.

The corpus is chosen to exercise the categories the docstring names: repeated phrasing, duplicated
openers, a short rule-of-three sentence, articles before a substitutable noun, and a heading.
"""

from __future__ import annotations

import pytest

from untell.attacks.word_importance import _tell_probe_words, substitute_once
from untell.scripts.tells import _WORD, score_tells

# Each document targets a category from the docstring's table. Kept small: the invariant is checked
# by substituting EVERY word in turn and re-scoring, so cost is quadratic in document length.
DOCUMENTS = {
    "repeated phrasing": (
        "The model improves the result. The model improves the result again. "
        "The model improves the result once more, and we report it."
    ),
    "duplicated openers": (
        "Moreover the system works. Moreover the system scales. "
        "Moreover the system is fast. Moreover the system is cheap."
    ),
    "rule of three": "We tested it. Cats sleep here. Dogs bark loudly. It works well now.",
    "article before noun": "It is a comprehensive result and an important finding for the field.",
    "heading": "# Key Findings\n\nThe approach delivers a robust and scalable improvement overall.",
    # >= 60 words AND >= 5% of them inside a repeated trigram, which is what makes
    # `trigram_fires` true. The shorter "repeated phrasing" document above does not reach the
    # 60-word floor, so the whole trigram branch — the docstring's "strongest signal in the
    # catalogue" — went unexercised until this was added.
    "firing trigrams": (
        "The model improves the result on every benchmark we ran this year. "
        "The model improves the result even when the data is noisy and sparse. "
        "The model improves the result across all three of the held out domains. "
        "We report these numbers in full below, with intervals, so a reader can check them. "
        "Every figure carries its own interval and the code that produced it is committed here."
    ),
    "plain prose": (
        "The bus never came so I walked, and it passed me two streets later with empty seats."
    ),
}

# A substitution that is a real word, is not a synonym of anything in particular, and is long enough
# to change token counts if the code depends on them.
REPLACEMENT = "zzqx"


def _tells_count(text: str) -> int:
    result = score_tells(text)
    return int(result.get("tells", 0) or 0)


def _words_of(text: str) -> list[str]:
    seen: list[str] = []
    for word in _WORD.findall(text):
        if word not in seen:
            seen.append(word)
    return seen


@pytest.mark.parametrize("label", sorted(DOCUMENTS))
def test_every_word_that_changes_the_count_is_in_the_probe_set(label: str):
    """The docstring's central claim, checked by doing the substitutions it reasons about."""
    text = DOCUMENTS[label]
    raw = _words_of(text)
    syns = {word: [REPLACEMENT] for word in raw}
    probe = _tell_probe_words(text, syns, raw)
    baseline = _tells_count(text)

    missed = []
    for word in raw:
        changed = substitute_once(text, word, REPLACEMENT)
        if changed == text:
            continue  # the substitution did not apply; it cannot have changed anything
        # Membership is checked LOWERCASED, because that is the contract: the caller in
        # `_tell_ranks` does `if word.lower() not in probe_words: continue`, and the set is keyed
        # from `syns_by_word = {w.lower(): ...}`. A first draft compared the raw word and reported
        # "Moreover" as a violation — the probe set holds "moreover" and the code is correct.
        if _tells_count(changed) != baseline and word.lower() not in probe:
            missed.append(word)

    assert not missed, (
        f"{label}: substituting {missed} changes the tells count, and the probe set omits them — "
        f"the ranking those words would have earned is silently lost"
    )


def test_the_check_has_something_to_find():
    """A corpus where no substitution ever moves the count would pass this vacuously."""
    moved = 0
    for text in DOCUMENTS.values():
        baseline = _tells_count(text)
        for word in _words_of(text):
            changed = substitute_once(text, word, REPLACEMENT)
            if changed != text and _tells_count(changed) != baseline:
                moved += 1
    assert moved >= 3, (
        f"only {moved} substitutions across the whole corpus move the tells count; the invariant "
        f"above is close to vacuous and the documents need to exercise more categories"
    )


def test_the_probe_set_is_a_restriction_and_not_everything():
    """A function returning every word satisfies the superset claim and saves nothing.

    The optimisation exists because scoring every word costs hours on a large document. A probe set
    equal to the full vocabulary would pass the invariant above while defeating the purpose, so the
    saving is asserted too.
    """
    text = DOCUMENTS["plain prose"]
    raw = _words_of(text)
    probe = _tell_probe_words(text, {w: [REPLACEMENT] for w in raw}, raw)
    assert probe != set(raw), "on ordinary prose the probe set must be smaller than the vocabulary"


def test_a_word_absent_from_the_normalised_stream_is_kept_unconditionally():
    """One of the docstring's two safety nets, stated as a rule and never exercised.

    The tells tokeniser is `[A-Za-z0-9']+`, so an apostrophe form like `don't` IS a single
    normalised token and is not covered by this net — a first draft asserted it was. A hyphenated
    compound splits into two tokens and therefore is.
    """
    text = "The result is well-founded and precise in the report we published today."
    raw = _words_of(text) + ["well-founded"]
    probe = _tell_probe_words(text, {w: [REPLACEMENT] for w in raw}, raw)
    assert "well-founded" in probe, "a hyphenated compound is not a normalised token"
    assert "don't" not in _tell_probe_words(
        "we don't agree with the result in the report we published today.",
        {"don't": [REPLACEMENT]}, ["don't"],
    ), "an apostrophe form IS a normalised token; the net does not apply to it"


def test_the_quant_frame_keys_are_kept_whenever_present():
    """The other safety net: their substitution rewrites a three-token frame at once."""
    text = "We found a myriad of results and a plethora of confirmations in the data today."
    raw = _words_of(text)
    probe = _tell_probe_words(text, {w: [REPLACEMENT] for w in raw}, raw)
    assert "myriad" in probe
    assert "plethora" in probe
