"""NOVEL probe: full config load() through hostile files (end-to-end coercion).

_try_yaml parses anything; load() is where defaults/coercion apply. Does a
hostile value for a KNOWN key (threshold: 'abc') get coerced to default, and
does an out-of-range value (threshold: 999999) get clamped or pass through?
"""
import sys, tempfile, os
from pathlib import Path
for p in Path(__file__).resolve().parents:
    if (p / "untell" / "__init__.py").exists():
        sys.path.insert(0, str(p)); break

import untell.config as C

# load() reads pyproject.toml then ~/.config/untell.yaml then env. We can't
# redirect it, but we can probe _coerce against the config's own keys.
from untell.config import _coerce

# Simulate what load() does per known key: coerce the yaml value with the default
KNOWN = {
    "threshold": (0.30, float),
    "max_iters": (3, int),
    "best_of": (3, int),
    "tier": ("lite", str),
    "sim_bar": (0.76, float),
}

for key, (default, typ) in KNOWN.items():
    for raw in ("abc", "-5", "999999", "", "0.5", "lite", "full"):
        try:
            coerced = _coerce(raw, default, key)
            ok = isinstance(coerced, typ) or coerced is None
            print(f"{key}={raw!r:12} -> {coerced!r:12} type_ok={ok}")
        except Exception as e:
            print(f"{key}={raw!r:12} -> {type(e).__name__}: {str(e)[:40]}")
    print()
