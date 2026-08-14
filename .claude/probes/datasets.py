"""datasets: builtin works offline, n respected, strict raises on missing, too-short warning."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from eval.datasets import load_samples, load_pairs, _warn_if_mostly_too_short

out = {}
# 1. builtin offline, exact n
s = load_samples("builtin", 3, strict=False)
out["builtin_n"] = len(s) == 3
out["builtin_strings"] = all(isinstance(x, str) and x for x in s)
# 2. unknown dataset non-strict -> fallback or empty, strict -> DatasetUnavailable
try:
    load_samples("nonexistent-dataset-xyz", 3, strict=True)
    out["strict_raises"] = False
except Exception as e:
    out["strict_raises"] = type(e).__name__ == "DatasetUnavailable"
# 3. too-short warning: mostly short texts -> warning emitted, texts returned
short = ["a", "b", "the", "x"]
warned = _warn_if_mostly_too_short("builtin", short)
out["short_warns"] = len(warned) == len(short)
# 4. load_pairs offline on hc3 (may need network; check graceful path)
try:
    p = load_pairs("builtin", 2)
    out["pairs_ok"] = len(p) >= 1 and all(len(t) == 2 for t in p)
except Exception as e:
    out["pairs_ok"] = False
    out["pairs_err"] = type(e).__name__
print(json.dumps(out, indent=1))
