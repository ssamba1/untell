import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.composite import CompositeRewriter

out = {}
rw = CompositeRewriter()
t = ("Moreover, the framework leverages robust solutions to deliver outcomes at scale. "
     "It is important to note that the results demonstrate significant improvement.")
r = rw.rewrite(t, {"max": 0.9, "tier": "lite"}, 0.3)
out["changed"] = r.strip() != t
out["nonempty"] = bool(r.strip())
out["no_sentinel"] = "⟦" not in r
out["no_fragment"] = all(len(s.split()) >= 3 for s in r.split(". ") if s)
out["sample"] = r[:70]
print(json.dumps(out, indent=1))
