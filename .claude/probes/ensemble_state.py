import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.ensemble import EnsembleRewriter

out = {}
rw = EnsembleRewriter()
out["members"] = rw.member_names
out["available"] = rw.available()
t = "Moreover, the framework leverages robust solutions to deliver outcomes at scale."
try:
    r = rw.rewrite(t, {"max": 0.9, "tier": "lite"}, 0.30)
    out["ran"] = True
    out["changed"] = r.strip() != t
    out["nonempty"] = bool(r.strip())
    out["no_sentinel"] = "⟦" not in r
    out["sample"] = r[:60]
except Exception as e:
    out["ran"] = False
    out["error"] = f"{type(e).__name__}: {str(e)[:60]}"
print(json.dumps(out, indent=1))
