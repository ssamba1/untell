"""quality CLI exits 2 on missing args, not 3.

quality.py:307: `main()` with fewer than 2 arguments logs the usage line and
returns 2 — the same usage-error convention as argparse. The mutation 2 -> 3
changes the exit code; the docstring documents the -h/--help fix history, so
the exact code is part of the contract.
"""
from untell.scripts.quality import main


def test_missing_args_exits_two():
    assert main([]) == 2


def test_single_arg_exits_two():
    assert main(["only-one"]) == 2
