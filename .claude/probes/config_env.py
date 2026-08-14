"""config.py: env var precedence, coercion, fallthrough invariants."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.config import load, get

out = {}
c = load()
out["loads"] = isinstance(c, dict)
out["has_keys"] = len(c) > 0
# get() with env override
os.environ["UNTELL_THRESHOLD"] = "0.42"
out["threshold_env"] = get("threshold", 0.3)
del os.environ["UNTELL_THRESHOLD"]
# fallback when unset
out["threshold_default"] = get("threshold", 0.3)
out["missing_key_default"] = get("no_such_key_xyz", "fallback")
print(json.dumps(out, indent=1))
