"""Issue #36 — optional-extra guard matrix: every optional dep fails cleanly.

Generic defect class: optional-dependency absence must yield a clean message,
never a traceback, across all entry points. This file is the acceptance test
for that contract: one subprocess row per optional dep, each running the
surface that uses the dep with that dep *genuinely absent* from ``sys.path``
(a meta_path finder raising ``ModuleNotFoundError`` — see
``_optional_extra_surfaces.py``) rather than relying on whatever is or is not
installed on this runner.

Each row asserts the same three things:

1. **no traceback** — the word ``Traceback`` must not appear in any output;
2. **a documented exit code** — the surface's own verdict code;
3. **a clean message** — a fragment naming the situation / the extra.

The peft row pins the wave-5/issue-#34 fix (``unavailable_reason`` names the
missing package *and* the ``untell[train]`` extra; the ``--rewriter local``
CLI path exits 2 with that reason); the remaining rows pin that the other
optional deps were already clean and stay that way.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# (blocked dep, surface, expected exit code, expected message fragment)
rows = [
    # peft — the known case, fixed at wave 5 / issue #34. CLI exit 2 + reason.
    pytest.param("peft", "peft_cli", 2, "untell[train]", marks=pytest.mark.slow),
    pytest.param("peft", "peft_unavailable_reason", 0, "needs the 'peft' package"),
    # sacremoses — transitive transformers-level need of the Marian/T5 tokenizer;
    # mt_pivot's availability must survive without it (transformers warns, untell
    # does not crash).
    pytest.param("sacremoses", "sacremoses_mtpivot", 0, "available: True"),
    # nltk — word_importance falls back to the built-in synonym map.
    pytest.param("nltk", "nltk_synonyms", 0, "kick off"),
    # torch — full-tier scoring honestly degrades to lite (never a traceback).
    pytest.param("torch", "torch_score", 0, "reported_tier: lite", marks=pytest.mark.slow),
    # spacy — the predicate-argument veto degrades to unavailable/'unknown'.
    pytest.param("spacy", "spacy_roles", 0, "roles.available: False"),
    # fastapi — the server entry itself (`untell-server`) must fail cleanly (exit 2,
    # one-line message naming the extra, no traceback), and `untell check` reports it.
    pytest.param("fastapi", "fastapi_server_cli", 2, "untell[server]"),
    pytest.param("fastapi", "fastapi_check", 0, "untell[server]", marks=pytest.mark.slow),
]
ROWS = rows


def _run_surface(dep: str, surface: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    # Blocked-import subprocesses must not write .pyc files (a killed subprocess
    # can otherwise leave a half-written bytecode file a later test trips over).
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # The dep-block is the independent variable, not the ambient machine: scrub
    # UNTELL_LITE_NO_TORCH so the torch row proves the *blocker* forces lite
    # rather than an env var the runner happened to export.
    env.pop("UNTELL_LITE_NO_TORCH", None)
    runner = ROOT / "tests" / "_optional_extra_surfaces.py"
    return subprocess.run(
        [sys.executable, str(runner), dep, surface],
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        env=env,
        timeout=240,
    )


@pytest.mark.parametrize("dep,surface,expected_rc,fragment", ROWS)
def test_optional_dep_fails_cleanly(dep, surface, expected_rc, fragment):
    p = _run_surface(dep, surface)
    output = p.stdout + p.stderr
    assert "Traceback" not in output, (
        f"{dep}/{surface} leaked a traceback (rc={p.returncode}):\n{output[:2000]}"
    )
    assert p.returncode == expected_rc, (
        f"{dep}/{surface} exited {p.returncode} (expected {expected_rc}):\n{output[:2000]}"
    )
    assert fragment in output, (
        f"{dep}/{surface} output missing fragment {fragment!r}:\n{output[:2000]}"
    )


def test_matrix_covers_the_intersection_of_issue_and_task_deps():
    """The six deps the issue/task names are all pinned (regression guard on the
    parametrize list itself, so a future dep is added with its own row)."""
    deps_pinned = {row.values[0] for row in ROWS}
    assert {"peft", "sacremoses", "nltk", "torch", "spacy", "fastapi"} == deps_pinned
