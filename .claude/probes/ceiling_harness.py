"""measure_ceiling: repeats>1 yields stdev; per-run means present; corpus named."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from eval.ceiling import measure_ceiling

out = {}
r = measure_ceiling(tier="lite", max_iters=1, rewriter="structural", repeats=2, workers=1)
out["keys"] = sorted(r.keys())
out["has_stdev"] = "post_mean_max_stdev" in r
out["has_means"] = "run_post_means" in r and len(r.get("run_post_means", [])) == 2
out["n_texts"] = r.get("n")
print(json.dumps(out, indent=1))
