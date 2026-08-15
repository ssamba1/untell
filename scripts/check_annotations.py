"""Check that every type annotation in untell/ resolves (no undefined names in annotations).

Ruff catches undefined names in *runtime* annotations, but with
`from __future__ import annotations` (used in most untell/ modules) annotations
are never evaluated, so a typo like `-> list[Strin]` or a forgotten import in an
annotation sails through lint and only explodes when something calls
typing.get_type_hints() (pydantic models, dataclasses with resolve hooks, etc.).

This script imports each untell/ module and evaluates every public function /
method / class annotation via typing.get_type_hints(), which forces forward-ref
resolution and surfaces undefined annotation names.

Run: ./.venv/Scripts/python.exe scripts/check_annotations.py [--package PKG]
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import pkgutil
import sys
import typing


def _walk_modules(pkg) -> list:
    mods = []
    for m in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        if m.ispkg:
            mods.extend(_walk_modules(importlib.import_module(m.name)))
        else:
            mods.append(m.name)
    return mods


def _obj_annotations(obj, owner_name: str, problems: list) -> None:
    """Resolve annotations on a callable/class, recursing into methods."""
    if isinstance(obj, type):
        try:
            typing.get_type_hints(obj)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{owner_name}: class annotations: {type(exc).__name__}: {exc}")
        for mname, mval in vars(obj).items():
            if mname.startswith("__") and mname not in ("__init__", "__new__"):
                continue
            if callable(mval):
                _obj_annotations(mval, f"{owner_name}.{mname}", problems)
    elif callable(obj):
        try:
            typing.get_type_hints(obj)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{owner_name}: {type(exc).__name__}: {exc}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--package",
        default="untell",
        help="package to walk (default: untell)",
    )
    args = ap.parse_args(argv)
    try:
        pkg = importlib.import_module(args.package)
    except Exception as exc:  # noqa: BLE001
        print(f"cannot import {args.package!r}: {type(exc).__name__}: {exc}")
        return 1
    problems = []
    failed_imports = []
    for mod_name in sorted(_walk_modules(pkg)):
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:  # noqa: BLE001
            failed_imports.append(f"{mod_name}: {type(exc).__name__}: {exc}")
            continue
        for name, obj in vars(mod).items():
            if name.startswith("_"):
                continue
            if isinstance(obj, type) and obj.__module__ != mod_name:
                continue  # imported class, not defined here
            # Skip typing special forms and instances of arbitrary classes
            # (e.g. FastAPI app objects) — only functions and locally-defined
            # classes carry annotations worth resolving.
            if isinstance(obj, type):
                _obj_annotations(obj, f"{mod_name}.{name}", problems)
            elif (
                inspect.isfunction(obj) or inspect.isclass(obj)
            ) and getattr(obj, "__module__", None) == mod_name:
                # Locally-defined functions only: resolving annotations on
                # *imported* callables (e.g. pydantic.Field) trips over the
                # library's own lazy forward refs (NameError: JsonValue) and
                # reports false positives. The module that defines a callable
                # is the one that audits it.
                _obj_annotations(obj, f"{mod_name}.{name}", problems)
    if failed_imports:
        print("MODULE IMPORT FAILURES:")
        for f in failed_imports:
            print("  " + f)
    if problems:
        print("\nANNOTATION PROBLEMS:")
        for p in problems:
            print("  " + p)
    if failed_imports or problems:
        print(f"\n{len(failed_imports)} import failures, {len(problems)} annotation problems")
        return 1
    print(f"All {args.package} module imports and type annotations resolve cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
