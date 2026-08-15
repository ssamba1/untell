import json
from untell.rewriter.base import selection_key

out = {}
out["normal"] = selection_key({"max": 0.5, "mean": 0.3}) == (0.5, 0.3)
out["no_mean_fallback"] = selection_key({"max": 0.5}) == (0.5, 0.5)
out["bool_mean_excluded"] = selection_key({"max": 0.5, "mean": True}) == (0.5, 0.5)
out["lexicographic"] = (0.4, 0.9) < selection_key({"max": 0.5, "mean": 0.1}) < (0.6, 0.0)
print(json.dumps(out, indent=1))
