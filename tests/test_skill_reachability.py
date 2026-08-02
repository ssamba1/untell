"""Every step script must be runnable, and the skill must actually reference it.

Three capabilities were found sitting behind this exact gap, one after another: the NLI meaning
gate, the predicate-argument veto, and the watermark scrub. Each was implemented, tested, and
documented in the README as part of the pipeline — and each was unreachable from SKILL.md, because
the skill drives every step through `python scripts/<name>.py` and none of the three had a CLI.

The scrub one mattered most: text could complete the entire loop, read perfectly human, and still
carry an intact zero-width watermark identifying its origin.

Nothing detected any of it, because "module exists and its unit tests pass" and "the flagship path
can run it" are different properties. These tests check the second one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "untell" / "scripts"
SKILL = REPO / "untell" / "SKILL.md"

# Infrastructure, not steps: the dispatcher front door and the IO helper. Excluded from both checks.
_NOT_STEPS = {"__init__.py", "cli.py", "io_utils.py"}

# Runnable commands that are deliberately NOT steps of the skill's procedure. They still must have
# a working CLI — they are just not things Claude invokes while looping:
#   run.py     — the headless loop itself. On the skill path Claude *is* the rewriter, so calling
#                run.py would be running a second, competing loop inside the first.
#   verify.py  — a standalone honest pass/fail report a user runs against a finished draft; the
#                loop already gets per-detector numbers from score.py.
# Keep this list short and justified. Every entry is a place the guard is deliberately blind, and
# the three gaps that motivated this file all looked exactly like "obviously not a step" until
# someone checked.
_NOT_SKILL_STEPS = {"run.py", "verify.py"}


def _step_modules() -> list[Path]:
    return sorted(p for p in SCRIPTS.glob("*.py") if p.name not in _NOT_STEPS)


def _skill_step_modules() -> list[Path]:
    return [p for p in _step_modules() if p.name not in _NOT_SKILL_STEPS]


def test_there_are_step_modules_to_check():
    """Guard the guard: an empty glob would make every test below pass vacuously."""
    assert len(_step_modules()) >= 5


@pytest.mark.parametrize("module", _step_modules(), ids=lambda p: p.stem)
def test_step_script_has_a_cli(module: Path):
    """`main()` plus a `__main__` guard — without the guard, `python scripts/x.py` silently does
    nothing and exits 0, which is worse than failing. That was a real bug in the entailment CLI:
    it had `main()`, ran clean, printed nothing, and returned success on a rewrite it should have
    rejected."""
    src = module.read_text(encoding="utf-8", errors="replace")
    assert re.search(r"^def main\(", src, re.M), f"{module.name} has no main() — the skill cannot run it"
    assert re.search(r'^if __name__ == "__main__":', src, re.M), (
        f"{module.name} defines main() but never calls it; `python scripts/{module.name}` would "
        "exit 0 having done nothing"
    )


@pytest.mark.parametrize("module", _skill_step_modules(), ids=lambda p: p.stem)
def test_step_script_is_referenced_by_the_skill(module: Path):
    """A step the skill never mentions is a step the flagship path does not run.

    Matches on the full filename, not the stem: 'run' and 'verify' occur constantly as ordinary
    words in the prose, so a stem match reports every script as referenced and finds nothing.
    """
    skill = SKILL.read_text(encoding="utf-8", errors="replace")
    assert module.name in skill, (
        f"{module.name} is a runnable step but SKILL.md never mentions it — either wire it into "
        "the procedure or move it out of scripts/"
    )


def test_skill_invokes_scripts_by_relative_path():
    """The skill's idiom is `python scripts/<name>.py`. A `-m untell.scripts.x` form needs the
    package parent on sys.path, which is not guaranteed from the skill's working directory."""
    skill = SKILL.read_text(encoding="utf-8", errors="replace")
    stray = re.findall(r"python -m untell\.scripts\.\w+", skill)
    assert not stray, f"SKILL.md should call scripts by path, not -m: {stray}"
