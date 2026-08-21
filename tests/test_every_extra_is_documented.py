"""Every non-internal optional extra declared in pyproject.toml must have a pip-install
line somewhere in README.md or docs/*.md.

Defect class: a pyproject.toml extra exists, a feature silently uses it, and users
have no discoverable install command for it. The [docs] and [rich] extras were the
first instances — both provided real user-facing functionality (.docx/.pdf reading and
coloured terminal output respectively) with zero install documentation.

Extras explicitly excluded from this check:
- ``dev`` — contributor tooling only; not shipped to end users.

An extra that genuinely should not be documented (CI-only, etc.) can be added to
INTERNAL_EXTRAS below with a comment explaining why.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Extras that do not need user-facing install documentation.
# Add here with a comment rather than silently omitting the check.
INTERNAL_EXTRAS: frozenset[str] = frozenset(
    {
        "dev",  # contributor tooling: pytest, ruff, httpx — not an end-user feature
    }
)


def _declared_extras() -> set[str]:
    """Return the set of extra names declared in [project.optional-dependencies]."""
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    block = pyproject[pyproject.index("[project.optional-dependencies]") :]
    end = block.find("\n[", 1)
    block = block[:end] if end != -1 else block
    return set(re.findall(r"^(\w+) = \[", block, re.M))


def _documented_extras() -> set[str]:
    """Return the set of extra names that appear in a pip install command in README or docs."""
    sources = [REPO / "README.md"] + sorted((REPO / "docs").glob("*.md"))
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sources if p.exists())
    # Match both: pip install "untell[extra]"  and  pip install -e ".[extra]"
    # The latter expands to multiple extras when comma-separated, so split on comma.
    raw_matches: list[str] = []
    for m in re.finditer(r'pip install[^"\n]*"(?:untell|\.)?\[([^\]]+)\]"', text):
        raw_matches.extend(e.strip() for e in m.group(1).split(","))
    return set(raw_matches)


def test_every_extra_has_a_pip_install_line() -> None:
    """Each non-internal extra must be installable from the docs alone."""
    declared = _declared_extras()
    documented = _documented_extras()

    user_extras = declared - INTERNAL_EXTRAS
    undocumented = user_extras - documented

    assert not undocumented, (
        f"Optional extra(s) {sorted(undocumented)!r} are declared in pyproject.toml "
        f"but have no pip install command in README.md or docs/*.md. "
        f"A user who needs the feature cannot discover how to enable it. "
        f"Either add a pip install line to README.md/docs/ or add the extra to "
        f"INTERNAL_EXTRAS with a comment if it is not end-user-facing."
    )


def test_internal_extras_allowlist_is_not_stale() -> None:
    """Every entry in INTERNAL_EXTRAS must still exist in pyproject.toml.

    If an extra is removed from pyproject.toml and its name stays in INTERNAL_EXTRAS,
    the check above silently stops covering it — and the next add/rename of that extra
    name would skip the check without anyone noticing.
    """
    declared = _declared_extras()
    stale = INTERNAL_EXTRAS - declared
    assert not stale, (
        f"INTERNAL_EXTRAS in this test file names extra(s) {sorted(stale)!r} that no "
        f"longer exist in pyproject.toml [project.optional-dependencies]. "
        f"Remove them from INTERNAL_EXTRAS."
    )


def test_there_are_extras_to_check() -> None:
    """Guards the guard: if the parser returns nothing, the tests above pass vacuously."""
    extras = _declared_extras()
    assert len(extras) >= 10, f"expected at least 10 declared extras, found {sorted(extras)}"
