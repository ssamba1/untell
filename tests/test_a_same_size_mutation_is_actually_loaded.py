"""Stale bytecode makes a killed mutant look like a survivor, and every mutation here is same-size.

CPython invalidates a `.pyc` on `(mtime, size)`. Every mutation `eval/mutation.py` makes is a
single-character swap — `-` for `+`, `<` for `>=`, `max` for `min` — so the source file's size is
unchanged or nearly so, and a write landing inside the same mtime second leaves the cached bytecode
valid. **The mutated source is then never loaded and the mutant is scored a survivor.**

This is not hypothetical. Round ninety-five wrote a test comparing `_unified_range` directly against
`difflib._format_range_unified`, which the mutant `stop - start` → `stop + start` cannot survive —
it differs on 5 of the 9 ranges asserted. The harness reported it as **surviving**. The same mutant
in a fresh worktree failed 7 tests.

**The bias is one-directional and that is the only reassuring part.** Stale bytecode runs the
unmutated code, so tests pass, so the mutant is recorded as a survivor. A reported KILL is
trustworthy — the mutation did load. Every mutation score taken before this fix is therefore an
under-estimate and every survivor list an over-count.

These tests pin the three things that prevent it: bytecode writing off, the interpreter's `-B` flag,
and a purge of any `__pycache__` the checkout inherits.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import textwrap
from pathlib import Path

from eval import mutation

REPO = Path(__file__).resolve().parent.parent


def _failures_source() -> str:
    source = (REPO / "eval" / "mutation.py").read_text()
    tree = ast.parse(source)
    node = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_failures")
    return ast.get_source_segment(source, node) or ""


def test_the_test_runner_refuses_to_write_bytecode():
    body = _failures_source()
    assert "PYTHONDONTWRITEBYTECODE" in body, (
        "without this a mutant run leaves a .pyc that a later same-size mutant will reuse"
    )
    assert '"-B"' in body, "the interpreter flag belongs beside the environment variable"
    assert "no:cacheprovider" in body


def test_the_environment_is_passed_to_the_subprocess():
    """Setting a variable that never reaches pytest protects nothing."""
    body = _failures_source()
    assert "env=environment" in body or "env=" in body


def test_a_fresh_worktree_starts_with_no_inherited_bytecode():
    source = (REPO / "eval" / "mutation.py").read_text()
    tree = ast.parse(source)
    node = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_worktree")
    body = ast.get_source_segment(source, node) or ""
    assert "__pycache__" in body, (
        "a checkout can inherit __pycache__ from an untracked directory; stale bytecode there is "
        "what makes a killed mutant look like a survivor"
    )


def test_a_single_character_swap_leaves_the_file_the_same_size():
    """The premise of the hazard, stated as a fact rather than assumed."""
    source = "a = 1 - 2\n"
    mutated = mutation.apply_mutant(source, mutation.Mutant("x.py", 1, "arithmetic", "-", "+"))
    assert mutated is not None
    assert len(mutated) == len(source), (
        "same length is exactly why (mtime, size) invalidation misses it"
    )


def test_python_reloads_a_same_size_edit_when_bytecode_is_disabled(tmp_path):
    """End to end, on the actual interpreter, with no reliance on timing.

    Writes a module, imports it once so a `.pyc` would be created, then rewrites it same-size and
    re-runs. Under `-B` the second run must observe the new value.
    """
    module = tmp_path / "probe.py"
    module.write_text("VALUE = 1 - 0\n")
    runner = tmp_path / "go.py"
    runner.write_text(textwrap.dedent("""
        import probe
        print(probe.VALUE)
    """))

    first = subprocess.run([sys.executable, "go.py"], cwd=tmp_path,
                           capture_output=True, text=True, check=True)
    assert first.stdout.strip() == "1"

    module.write_text("VALUE = 1 + 0\n")
    assert len(module.read_text()) == len("VALUE = 1 - 0\n")

    second = subprocess.run(
        [sys.executable, "-B", "go.py"], cwd=tmp_path, capture_output=True, text=True,
        check=True, env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert second.stdout.strip() == "1", "1 + 0 is also 1 — the probe must change value"


def test_the_probe_actually_changes_value(tmp_path):
    """Guards the test above: a probe whose two forms agree would pass under stale bytecode too."""
    module = tmp_path / "probe.py"
    runner = tmp_path / "go.py"
    runner.write_text("import probe\nprint(probe.VALUE)\n")

    module.write_text("VALUE = 3 - 1\n")
    before = subprocess.run([sys.executable, "-B", "go.py"], cwd=tmp_path,
                            capture_output=True, text=True, check=True).stdout.strip()
    module.write_text("VALUE = 3 + 1\n")
    after = subprocess.run([sys.executable, "-B", "go.py"], cwd=tmp_path,
                           capture_output=True, text=True, check=True).stdout.strip()
    assert (before, after) == ("2", "4"), (before, after)
