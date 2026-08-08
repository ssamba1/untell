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
#   audit.py   — `untell-audit` re-checks the DOCUMENTATION against the code. It is a maintainer
#                and CI command about this repository's claims, not a step in anyone's rewrite, and
#                it does not read or produce the user's text at all.
# Keep this list short and justified. Every entry is a place the guard is deliberately blind, and
# the three gaps that motivated this file all looked exactly like "obviously not a step" until
# someone checked.
_NOT_SKILL_STEPS = {"run.py", "verify.py", "audit.py"}


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


def test_no_step_script_shadows_a_stdlib_module():
    """A script here must not be named after a stdlib module.

    SKILL.md runs every step as `python scripts/<name>.py`, and Python puts the SCRIPT'S directory
    first on sys.path. So a file named `numbers.py` in this folder becomes THE `numbers` module for
    that process — including for numpy, which does `import numbers` and calls
    `numbers.Integral.register(...)` during its own import.

    That is not theoretical. Adding `scripts/numbers.py` broke `python scripts/preserve.py` outright:

        AttributeError: module 'numbers' has no attribute 'Integral'

    preserve.py -> spacy -> thinc -> numpy, and numpy's import died on the shadowed module. Every
    step script that reaches numpy transitively would have failed the same way, which is most of
    them, via the exact invocation the skill documents. Renaming to `numerals.py` fixed it.
    """
    import sys

    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    assert stdlib, "sys.stdlib_module_names unavailable — this guard needs Python 3.10+"

    offenders = [p.name for p in SCRIPTS.glob("*.py") if p.stem in stdlib]
    assert not offenders, (
        f"these shadow stdlib modules for any `python scripts/<name>.py` run: {offenders}. "
        "Rename them — the shadowing breaks any dependency that imports the real module."
    )


def test_stdlib_shadowing_guard_would_actually_fire():
    """Guard the guard: prove the check recognises a known stdlib name."""
    import sys

    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    assert {"numbers", "json", "types", "string"} <= stdlib


def test_skill_runs_every_check_the_loop_runs():
    """SKILL.md must call every gate `meaning_preserved()` calls.

    This is the divergence that kept recurring: the headless loop gained the NLI gate, then the
    predicate-argument veto, then quantity and certainty checks, and each time the flagship path —
    where Claude is the rewriter — was left running an older, weaker gate. The skill was still
    enforcing a similarity bar the loop had abandoned, and had no contradiction check at all.

    `meaning_preserved` imports its sub-checks lazily by module, so the set of imports inside it is
    the authoritative list of what the loop enforces. Every one must appear in SKILL.md as a step.
    """
    import inspect

    from untell.scripts import entailment

    src = inspect.getsource(entailment.meaning_preserved)
    modules = set(re.findall(r"from untell\.scripts\.(\w+) import", src))
    assert modules, "no sub-check imports found — has meaning_preserved been restructured?"

    skill = SKILL.read_text(encoding="utf-8", errors="replace")
    missing = sorted(m for m in modules if f"scripts/{m}.py" not in skill)
    assert not missing, (
        f"the loop's meaning gate runs {sorted(modules)} but SKILL.md never invokes {missing} — "
        "the flagship path would enforce a weaker gate than the headless loop"
    )


def test_every_module_with_a_main_can_be_run_with_dash_m():
    """`python -m untell.humanness` executed the module, printed nothing, and exited 0.

    The guard above only walks `untell/scripts/`, so a module with a `main()` living anywhere else
    in the package was never checked — and `untell/humanness.py` had no `__main__` block. Its
    console script and `untell humanness` both worked, which is exactly why nobody noticed: only
    the `-m` form was dead, and it failed by succeeding silently.
    """
    import re

    package = REPO / "untell"
    offenders = []
    for path in sorted(package.rglob("*.py")):
        if "__pycache__" in path.parts or path.name == "__init__.py":
            continue
        src = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^def main\(", src, re.M) and "__main__" not in src:
            offenders.append(str(path.relative_to(REPO)))

    assert not offenders, (
        f"these define main() but have no `if __name__ == '__main__'` block, so `python -m` on "
        f"them does nothing and exits 0: {offenders}"
    )
