"""Skill entry point for `untell flagmath` — see :mod:`untell.evidence.cli`.

Runnable as ``python scripts/flagmath.py`` from the skill directory with no install: it puts the
package root on ``sys.path`` the same way every other script here does.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    for _p in Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            sys.path.insert(0, str(_p))
            break

from untell.evidence.cli import flagmath_main as main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
