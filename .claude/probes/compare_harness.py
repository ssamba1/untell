"""compare_humanizers: each technique returns per-technique scores with corpus named."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from eval.compare_humanizers import compare, _SAMPLE

out = {}
r = compare(list(_SAMPLE), tier="lite", corpus="built-in sample")
out["keys"] = sorted(r.keys())
out["corpus_named"] = r.get("corpus") == "built-in sample"
out["has_techniques"] = "techniques" in r or "results" in r
# per-technique rows have score + tells
import sys
sys.path.insert(0, "eval")
print(json.dumps({k: (v if not isinstance(v, list) else f"list[{len(v)}]") for k, v in r.items()}, indent=1))
