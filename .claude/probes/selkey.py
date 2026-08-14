"""selection_key edge invariants: NaN max/mean, missing keys, None values."""
import json, math
from untell.rewriter.base import selection_key

out = {}
cases = {
    "normal": {"max": 0.5, "mean": 0.3},
    "max_nan": {"max": float("nan"), "mean": 0.3},
    "mean_nan": {"max": 0.5, "mean": float("nan")},
    "no_mean": {"max": 0.5, "detectors": {"a": 0.2, "b": 0.4}},
    "no_mean_with_err": {"max": 0.5, "detectors": {"a": 0.2, "b": 0.4, "c__error": "boom"}},
    "mean_bool": {"max": 0.5, "mean": True},
    "no_max": {"mean": 0.3},
}
for name, c in cases.items():
    try:
        out[name] = selection_key(c)
    except Exception as e:
        out[name] = f"{type(e).__name__}: {e}"
print(json.dumps(out, indent=1))
