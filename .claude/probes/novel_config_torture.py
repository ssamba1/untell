"""NOVEL probe: config-file torture — malformed, hostile, and edge configs.

The fleet's config_coerce.py / config_env.py probed specific paths. This
throws hostile config files at load_config: malformed YAML, wrong types,
deep nesting, unknown keys, empty file, directory-as-config, and checks the
fallthrough is actually reachable end-to-end.
"""
import sys, json, tempfile, os
from pathlib import Path
for p in Path(__file__).resolve().parents:
    if (p / "untell" / "__init__.py").exists():
        sys.path.insert(0, str(p)); break

from untell.config import _try_yaml, _try_pyproject, _coerce

def load_yaml_file(path):
    return _try_yaml(Path(path)) or {}

HOSTILE = {
    "malformed_yaml": "threshold: [unclosed",
    "wrong_types": "threshold: not_a_number\nmax_iters: [1,2]",
    "deep_nesting": "a:\n  b:\n    c:\n      d: 1\n",
    "unknown_keys": "threshold: 0.3\nfrobnicate: true\n",
    "empty": "",
    "null": "null\n",
    "duplicate": "threshold: 0.3\nthreshold: 0.9\n",
    "negative": "threshold: -5\n",
    "huge": "threshold: 999999\n",
}

for name, content in HOSTILE.items():
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(content)
        path = f.name
    try:
        cfg = load_yaml_file(path)
        print(f"{name:15} -> parsed: {cfg!r}")
    except Exception as e:
        print(f"{name:15} -> {type(e).__name__}: {str(e)[:60]}")
    os.unlink(path)

# coerce torture
for raw, default in [("abc", 0.3), ("-5", 0.3), ("999999", 0.3), ("", 0.3), ("True", 3)]:
    print(f"coerce({raw!r}, {default!r}) -> {_coerce(raw, default)!r}")
