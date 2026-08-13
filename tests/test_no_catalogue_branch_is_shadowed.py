"""Two defects in an alternation are decidable without matching anything.

The probe-based audit in `test_no_catalogue_branch_is_dead.py` reaches 64 of roughly 248 literal
branches. Pushing it further does not work with that machinery: MEASURED, 185 branches sit in groups
the category probe never captured, and synthesizing a probe per branch reaches only 10 more because
64 of those groups need surrounding pattern context to match at all. Supplying it means expanding
the regex, which is real machinery and a poor thing to write blind.

These two defects need no match at all, so they cover branches the other file cannot reach:

DUPLICATE — the same literal twice in one alternation. Harmless to behaviour, and a reliable sign of
an edit applied twice; the second copy can never be the branch that matches.

SHADOWED — a branch that can never win. Python's alternation is ordered and first-match, so in
`(?:run|running)` the branch `running` never matches as itself: `run` takes the position first. Any
earlier branch that is a PREFIX of a later one shadows it, UNLESS the group is followed by a word
boundary, which forces the engine past the short branch. That trailing `\\b` is exactly the detail
that gets lost when a list grows to forty words.

RESULT: 62 groups examined, 148 branch pairs compared, 0 duplicates, 0 shadowed.
"""

from __future__ import annotations

import collections
import re

import pytest

from untell.scripts.tells import _CATEGORIES

_LITERAL_RE = re.compile(r"^[a-zA-Z][a-zA-Z '\-]*$")

# The audit must fail rather than pass silently if a refactor makes it vacuous. Every earlier
# version of this work reached a confident zero at least once while measuring almost nothing.
_MIN_GROUPS = 30
_MIN_PAIRS = 80


def _alternation_groups(src: str) -> list[tuple[str, int]]:
    """(body, offset just past the closing paren) for every ``(?:...)`` with no nested group."""
    out: list[tuple[str, int]] = []
    i = 0
    while i < len(src):
        if src[i] == "\\":
            i += 2
            continue
        if src.startswith("(?:", i):
            depth, j = 1, i + 3
            while j < len(src) and depth:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "(":
                    depth += 1
                elif src[j] == ")":
                    depth -= 1
                j += 1
            body = src[i + 3:j - 1]
            if "(" not in body:
                out.append((body, j))
            i += 3
            continue
        i += 1
    return out


def _literals(body: str) -> list[str]:
    return [a.strip() for a in body.split("|") if _LITERAL_RE.match(a.strip())]


# A trailing word boundary means a short branch cannot swallow a longer word, so prefix ordering is
# safe there. Read from the source immediately after the group's own closing paren — an earlier
# version searched for the body text instead, which finds the wrong occurrence when two groups share
# a body.
_BOUNDARY_AFTER = (r"\b", r"(?!\w", r"\s", r"s?\b", r"\W", r"(?![a-z]")


@pytest.mark.parametrize("name,compiled", _CATEGORIES, ids=[n for n, _ in _CATEGORIES])
def test_no_literal_appears_twice_in_one_alternation(name: str, compiled: re.Pattern) -> None:
    for body, _end in _alternation_groups(compiled.pattern):
        counts = collections.Counter(a.lower() for a in _literals(body))
        repeated = {lit: n for lit, n in counts.items() if n > 1}
        assert not repeated, f"{name}: {repeated} — the second copy can never be the branch that matches"


@pytest.mark.parametrize("name,compiled", _CATEGORIES, ids=[n for n, _ in _CATEGORIES])
def test_no_branch_is_shadowed_by_an_earlier_prefix(name: str, compiled: re.Pattern) -> None:
    src = compiled.pattern
    for body, end in _alternation_groups(src):
        if src[end:end + 8].startswith(_BOUNDARY_AFTER):
            continue  # a boundary after the group forces the engine past the shorter branch
        lits = _literals(body)
        for i, earlier in enumerate(lits):
            for later in lits[i + 1:]:
                assert not (
                    later.lower().startswith(earlier.lower()) and later.lower() != earlier.lower()
                ), (
                    f"{name}: {later!r} can never match — {earlier!r} comes first in the same "
                    f"alternation and is a prefix of it, with no word boundary after the group"
                )


def test_the_audit_examines_enough_to_mean_something() -> None:
    """Guards both tests above. An `_alternation_groups` that returned nothing, or a `_literals`
    that filtered everything out, would make every case pass while checking zero branches."""
    groups = pairs = 0
    for _name, compiled in _CATEGORIES:
        for body, _end in _alternation_groups(compiled.pattern):
            lits = _literals(body)
            if len(lits) < 2:
                continue
            groups += 1
            pairs += len(lits) * (len(lits) - 1) // 2
    assert groups >= _MIN_GROUPS, f"only {groups} multi-branch alternations found"
    assert pairs >= _MIN_PAIRS, f"only {pairs} branch pairs to compare"


def test_the_shadowing_rule_is_the_real_regex_behaviour() -> None:
    """The premise, asserted rather than assumed. If Python ever preferred the longest alternative,
    the whole shadowing test would be checking a rule that does not exist."""
    assert re.search(r"(?:run|running)", "running").group(0) == "run"
    # And the boundary exemption is real: with \b after the group, the short branch cannot take it.
    assert re.search(r"(?:run|running)\b", "running").group(0) == "running"
