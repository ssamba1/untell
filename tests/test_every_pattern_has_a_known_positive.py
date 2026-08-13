"""Every compiled pattern in the package must be shown to match something.

This repository has now shipped the same defect twice: a regex containing a literal **0x08 BACKSPACE
byte** where `\\b` was meant. The first time it killed three patterns and 2526 tests stayed green. The
second time I wrote a new one while fixing an unrelated gate, and it survived review, a passing suite
and sound reasoning — caught only because I re-ran the measurement it was supposed to move and found
it unmoved:

    STANCE_FRAME_RE.pattern[:12]  ->  '\\x08(?:[Ii]t('

**A dead pattern and a correct no-op produce identical output everywhere.** The only difference is
that a dead pattern can never fire, so this asks exactly that of every one of them.

MEASURED when this was written: 127 module-level patterns across `untell`, of which 123 match
something in the repository's own prose and source, and 4 cannot by their nature — internal
sentinels, invisible Unicode, trailing whitespace. Those four carry an explicit positive below.

A new pattern that matches nothing fails this test until someone either fixes it or states what it is
supposed to match. That is the point: the registry is not a nuisance, it is the known-positive the
lesson says every pattern needs.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
import re
from pathlib import Path

import pytest

import untell

REPO = Path(untell.__file__).resolve().parent.parent

# Patterns no natural text in this repository contains. Each entry is a string the pattern MUST
# match; if the pattern breaks, its entry stops matching and the test says which one.
KNOWN_POSITIVES: dict[str, str] = {
    # A sentinel this pipeline inserts around preserved spans, never written by a human.
    "_LEADING_SENTINEL_RE": "⟦HZ00ab⟧ the rest of the sentence follows here.",
    "_SENTINEL_AT_SENTENCE_START": "⟦HZ0001⟧ begins the text.",
    # Trailing horizontal whitespace, which every formatter in this repo strips on save.
    "_TRAILING_HORIZONTAL": "a line with trailing spaces   \nnext line",
    # Rhetorical openers the corpora happen not to contain.
    "_RHETORICAL_OPENER_RE": "Here's the thing: it works.",
    # Anchored at BOTH ends, and matched against the slice of a line that precedes a sentinel —
    # never against prose. So no document in this repository can match it, however much ordered-list
    # markup it contains, and the haystack sweep would report it dead. "1." is what `restore` hands
    # it when a locked span opens a numbered list item.
    "_LIST_MARKER_ONLY": "1. ",
}


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def _compiled_patterns() -> dict[str, re.Pattern]:
    """Every module-level compiled pattern reachable from `untell`, keyed by module.name."""
    found: dict[str, re.Pattern] = {}
    for info in pkgutil.walk_packages(untell.__path__, "untell."):
        try:
            module = importlib.import_module(info.name)
        except Exception:  # an optional dependency missing is not this test's business
            continue
        for name in dir(module):
            obj = getattr(module, name, None)
            if isinstance(obj, re.Pattern):
                found.setdefault(f"{info.name.replace('untell.', '')}.{name}", obj)
    return found


def _haystack() -> tuple[list[str], list[str]]:
    """The repository's own prose and source: whole files first, then lines for anchored patterns."""
    texts: list[str] = []
    for directory in ("untell", "tests", "docs"):
        for path in (REPO / directory).rglob("*"):
            if path.suffix in (".py", ".md"):
                texts.append(path.read_text(encoding="utf-8", errors="replace"))
    lines = [line for text in texts for line in text.splitlines()]
    return texts, lines


PATTERNS = _compiled_patterns()


def test_there_are_patterns_to_check() -> None:
    """Premise. A walk that imported nothing would make every assertion below vacuous — which is the
    same failure mode the file exists to catch, one level up."""
    assert len(PATTERNS) > 100, len(PATTERNS)


@pytest.mark.parametrize("name", sorted(PATTERNS), ids=str)
def test_the_pattern_matches_something(name: str) -> None:
    pattern = PATTERNS[name]
    bare = name.rsplit(".", 1)[-1]
    if bare in KNOWN_POSITIVES:
        assert pattern.search(KNOWN_POSITIVES[bare]), f"{name} no longer matches its known positive"
        return
    texts, lines = _HAYSTACK
    if any(pattern.search(text) for text in texts):
        return
    assert any(pattern.search(line) for line in lines), (
        f"{name} matches nothing in this repository and has no known positive.\n"
        f"    pattern: {pattern.pattern[:120]!r}\n"
        "Either it is dead — check for a literal 0x08 where \\b was meant, the defect this file "
        "exists for — or add a string it should match to KNOWN_POSITIVES."
    )


def test_no_pattern_contains_a_control_character() -> None:
    """The specific shape, asserted directly as well as behaviourally. A pattern can be alive and
    still carry a stray byte, and this names the offender instead of leaving a mystery non-match."""
    offenders = [
        (name, hex(ord(char)))
        for name, pattern in PATTERNS.items()
        for char in pattern.pattern
        if ord(char) < 0x20 and char not in "\n\t"
    ]
    assert not offenders, offenders


_HAYSTACK = _haystack()
