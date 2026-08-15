import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.ensemble import EnsembleRewriter

out = {}
# member composition in this env
rw = EnsembleRewriter()
out["members"] = rw.member_names
out["always_available"] = rw.available() is True
# ensemble runs and returns valid text
try:
    r = rw.rewrite("Moreover, the framework leverages robust solutions for every team. "
                   "The system reads the file and processes the records in order. "
                   "It is important to note that the results were significant.",
                   {"tier": "lite"}, 0.3)
    out["ran"] = bool(r.strip())
    out["changed"] = "Moreover" not in r
    out["no_sentinel"] = "⟦" not in r
except Exception as e:
    out["ran"] = False
    out["error"] = f"{type(e).__name__}: {str(e)[:60]}"
print(json.dumps(out, indent=1))
