"""Verify every [project.scripts] entry in pyproject.toml resolves (imports cleanly).

Run with the project venv:  ./.venv/Scripts/python.exe scripts/verify_console_scripts.py
Exits 0 only if every entry point's module imports and its callable attribute exists.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _declared_scripts() -> dict[str, str]:
    """[project.scripts] from pyproject.toml, or from the installed metadata before Python 3.11.

    `tomllib` is standard library from 3.11 only, and the package supports 3.9, so on 3.9 and 3.10
    this script died on its first import. The installed distribution's console_scripts entry points
    are the same table, as `pip install -e .` wrote it.
    """
    try:
        import tomllib
    except ModuleNotFoundError:
        from importlib.metadata import distribution

        return {
            ep.name: ep.value
            for ep in distribution("untell").entry_points
            if ep.group == "console_scripts"
        }
    with (ROOT / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)["project"]["scripts"]


def main() -> int:
    scripts = _declared_scripts()
    failures = []
    for name, target in sorted(scripts.items()):
        module_name, _, attr = target.partition(":")
        try:
            module = importlib.import_module(module_name)
            callable_ = getattr(module, attr, None)
            if callable_ is None:
                failures.append(f"{name} -> {target}: attribute {attr!r} missing in {module_name}")
                continue
            if not callable(callable_):
                failures.append(f"{name} -> {target}: {module_name}.{attr} is not callable")
                continue
            print(f"OK   {name:24s} -> {target}")
        except Exception as exc:  # noqa: BLE001 - report any import failure
            failures.append(f"{name} -> {target}: {type(exc).__name__}: {exc}")
            print(f"FAIL {name:24s} -> {target}: {type(exc).__name__}: {exc}")
    if failures:
        print(f"\n{len(failures)} entry point(s) FAILED to resolve")
        return 1
    print(f"\nAll {len(scripts)} console_scripts entry points resolve cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
