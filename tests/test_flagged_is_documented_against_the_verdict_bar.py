"""Two documents still defined `flagged` by the loop threshold, years after that stopped being true.

FOUND by asking whether the two thresholds are compared the same way everywhere. In the CODE they
are: over 10 HC3 documents scoring between the loop bar (0.30) and the verdict bar (0.45), every
user-visible surface agreed — `score_text`, `untell_text` top level, `pre` and `post` all reported
`flagged: false` against `verdict_threshold: 0.45`. That hypothesis was refuted.

The drift was in the writing. `flagged` used to mean `max >= threshold`; the CHANGELOG records the
day it stopped, `SKILL.md` warns at length that "`flagged` and `max < threshold` are two different
questions now", `result-shapes.md` and the OpenAPI description were both updated. Two surfaces were
missed:

    untell/references/thresholds.md   "`flagged` — `true` when `max >= threshold` (keep rewriting)."
    untell/scripts/score.py           '"flagged": true   # max >= threshold => still looks AI, keep
                                       rewriting'

Both state the rule `SKILL.md` exists to correct, and both say to drive the loop on it. An agent
reading either would stop rewriting at `max = 0.35` — inside the band where the loop should continue
— or, worse, tell a user their text is flagged when the calibrated verdict says it is not. That is
the false accusation `verdict_threshold` was introduced to prevent, and the reference document about
thresholds was the one still recommending it.

This file is the machine check that was missing. It fails on the exact text that shipped: verified by
running it against the pre-fix wording of both files, where it names both.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Shipped surfaces a reader or an agent consults for the contract. The CHANGELOG and the results log
# are deliberately excluded: they are historical records, and a record of what `flagged` USED to mean
# is correct exactly as written.
SURFACES = [
    "untell/references/thresholds.md",
    "untell/SKILL.md",
    "untell/scripts/score.py",
    "docs/result-shapes.md",
    "README.md",
]

# A line that ties `flagged` to a bare `threshold` comparison is defining it, quoting it, or
# illustrating it. Any of those is fine as long as the distinction is right there — hence the window
# below rather than a same-line requirement: SKILL.md's correct passage spans several lines.
_DEFINES = re.compile(r"flagged", re.IGNORECASE)
_BARE_COMPARISON = re.compile(r"max\s*(>=|<|>|<=)\s*`?threshold", re.IGNORECASE)
# Naming `verdict_threshold` is one way to carry the distinction; saying it outright is another, and
# SKILL.md does the second — "no longer the same as `flagged: false`" IS the correction, with the
# field named eight lines further down. Requiring the identifier within a window rejected that
# passage, which would have pushed the documents toward the jargon and away from the explanation.
_CORRECTS = re.compile(
    r"verdict_threshold|no longer the same|two different questions|not the same as", re.IGNORECASE
)
_WINDOW = 4


def _offending_lines(path: Path) -> list[tuple[int, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    for i, line in enumerate(lines):
        if not (_DEFINES.search(line) and _BARE_COMPARISON.search(line)):
            continue
        near = "\n".join(lines[max(0, i - _WINDOW) : i + _WINDOW + 1])
        if not _CORRECTS.search(near):
            out.append((i + 1, line.strip()))
    return out


@pytest.mark.parametrize("rel", SURFACES)
def test_no_surface_defines_flagged_by_the_loop_threshold(rel: str) -> None:
    path = ROOT / rel
    if not path.exists():  # a moved file is the audit's business, not this test's
        pytest.skip(f"{rel} is not present")
    offenders = _offending_lines(path)
    assert not offenders, f"{rel} ties `flagged` to `threshold` with no `verdict_threshold` near it: {offenders}"


def test_the_check_catches_the_text_that_actually_shipped(tmp_path: Path) -> None:
    """Guards the guard, with the real defect rather than an invented one. Without this the test
    above passes on any file that simply never mentions `flagged`."""
    shipped = tmp_path / "thresholds.md"
    shipped.write_text(
        "- `max` / `mean` — aggregate proxies; the loop drives `max`.\n"
        "- `flagged` — `true` when `max >= threshold` (keep rewriting).\n",
        encoding="utf-8",
    )
    assert _offending_lines(shipped), "the check does not catch the wording that shipped"


def test_the_check_accepts_the_correct_wording(tmp_path: Path) -> None:
    """And the other direction: a passage that draws the distinction must pass, or the check would
    force the documents to stop explaining the band at all."""
    fixed = tmp_path / "ok.md"
    fixed.write_text(
        "- `verdict_threshold` — the calibrated bar `flagged` is decided on.\n"
        "- `flagged` — `true` when `max >= verdict_threshold`. Drive the loop on `max < threshold`\n"
        "  instead; between the two there is a band where `max >= threshold` and `flagged` is false.\n",
        encoding="utf-8",
    )
    assert not _offending_lines(fixed)


def test_the_two_bars_really_are_different_by_default() -> None:
    """The premise the documents have to describe. If these ever collapse to one number the wording
    above is harmless but pointless, and this test says which world we are in."""
    from untell.scripts.score import score_text

    result = score_text(
        "Moreover, the framework leverages a robust approach to delivery at scale. "
        "Furthermore, this underscores the pivotal integration for every team involved.",
        tier="lite",
    )
    assert result["verdict_threshold"] >= result["threshold"]
    assert result["flagged"] == (result["max"] >= result["verdict_threshold"])
