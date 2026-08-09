"""`docs/result-shapes.md` must describe what the functions actually return.

The document exists because three result dicts were misread in one session, each producing a
plausible wrong answer rather than a KeyError. A reference that drifts would reintroduce exactly
that failure with an authoritative tone, so every key it lists is checked against a live call.

Deliberately checks the direction that matters: a key the doc names must exist. Extra keys in the
result are fine — a function may grow a field before the doc catches up, and failing on that would
make the test a chore rather than a guard. What must not happen is the doc naming something that
is not there.
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
    current = None
    for line in block.splitlines():
        if not line.strip():
            continue
        head = re.match(r"^(\w+)\s+(.*)$", line)
        if head and not line.startswith(" "):
            current = head.group(1)
            out[current] = set()
            rest = head.group(2)
        else:
            rest = line
        if current is None:
            continue
        if rest.strip().startswith("+"):  # conditional keys, noted separately
            continue
        out[current].update(k.strip() for k in rest.split(",") if k.strip() and " " not in k.strip())
    return out


DOCUMENTED = _documented_keys()


def test_the_document_lists_every_function():
    expected = {"score_text", "score_tells", "score_sentences", "untell_text", "verify"}
    assert set(DOCUMENTED) == expected, f"parsed {sorted(DOCUMENTED)}"


def test_no_function_block_is_empty():
    """Guards the guard: a parsing change that produced empty sets would pass everything below."""
    for name, keys in DOCUMENTED.items():
        assert len(keys) >= 4, f"{name} parsed only {keys}"


@pytest.mark.parametrize("func", ["score_text", "score_tells", "score_sentences", "verify"])
def test_documented_keys_exist(func):
    from untell.scripts.score import score_text
    from untell.scripts.sentences import score_sentences
    from untell.scripts.tells import score_tells
    from untell.scripts.verify import verify

    calls = {
        "score_text": lambda: score_text(TEXT, tier="lite"),
        "score_tells": lambda: score_tells(TEXT),
        "score_sentences": lambda: score_sentences(TEXT, tier="lite"),
        "verify": lambda: verify(TEXT),
    }
    result = calls[func]()
    missing = sorted(DOCUMENTED[func] - set(result))
    assert not missing, f"{func} does not return documented keys: {missing}"


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
