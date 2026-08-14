"""config.get coercion: env strings converted to the default's type; bad values fall back."""
import json, os
from untell.config import get

out = {}
# int coercion
os.environ["UNTELL_MAX_ITERS"] = "7"
out["int_env"] = get("max_iters", 3)
del os.environ["UNTELL_MAX_ITERS"]
# float coercion
os.environ["UNTELL_THRESHOLD"] = "0.42"
out["float_env"] = get("threshold", 0.3)
del os.environ["UNTELL_THRESHOLD"]
# bad float -> default
os.environ["UNTELL_THRESHOLD"] = "not-a-number"
out["bad_float"] = get("threshold", 0.3)
del os.environ["UNTELL_THRESHOLD"]
# string passthrough
os.environ["UNTELL_HOST"] = "0.0.0.0"
out["str_env"] = get("host", "127.0.0.1")
del os.environ["UNTELL_HOST"]
print(json.dumps(out, indent=1))
