"""Pin the lint/import-hygiene tooling under scripts/ to working behavior.

- Every [project.scripts] entry in pyproject.toml must resolve (module imports,
  callable attribute exists) — scripts/verify_console_scripts.py is the gate.
- scripts/check_annotations.py must pass on the clean tree (regression: it used
  to crash on a missing `import inspect`, then exit 1 on a pydantic-internal
  false positive), and must still catch a genuinely undefined annotation name —
  that is the entire reason it exists.

The tools run as subprocesses with the project venv's python (sys.executable)
and a cleared PYTHONPATH: the Hermes desktop app injects its own site-packages
into PYTHONPATH, which shadows the project venv and breaks pydantic/fastapi
imports, so the untell-server / untell-mcp entry points would fail for the wrong
reason. The project is not a src-layout, so nothing needs PYTHONPATH set.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "scripts" / "check_annotations.py"
VERIFIER = ROOT / "scripts" / "verify_console_scripts.py"


def _run(
    script: Path,
    *args: str,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items()}
    env["PYTHONPATH"] = ""
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120,
    )


def test_every_console_scripts_entry_resolves() -> None:
    proc = _run(VERIFIER)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "FAIL" not in proc.stdout
    assert "entry points resolve cleanly" in proc.stdout


def test_annotations_checker_passes_on_clean_tree() -> None:
    proc = _run(CHECKER)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "resolve cleanly" in proc.stdout


def test_annotations_checker_detects_undefined_annotation_name(tmp_path) -> None:
    pkg = tmp_path / "probe_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "poisoned.py").write_text(
        textwrap.dedent(
            """\
            from __future__ import annotations

            def broken(x: Strin) -> None:  # Strin is defined nowhere
                return None
            """
        ),
        encoding="utf-8",
    )
    proc = _run(
        CHECKER,
        "--package",
        "probe_pkg",
        env_extra={"PYTHONPATH": str(tmp_path)},
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "NameError" in proc.stdout
    assert "Strin" in proc.stdout


def test_annotations_checker_ignores_imported_callables(tmp_path) -> None:
    """pydantic.Field's own annotations reference a lazy name (JsonValue) that
    get_type_hints cannot resolve outside pydantic's internals. The checker must
    audit only objects DEFINED in the walked package, or every module that
    imports Field would report a false positive.
    """
    pkg = tmp_path / "probe_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "uses_field.py").write_text(
        textwrap.dedent(
            """\
            from pydantic import Field

            def make(**kw):
                return Field(**kw)
            """
        ),
        encoding="utf-8",
    )
    proc = _run(
        CHECKER,
        "--package",
        "probe_pkg",
        env_extra={"PYTHONPATH": str(tmp_path)},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "JsonValue" not in proc.stdout
