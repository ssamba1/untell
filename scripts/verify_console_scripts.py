"""Verify every [project.scripts] entry in pyproject.toml resolves (imports cleanly).

Run with the project venv:  ./.venv/Scripts/python.exe scripts/verify_console_scripts.py
Exits 0 only if every entry point's module imports and its callable attribute exists.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    with (ROOT / "pyproject.toml").open("rb") as f:
        pyproject = tomllib.load(f)
    scripts = pyproject["project"]["scripts"]
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
