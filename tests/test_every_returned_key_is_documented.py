"""`post` carried two fields that appeared in no document anywhere.

FOUND by asking the question Result 173 raised in general form: a change reaches the places that
argue about it and misses the places that merely state it. So does every key the code actually
returns appear in the document that lists them?

MEASURED against the "Full key lists" block of `docs/result-shapes.md`, on real payloads:

    score_text        emitted-not-listed  []
    score_tells       emitted-not-listed  []
    score_sentences   emitted-not-listed  []
    untell_text       emitted-not-listed  []      <- at the top level

At the top level, nothing. The four entries that appear listed-but-not-emitted — `unrankable`,
`warning`, `failed_detectors`, `detector_errors` — are all documented as conditional, so their
absence on ordinary input is the contract working.

The gap was one level down. `untell_text` returns `pre` and `post`, and a reader has every reason to
take both for `score_text` payloads. `pre` is exactly that. `post` is not:

    extra in pre :  []
    extra in post:  ['flagged_sentences', 'style']

`run.py` merges them in when it settles on the winning draft. `flagged_sentences` is the per-sentence
flag list for the text actually returned — the most useful thing in the payload for deciding what to
edit next — and `style` records which profile ran, without which the rest of the result cannot be
interpreted. Neither appeared in `result-shapes.md`, `SKILL.md` or any reference document. This
repository has shipped exactly this before with `unrankable`.

**Two probe errors on the way, both of the kind that manufactures a finding.** Reading the document
for backticked names reported 19 of 28 fields undocumented; the key lists are a fenced block of
comma-separated names with no backticks at all. Adding a JSON-key pattern found zero, because there
is no JSON in the file either. The number only became real once the block itself was parsed.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest

from untell.scripts.run import untell_text
from untell.scripts.score import score_text
from untell.scripts.sentences import score_sentences
from untell.scripts.tells import score_tells

DOC = Path(__file__).resolve().parents[1] / "docs" / "result-shapes.md"
TEXT = (
    "Moreover, the framework leverages a robust approach to delivery at scale. "
    "Furthermore, it is important to note that this underscores the pivotal integration "
    "for every team involved in the programme this year."
)
FUNCTIONS = ("score_text", "score_tells", "score_sentences", "untell_text", "verify")
# Prose inside the block — "only when a detector raised", "(only when a caveat applies)" — is
# grammar, not field names.
#
# Every word here must be one that is NOT a field name. `final` was in the first version of this
# set, to absorb the phrase "for the FINAL text" — and `final` is the key holding the rewritten
# document, so the check reported the payload's most important field as undocumented. The block is
# now key lists only, with the explanation outside it, and the set stays this small.
_PROSE = {
    "only", "when", "and", "the", "detector", "raised", "caveat", "applies", "per",
    "sentence", "scores", "cannot", "be", "ranked", "above", "for", "input", "plus",
}


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.fixture(scope="module")
def documented() -> dict[str, set[str]]:
    block = re.search(r"## Full key lists\s*```(.*?)```", DOC.read_text(encoding="utf-8"), re.S)
    assert block, "result-shapes.md has no `Full key lists` block"
    listed: dict[str, set[str]] = {}
    current: str | None = None
    for line in block.group(1).splitlines():
        head = re.match(r"^(\w+)\s+(.*)$", line.strip())
        if head and head.group(1) in FUNCTIONS:
            current = head.group(1)
            listed.setdefault(current, set())
            rest = head.group(2)
        elif current:
            rest = line.strip()
        else:
            continue
        for key in re.findall(r"[a-z_][a-z0-9_]{2,30}", rest):
            if key not in _PROSE and key not in FUNCTIONS:
                listed[current].add(key)
    return listed


@pytest.fixture(scope="module")
def payloads() -> dict[str, dict]:
    return {
        "score_text": score_text(TEXT, tier="lite"),
        "score_tells": score_tells(TEXT),
        "score_sentences": score_sentences(TEXT, tier="lite"),
        "untell_text": untell_text(
            TEXT, tier="lite", threshold=0.3, max_iters=1, rewriter="structural",
            best_of=1, seed=1,
        ),
    }


def test_the_document_still_lists_every_function(documented) -> None:
    """Premise. If the block were renamed or emptied every assertion below would pass on nothing."""
    for fn in FUNCTIONS:
        assert documented.get(fn), f"{fn} has no key list"


@pytest.mark.parametrize("fn", ["score_text", "score_tells", "score_sentences", "untell_text"])
def test_no_returned_key_is_undocumented(fn: str, documented, payloads) -> None:
    """The direction that matters to a caller: a key they can read must be a key they can look up.

    The reverse — documented but absent — is the contract working, since several fields are
    explicitly conditional.
    """
    extra = sorted(set(payloads[fn]) - documented[fn])
    assert not extra, f"{fn} returns undocumented keys: {extra}"


def test_the_nested_score_payloads_are_documented_too(documented, payloads) -> None:
    """Where the real gap was. `pre` and `post` look like the same shape and are not."""
    result = payloads["untell_text"]
    allowed = documented["score_text"] | documented["untell_text"]
    for name in ("pre", "post"):
        extra = sorted(set(result[name]) - allowed)
        assert not extra, f"untell_text.{name} carries undocumented keys: {extra}"


def test_post_really_does_differ_from_pre() -> None:
    """Guards the guard. If `post` ever became a plain `score_text` payload the assertion above
    would pass for a new reason, and the document would then be describing fields that no longer
    exist — the opposite drift, equally worth catching."""
    result = untell_text(
        TEXT, tier="lite", threshold=0.3, max_iters=1, rewriter="structural", best_of=1, seed=1
    )
    assert set(result["post"]) - set(result["pre"]) == {"flagged_sentences", "style"}


def test_the_check_catches_an_undocumented_field(documented, payloads) -> None:
    """Vacuity check against a synthetic addition: the comparison must actually be able to fail."""
    fake = dict(payloads["score_text"])
    fake["a_field_nobody_documented"] = 1
    assert sorted(set(fake) - documented["score_text"]) == ["a_field_nobody_documented"]
