"""The static check proves the bootstrap exists. This one proves the script runs.

Its sibling, `test_the_zero_dep_scripts_run_from_a_bare_interpreter.py`, reads source and checks
the sys.path bootstrap sits above the package imports. That is the defect that shipped twice, so
it earns its place — but a file can satisfy it and still die at runtime on a machine with nothing
installed, and only CI's installer jobs would say so.

`python -S` is the missing piece: it skips site processing, so the editable install that hides
this on every developer machine is not on the path. VERIFIED — `-S -c "import untell"` raises
ModuleNotFoundError here, which is the same condition CI's bare interpreter provides.

Each script is run against a copy of the package tree from an unrelated cwd, with real input,
and has to produce output rather than a traceback. The lite path is stdlib-only, so nothing
third-party is needed to answer.

MEASURED when this was written, on eleven skill scripts: all eleven ran, and the ones needing an
optional dependency said so in their output rather than failing — `quality` fell back to
token_overlap with confidence "low", `roles` reported `available: false` with a note, `entailment`
the same. `preserve` locked all three of a citation, a percentage and a filename.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

AI = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "It significantly improves overall efficiency and accuracy across the evaluated corpus."
)
REWRITE = "The framework uses solid methods to deliver outcomes at scale, and efficiency improves."

# (script, argv). Two-argument scripts compare an original against a rewrite.
CASES = [
    ("tells.py", [AI]),
    ("scrub.py", [AI]),
    ("sentences.py", [AI]),
    ("preserve.py", ["See Smith (2020) for the 42% figure in config.yaml."]),
    ("numerals.py", [AI, REWRITE]),
    ("hedges.py", [AI, REWRITE]),
    ("quality.py", [AI, REWRITE]),
    ("roles.py", [AI, REWRITE]),
    ("entailment.py", [AI, REWRITE]),
]


@pytest.fixture(scope="module")
def bare_tree(tmp_path_factory) -> Path:
    """A copy of the package, so nothing here can pick the repo up by being next to it."""
    root = tmp_path_factory.mktemp("zerodep")
    shutil.copytree(REPO / "untell", root / "untell", ignore=shutil.ignore_patterns("__pycache__"))
    return root


def test_the_isolation_actually_isolates(bare_tree: Path):
    """Guards the guard. If -S stopped hiding the install, every test below would pass trivially."""
    probe = subprocess.run(
        [sys.executable, "-S", "-c", "import untell"],
        capture_output=True,
        text=True,
        cwd=bare_tree.parent,
    )
    assert probe.returncode != 0 and "ModuleNotFoundError" in probe.stderr, (
        "`python -S` can still import untell, so these tests are not reproducing the "
        "zero-dependency condition and would pass even with the bootstrap removed"
    )


@pytest.mark.parametrize("script,argv", CASES, ids=[c[0] for c in CASES])
def test_the_script_runs_with_nothing_installed(bare_tree: Path, script: str, argv: list[str]):
    run = subprocess.run(
        [sys.executable, "-S", str(bare_tree / "untell" / "scripts" / script), *argv],
        capture_output=True,
        text=True,
        cwd=bare_tree.parent,
        timeout=180,
    )

    assert "ModuleNotFoundError" not in run.stderr, (
        f"{script} cannot import its own package on a bare interpreter:\n{run.stderr[-400:]}"
    )
    assert "Traceback" not in run.stderr, f"{script} raised:\n{run.stderr[-400:]}"
    assert run.stdout.strip(), f"{script} produced no output (stderr: {run.stderr[-200:]})"


def test_an_optional_dependency_is_reported_not_faked(bare_tree: Path):
    """Degrading is fine; degrading silently is not — the caller has to be able to tell."""
    run = subprocess.run(
        [sys.executable, "-S", str(bare_tree / "untell" / "scripts" / "roles.py"), AI, REWRITE],
        capture_output=True,
        text=True,
        cwd=bare_tree.parent,
        timeout=180,
    )
    assert '"available": false' in run.stdout, (
        "roles.py answered without saying whether the parser it needs was there; a caller cannot "
        f"tell a real verdict from an unavailable one: {run.stdout[:200]}"
    )
