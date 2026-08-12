"""`docs/result-shapes.md` must describe what the functions actually return.

The document exists because three result dicts were misread in one session, each producing a
plausible wrong answer rather than a KeyError. A reference that drifts would reintroduce exactly
that failure with an authoritative tone, so every key it lists is checked against a live call.

This file used to check one direction only, on the reasoning that "a function may grow a field
before the doc catches up, and failing on that would make the test a chore rather than a guard".
That judgement was reasonable and the evidence went against it: the doc did not catch up. By the
time the reverse check was added, `untell_text` was returning three keys the document did not
list — `seed`, `tells_before`, `tells_after` — added across three separate commits, none of which
updated the list, and nothing anywhere surfaced the drift.

A result shape nobody can look up is the same defect as one that is wrong: a caller writing
against `.get()` receives None either way and finds out in production. So both directions are
checked now, with conditional keys — the ones the document annotates "(only when ...)" — held in
their own set, since asserting `warning` is always present fails on any text without a caveat.

`untell_text` was also documented and never called here, so its list could have said anything. It
is the longest of the five and the one that changes most often.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parent.parent / "docs" / "result-shapes.md"
TEXT = (
    "Moreover, the framework leverages a robust approach to deliver outcomes. "
    "The kettle boiled while I read the last few pages of the book."
)


def _documented_keys() -> dict[str, set[str]]:
    """Parse the fenced 'Full key lists' block into {function: {keys}}."""
    body = DOC.read_text(encoding="utf-8")
    block = body.split("## Full key lists", 1)[1].split("```", 2)[1]
    out: dict[str, set[str]] = {}
    conditional: dict[str, set[str]] = {}
    current = None
    for line in block.splitlines():
        if not line.strip():
            continue
        head = re.match(r"^(\w+)\s+(.*)$", line)
        if head and not line.startswith(" "):
            current = head.group(1)
            out.setdefault(current, set())
            conditional.setdefault(current, set())
            rest = head.group(2)
        else:
            rest = line
        if current is None:
            continue
        if rest.strip().startswith("+"):  # conditional keys, noted separately
            continue
        # Conditional keys carry a "(only when ...)" note. They are DOCUMENTED but not always
        # RETURNED, so they belong in a separate set: asserting `warning` is always present fails
        # on any text without a caveat, and leaving it unparsed — tokens containing a space are
        # skipped as prose — made it count as undocumented wherever it did appear.
        for chunk in re.split(r",(?![^(]*\))", rest):
            # Two notations mark a conditional key and the document uses both: a trailing "?"
            # (`unrankable?`) and a parenthetical (`warning (only when a caveat applies)`). Reading
            # only the parenthetical form made `unrankable?` parse as a key literally named with a
            # question mark, so it was demanded on every response and never found.
            note = re.search(r"\(([^)]*)\)", chunk)
            name = re.sub(r"\([^)]*\)", "", chunk).strip()
            if name.endswith("?"):
                name, note = name[:-1].strip(), note or "?"
            if not name or " " in name:
                continue
            (conditional if note else out)[current].add(name)
    return out, conditional


DOCUMENTED, CONDITIONAL = _documented_keys()


def test_the_document_lists_every_function():
    expected = {"score_text", "score_tells", "score_sentences", "untell_text", "verify"}
    assert set(DOCUMENTED) == expected, f"parsed {sorted(DOCUMENTED)}"


def test_no_function_block_is_empty():
    """Guards the guard: a parsing change that produced empty sets would pass everything below."""
    for name, keys in DOCUMENTED.items():
        assert len(keys) >= 4, f"{name} parsed only {keys}"


def _call(func: str):
    from untell.scripts.run import untell_text
    from untell.scripts.score import score_text
    from untell.scripts.sentences import score_sentences
    from untell.scripts.tells import score_tells
    from untell.scripts.verify import verify

    return {
        "score_text": lambda: score_text(TEXT, tier="lite"),
        "score_tells": lambda: score_tells(TEXT),
        "score_sentences": lambda: score_sentences(TEXT, tier="lite"),
        "verify": lambda: verify(TEXT),
        # `untell_text` was documented and never called here, so its key list could say anything.
        # It is the longest list of the five and the one that changes most often.
        "untell_text": lambda: untell_text(
            TEXT, tier="lite", max_iters=1, best_of=1, rewriter="composite"
        ),
    }[func]()


ALL_FUNCS = ["score_text", "score_tells", "score_sentences", "verify", "untell_text"]


@pytest.mark.parametrize("func", ALL_FUNCS)
def test_documented_keys_exist(func):
    result = _call(func)
    missing = sorted(DOCUMENTED[func] - set(result))
    assert not missing, f"{func} does not return documented keys: {missing}"


@pytest.mark.parametrize("func", ALL_FUNCS)
def test_returned_keys_are_documented(func):
    """The other direction, which nothing checked.

    `test_documented_keys_exist` asks whether the doc promises anything the code does not deliver.
    It cannot see the reverse — a key ADDED to a result and not written down — so the document
    drifted silently in the direction it was most likely to drift. MEASURED when this was added:
    `untell_text` returned `seed`, `tells_before` and `tells_after` beyond its documented list, two
    of which had been added in this session and one earlier.

    A result shape nobody can look up is the same defect as one that is wrong; a caller writing
    against `.get()` gets None either way and finds out in production.
    """
    result = _call(func)
    undocumented = sorted(set(result) - DOCUMENTED[func] - CONDITIONAL[func])
    assert not undocumented, (
        f"{func} returns keys the document does not list: {undocumented}. Add them to the "
        "'Full key lists' block rather than deleting this assertion — a caller cannot use a key "
        "they cannot find."
    )


def test_untell_text_documented_keys_exist():
    """Separate because it runs the loop and is slower than the rest put together."""
    from untell.scripts.run import untell_text

    result = untell_text(TEXT, tier="lite", rewriter="structural", best_of=1, max_iters=1)
    missing = sorted(DOCUMENTED["untell_text"] - set(result))
    assert not missing, f"untell_text does not return documented keys: {missing}"


def test_the_confusable_names_the_doc_warns_about_are_still_absent():
    """The whole point of the table. If any of these appear, the document is now lying about the
    thing it exists to prevent."""
    from untell.scripts.run import untell_text
    from untell.scripts.score import score_text
    from untell.scripts.sentences import score_sentences

    assert "text" not in untell_text(
        TEXT, tier="lite", rewriter="structural", best_of=1, max_iters=1
    )
    assert "scores" not in score_text(TEXT, tier="lite")
    for entry in score_sentences(TEXT, tier="lite")["sentences"]:
        assert "score" not in entry


def test_the_bare_float_returns_are_still_bare():
    from untell.humanness import humanness
    from untell.scripts.quality import similarity

    assert isinstance(humanness(TEXT), float)
    assert isinstance(similarity(TEXT, TEXT), float)
