"""A worked example nothing runs is a claim about the code, not a check on it.

`untell/calibrate.py` opened with a three-line example showing `calibrate()` turning five scores
into a threshold of 0.3. It cannot: twenty documents is the floor for any alpha, and the call returns
`None`, so the example raised `TypeError` on the subscript. It had never raised it anywhere, because
this repository had no doctest configuration — not in `pyproject.toml`, not in a pytest ini, not in
CI — so the only doctest in `untell/` and `eval/` had never been executed.

That is the same defect this project documents in other people's work, in the module whose subject is
not trusting a number you have not run. The example was also the most load-bearing kind: a reader
checking what `calibrate()` returns for a small sample would have been told it returns a threshold,
when refusing small samples is the module's whole design.

So doctests run now, and this file is what runs them. It collects every module under `untell/` and
`eval/` rather than naming the one that had an example, because the failure mode being fixed is an
example nobody thought to check.
"""

from __future__ import annotations

import doctest
import importlib
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
ROOTS = ("untell", "eval")


def _modules() -> list[str]:
    out = []
    for root in ROOTS:
        for path in sorted((REPO / root).rglob("*.py")):
            if path.name == "__init__.py":
                continue
            out.append(str(path.relative_to(REPO).with_suffix("")).replace("/", "."))
    return out


MODULES = _modules()


@pytest.mark.parametrize("name", MODULES)
def test_a_modules_doctests_pass(name):
    try:
        module = importlib.import_module(name)
    except ImportError as exc:
        # Optional heavy dependencies (torch and friends) are not installed in every environment.
        # Skipping is right for those; failing would make this file's verdict depend on the machine.
        pytest.skip(f"{name} not importable here: {exc}")
    result = doctest.testmod(module, verbose=False, report=True)
    assert result.failed == 0, (
        f"{name}: {result.failed} of {result.attempted} worked example(s) failed — see the report "
        f"above. An example that does not run is documentation of behaviour the code may not have.")


def test_the_sweep_actually_reaches_the_module_that_had_the_broken_example():
    """Guards the guard. A collector that silently found nothing would pass every case above.

    `untell.calibrate` is named here because it is where the defect was; the parametrisation above
    is deliberately not limited to it.
    """
    assert "untell.calibrate" in MODULES
    assert len(MODULES) > 50, f"only {len(MODULES)} modules collected; the sweep is not sweeping"


def test_at_least_one_worked_example_exists_to_run():
    """A suite that runs zero examples passes forever and checks nothing.

    This is the assertion that would have failed if the fix had been to *delete* the broken example
    rather than correct it — which is the tempting fix and the wrong one.
    """
    found = 0
    for name in MODULES:
        try:
            module = importlib.import_module(name)
        except ImportError:
            continue
        found += len(doctest.DocTestFinder().find(module))
    examples = 0
    for name in MODULES:
        try:
            module = importlib.import_module(name)
        except ImportError:
            continue
        examples += sum(len(t.examples) for t in doctest.DocTestFinder().find(module))
    assert examples >= 5, f"only {examples} runnable examples across {found} docstrings"
