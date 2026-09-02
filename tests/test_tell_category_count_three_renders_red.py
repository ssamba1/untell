"""A tell category with count >= 3 renders red, not yellow.

rich_output.py:316: `"red" if count >= 3 else ("yellow" if count >= 2 else "white")`.
The mutation >= -> > demotes count==3 from red to yellow, silently lowering the
severity of the worst tells. The markup passed to Table.add_row is the
observable — count 3 must carry "[red]", count 2 must carry "[yellow]".
"""

import pytest

# `import rich` at module scope made this file a COLLECTION ERROR on the lite
# install, which ships zero ML — ten files did, so `pytest -q` was never green on
# the path CONTRIBUTING calls zero-dependency. A skip is the honest outcome: the
# test is not applicable, not broken. Install with `pip install 'untell[rich]'`
# to run it.
pytest.importorskip("rich")
from rich.table import Table

import untell.rich_output as rich_output


def _capture(monkeypatch, tells):
    captured = []
    monkeypatch.setattr(rich_output, "_RICH", True)
    monkeypatch.setattr(
        rich_output, "_CONSOLE", type("C", (), {"print": lambda self, *a, **k: None})()
    )
    real_add_row = Table.add_row
    monkeypatch.setattr(
        Table, "add_row", lambda self, *a, **k: captured.append(a) or real_add_row(self, *a, **k)
    )
    rich_output.print_tells_result(tells)
    return captured


def test_count_three_renders_red(monkeypatch):
    captured = _capture(monkeypatch, {"tells": 0, "tells_per_100w": 0.0,
                                      "by_category": {"hedging": 3}})
    assert ("[red]hedging[/]", "3") in captured, captured


def test_count_two_renders_yellow(monkeypatch):
    captured = _capture(monkeypatch, {"tells": 0, "tells_per_100w": 0.0,
                                      "by_category": {"hedging": 2}})
    assert ("[yellow]hedging[/]", "2") in captured, captured
