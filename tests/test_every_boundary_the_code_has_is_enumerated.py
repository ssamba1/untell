"""Round 99 said boundary tests "do not scale". They do not scale by hand — which is different.

The arc: round ninety-seven measured that this suite catches branch inversions and misses
off-by-ones, 55 to 0 over the pairs where it distinguishes them. Round ninety-eight fixed eight
thresholds and killed 7 of 7. Round ninety-nine established the mechanism — a property test runs on
whatever a corpus contains, away from every boundary — and concluded that the boundary discipline
cannot be applied 206 times.

**The part that does not scale is finding them, and that part is mechanical.** `x < THRESHOLD` has
exactly one boundary and it is written in the source. `eval/boundaries.py` enumerates every
comparison in `untell/` against a named numeric module constant and cross-references the boundary
mutation sweep to say which are protected. Eight thresholds found by grepping for names I thought of
becomes every threshold the code has.

⚠️ **A register is only as current as its sweep, and the first version was not.** It read a sweep
taken before round ninety-eight's tests existed, so all seven boundaries that round had verified as
killed came back "unprotected" — every number wrong in the alarming direction, which is the one that
wastes the most work. `sweep_is_stale` compares modification times and the report leads with the
warning.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from eval import boundaries

REPO = Path(__file__).resolve().parent.parent
REGISTER = json.loads((REPO / "eval" / "data" / "boundary_register.json").read_text())


def test_the_register_found_the_boundaries_that_are_there():
    """A scan that silently stops matching reports a fully protected repository."""
    assert REGISTER["boundaries"] >= 30, "the enumeration is broken, not the code"
    constants = {
        entry["constant"]
        for group in ("protected", "unprotected", "unmeasured")
        for entry in REGISTER[group]
    }
    assert "_MIN_WORDS_FOR_SIGNAL" in constants
    assert "_MIN_WORDS_FOR_A_BAND" in constants


def test_it_finds_a_boundary_in_a_synthetic_module(tmp_path):
    """The enumeration itself, on a case where the answer is known."""
    root = tmp_path / "repo"
    (root / "untell").mkdir(parents=True)
    (root / "untell" / "m.py").write_text(
        "_FLOOR = 12\n_NAME = 'x'\n\ndef f(n):\n    if n < _FLOOR:\n        return 0\n    return 1\n"
    )
    found = boundaries.boundaries(root)
    assert [(e["constant"], e["line"]) for e in found] == [("_FLOOR", 5)]


def test_a_comparison_against_a_literal_is_not_a_named_boundary(tmp_path):
    """Deliberate: an inline 3 is a different problem, and flagging every one would drown this."""
    root = tmp_path / "repo"
    (root / "untell").mkdir(parents=True)
    (root / "untell" / "m.py").write_text("def f(n):\n    return n < 3\n")
    assert boundaries.boundaries(root) == []


def test_equality_is_not_a_boundary(tmp_path):
    """`==` has no off-by-one to shift; only ordering comparisons do."""
    root = tmp_path / "repo"
    (root / "untell").mkdir(parents=True)
    (root / "untell" / "m.py").write_text("_N = 5\n\ndef f(x):\n    return x == _N\n")
    assert boundaries.boundaries(root) == []


def test_the_exclusion_list_is_short_and_every_entry_still_exists():
    """The default is that a named constant in a comparison IS a boundary."""
    assert len(boundaries.NOT_A_THRESHOLD) < 15, (
        "a long exclusion list turns this register into a list of what somebody felt like checking"
    )
    names: set[str] = set()
    for path in (REPO / "untell").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        names |= boundaries._module_constants(tree)
    dead = sorted(boundaries.NOT_A_THRESHOLD - names)
    assert not dead, f"excluded constants that no longer exist: {dead}"


def test_a_stale_sweep_is_reported_rather_than_believed():
    """The defect the first version shipped with, pinned so it cannot come back silently."""
    stale = REGISTER.get("stale_since_sweep")
    assert stale is not None, "the register must record whether its sweep is current"
    assert isinstance(stale, list)


def test_the_freshness_check_notices_a_newer_test(tmp_path):
    """Verified against a real file rather than asserted."""
    root = tmp_path / "repo"
    (root / "eval" / "data").mkdir(parents=True)
    (root / "tests").mkdir()
    sweep = root / "eval" / "data" / "mutation_boundary.json"
    sweep.write_text("{}")
    assert boundaries.sweep_is_stale(root) == []

    newer = root / "tests" / "test_later.py"
    newer.write_text("def test_x(): pass\n")
    import os
    os.utime(newer, (sweep.stat().st_mtime + 60, sweep.stat().st_mtime + 60))
    assert boundaries.sweep_is_stale(root) == ["tests/test_later.py"]


def test_a_missing_sweep_is_stale_rather_than_clean(tmp_path):
    root = tmp_path / "repo"
    (root / "eval" / "data").mkdir(parents=True)
    (root / "tests").mkdir()
    assert boundaries.sweep_is_stale(root), "no sweep at all must not read as up to date"


def test_the_thresholds_round_98_fixed_are_recorded_as_protected():
    """The seven off-by-ones verified killed in round 98 must show as protected here.

    This is the register's own calibration: if boundaries known to be tested come back unprotected,
    the cross-reference is wrong and every other row is suspect.
    """
    protected = {(e["file"], e["line"]) for e in REGISTER["protected"]}
    known_fixed = {
        ("untell/scripts/score.py", 732),
        ("untell/scripts/tells.py", 723),
        ("untell/scripts/tells.py", 853),
        ("untell/humanness.py", 426),
    }
    missing = sorted(known_fixed - protected)
    assert not missing, (
        f"round 98 verified these off-by-ones as killed and the register disagrees: {missing}. "
        f"Either the sweep is stale or the cross-reference is broken."
    )
