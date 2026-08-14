import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.verify import verify

out = {}
r = verify("The system reads the file and processes the records in order.", tier="lite")
out["keys"] = sorted(r.keys())
out["has_config"] = "configured" in r
out["passes_all_type"] = type(r.get("passes_all")).__name__
# checkers tally: local:max excluded
res = r.get("results", {})
out["n_results"] = len(res)
out["local_max_excluded"] = not any(k.startswith("local:max") for k in res) or "local:max (lite)" not in res
out["threshold_reported"] = "threshold" in r
print(json.dumps(out, indent=1))
