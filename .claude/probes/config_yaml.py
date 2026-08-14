"""config: pyproject [tool.untell] and untell.yaml precedence over defaults."""
import json, os, tempfile, pathlib
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.config import load, get

out = {}
# 1. load() returns dict
c = load()
out["loads_dict"] = isinstance(c, dict)
# 2. get() default
out["default"] = get("threshold", 0.3)
# 3. env override wins
os.environ["UNTELL_THRESHOLD"] = "0.55"
out["env_wins"] = get("threshold", 0.3) == 0.55
del os.environ["UNTELL_THRESHOLD"]
# 4. pyproject [tool.untell] read (if present in repo)
import tomllib
try:
    with open("pyproject.toml", "rb") as f:
        pp = tomllib.load(f)
    untell_pp = pp.get("tool", {}).get("untell", {})
    out["pyproject_has_config"] = bool(untell_pp)
    out["pyproject_keys"] = sorted(untell_pp.keys())
except FileNotFoundError:
    out["pyproject_has_config"] = False
print(json.dumps(out, indent=1))
