"""Contract test: .claude/instruments.json keys are real RECIPES.

Pins issue #17's verification: every instrument key must name a recipe that
`.claude/research.py` knows. An instrument for a recipe that does not exist is
calibration data for nothing, and a RECIPES entry silently losing its instrument
is a gap the ledger would otherwise not notice.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude"))
import research as R  # noqa: E402

INSTRUMENTS = Path(__file__).resolve().parent.parent / ".claude" / "instruments.json"


def test_instrument_keys_are_recipes() -> None:
    instruments = json.loads(INSTRUMENTS.read_text(encoding="utf-8"))
    unknown = sorted(set(instruments) - set(R.RECIPES))
    assert not unknown, (
        "instruments.json names recipes research.py does not know: " + ", ".join(unknown)
    )


def test_calibrated_recipes_have_instruments() -> None:
    instruments = json.loads(INSTRUMENTS.read_text(encoding="utf-8"))
    for name in ("lite-builtin", "lite-hc3", "lite-hc3-ensemble"):
        assert name in instruments, (
            f"expected calibrated recipe {name!r} in instruments.json"
        )
