"""The console-script list in the docs has to be the console-script list in pyproject.

The count was right — 23 — and the parenthetical beside it named 21, silently missing
`untell-audit` and `untell-latex`. A count and a list that disagree are worse than either alone,
because the list reads as exhaustive and is what a reader actually uses.
"""

from __future__ import annotations

import pathlib
import re

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.9 / 3.10
    # `tomllib` is 3.11+. `requires-python` is ">=3.9" and the CI matrix runs 3.9, where a bare
    # `import tomllib` at module scope is a COLLECTION error -- which aborts the entire run rather
    # than skipping this file, so one docs assertion took the whole 3.9 suite down with it.
    tomllib = None  # type: ignore[assignment]

pytestmark = pytest.mark.skipif(
    tomllib is None,
    reason="tomllib is 3.11+; this docs check still runs on the 3.11 and 3.12 jobs",
)


def _scripts() -> set[str]:
    data = tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
    return set(data["project"]["scripts"])


def test_the_documented_count_is_the_real_count() -> None:
    doc = pathlib.Path("docs/why-best-open-repo.md").read_text(encoding="utf-8")
    m = re.search(r"\*\*(\d+)\*\* console scripts", doc)
    assert m, "the console-script claim moved or was reworded"
    assert int(m.group(1)) == len(_scripts())


def test_every_console_script_is_named_in_the_list() -> None:
    doc = pathlib.Path("docs/why-best-open-repo.md").read_text(encoding="utf-8")
    m = re.search(r"console scripts \((.*?)\) \*\*and\*\*", doc, re.S)
    assert m, "the console-script list moved or was reworded"
    listed = {
        ("untell" + name) if name.startswith("-") else name
        for name in re.findall(r"`([^`]+)`", m.group(1))
    }
    missing = _scripts() - listed
    assert not missing, f"shipped but not documented: {sorted(missing)}"


def test_the_list_names_nothing_that_does_not_ship() -> None:
    doc = pathlib.Path("docs/why-best-open-repo.md").read_text(encoding="utf-8")
    m = re.search(r"console scripts \((.*?)\) \*\*and\*\*", doc, re.S)
    listed = {
        ("untell" + name) if name.startswith("-") else name
        for name in re.findall(r"`([^`]+)`", m.group(1))
    }
    assert not listed - _scripts(), f"documented but not shipped: {sorted(listed - _scripts())}"
