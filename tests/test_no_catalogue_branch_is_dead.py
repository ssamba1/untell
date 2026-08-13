"""Every catalogue PATTERN is tested. Every BRANCH inside it is not.

`test_every_tell_category_can_fire.py` gives each category one egregious example and requires a
match. That proves the pattern compiles and fires; it says nothing about the other forty words in
its alternation. A single dead branch is invisible: the category still fires on everything else,
the count is merely lower than it should be, and lower reads as cleaner text.

This repo has been bitten by exactly that. A literal 0x08 where `\\b` was meant killed three
patterns outright while every category test kept passing.

THE METHOD, which took three attempts and is the part worth keeping.

Attempt 1 dropped each literal branch into a generic carrier sentence and asked whether the pattern
matched. It reported 238 dead of 248 — because most patterns need several parts at once
(`vague_attribution` wants a vague SOURCE and a reporting VERB), so a lone branch satisfies half a
pattern and matches nothing. The probe was measuring its own naivety.

Attempt 2 restricted the audit to patterns that are a single alternation, where one branch IS
sufficient. Valid, and it covered 1 pattern of 20. Correct and nearly useless.

Attempt 3 substitutes inside a probe that already matches: recompile the pattern with its
non-capturing groups made capturing, run it on the known-positive probe, read off which alternation
produced which text, then swap that text for each sibling branch. Every other part of the pattern
stays satisfied, so a failure means that branch specifically cannot match.

Its first run was still wrong, and wrong in a way that looked like findings — it reported
`negated_contrast: 'it' (sibling of 'It is not just a tool, it is ')`, which is not a sibling of
anything. `re.findall` returns only groups without nested parens, while converting every `(?:` to
`(` renumbers ALL of them, so the group indices did not line up. Counting `(?:` in source order and
matching parens by depth fixes it.

RESULT: 64 sibling branches checked, 0 dead.

COVERAGE, stated because it is partial. Only groups whose body has no nested paren are auditable —
elsewhere splitting on `|` does not yield real alternatives — and only groups the probe actually
exercised. That is 64 of roughly 248 literal branches in the catalogue. The rest are not covered by
anything here, and this file should not be read as saying they are.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re

import pytest

from untell.scripts.tells import _CATEGORIES

_spec = importlib.util.spec_from_file_location(
    "_category_probes",
    pathlib.Path(__file__).with_name("test_every_tell_category_can_fire.py"),
)
_probe_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe_module)
PROBES: dict[str, str] = _probe_module.PROBES

_LITERAL_RE = re.compile(r"^[a-zA-Z][a-zA-Z '\-]*$")

# If a refactor makes this audit vacuous it must fail rather than pass silently — the failure mode
# of every earlier attempt was reaching a confident 0 while measuring almost nothing.
_MIN_BRANCHES = 40


def _groups_in_order(src: str) -> list[tuple[int, str]]:
    """(capture index, body) for every ``(?:...)``, numbered as after ``(?:`` -> ``(``."""
    out: list[tuple[int, str]] = []
    idx = i = 0
    while i < len(src):
        if src[i] == "\\":
            i += 2
            continue
        if src.startswith("(?:", i):
            idx += 1
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
            out.append((idx, src[i + 3:j - 1]))
            i += 3
            continue
        if src[i] == "(" and not src.startswith("(?", i):
            idx += 1
        i += 1
    return out


def _audit(name: str, compiled: re.Pattern) -> tuple[int, list[tuple[str, str]]]:
    probe = PROBES.get(name)
    if not probe:
        return 0, []
    capturing = re.compile(compiled.pattern.replace("(?:", "("), compiled.flags)
    match = capturing.search(probe)
    if not match:
        return 0, []

    checked = 0
    dead: list[tuple[str, str]] = []
    for index, body in _groups_in_order(compiled.pattern):
        if "(" in body:
            continue  # nested: splitting on | would not give the real alternatives
        try:
            captured = match.group(index)
        except IndexError:
            continue
        if not captured:
            continue
        for alt in (a.strip() for a in body.split("|")):
            if not _LITERAL_RE.match(alt) or alt.lower() == captured.lower():
                continue
            checked += 1
            swapped = probe[:match.start(index)] + alt + probe[match.end(index):]
            # `compiled.search(swapped)` is NOT enough, and the known-positive below is what showed
            # it: a pattern can match somewhere ELSE in the probe, so a live verdict would be
            # spurious. `negated_contrast` did exactly that — replacing its group with nonsense
            # still matched, at a different span. Require the substituted text to be what the group
            # itself captured.
            again = capturing.search(swapped)
            if not again or (again.group(index) or "").lower() != alt.lower():
                dead.append((alt, captured))
    return checked, dead


@pytest.mark.parametrize("name,compiled", _CATEGORIES, ids=[n for n, _ in _CATEGORIES])
def test_no_sibling_branch_is_unreachable(name: str, compiled: re.Pattern) -> None:
    _checked, dead = _audit(name, compiled)
    assert not dead, (
        f"{name}: branches that cannot match where their sibling does: "
        + ", ".join(f"{alt!r} (vs {captured!r})" for alt, captured in dead)
    )


def test_the_audit_reaches_enough_branches_to_mean_something() -> None:
    """Guards the guard, and it is the whole point. Three earlier versions of this audit reached a
    confident zero while checking the wrong thing or almost nothing."""
    total = sum(_audit(name, compiled)[0] for name, compiled in _CATEGORIES)
    assert total >= _MIN_BRANCHES, (
        f"only {total} sibling branches were reachable (expected >= {_MIN_BRANCHES}); the audit has "
        f"gone vacuous and is no longer evidence of anything"
    )


def test_a_deliberately_broken_branch_is_caught() -> None:
    """Known positive. Without this, "0 dead" is a claim about the method as much as the catalogue."""
    name, compiled = next(
        (n, c) for n, c in _CATEGORIES if _audit(n, c)[0] > 0
    )
    probe = PROBES[name]
    capturing = re.compile(compiled.pattern.replace("(?:", "("), compiled.flags)
    match = capturing.search(probe)
    assert match

    for index, body in _groups_in_order(compiled.pattern):
        if "(" in body:
            continue
        try:
            captured = match.group(index)
        except IndexError:
            continue
        if not captured:
            continue
        # A branch that is certainly not in the pattern must fail the same check the audit applies.
        # Note this is the group-aware check, not a bare `search`: `negated_contrast` still matches
        # a nonsense substitution at a DIFFERENT span, which is precisely the false "live" verdict
        # the audit had to be tightened against.
        swapped = probe[:match.start(index)] + "zzqqxx" + probe[match.end(index):]
        again = capturing.search(swapped)
        assert not again or (again.group(index) or "").lower() != "zzqqxx", (
            f"{name} reports a nonsense branch as reachable, so the substitution is not actually "
            f"testing that group"
        )
        return
    pytest.fail("no auditable group found to run the known-positive against")
