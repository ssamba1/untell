"""Polish stage live: polish=True changes output vs False; similarity gate still applies."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import untell_text

doc = ("Moreover, the framework leverages robust solutions to deliver outcomes at scale. "
       "It is important to note that the results demonstrate significant improvement.")
out = {}
r_off = untell_text(doc, tier="lite", max_iters=2, seed=1, polish=False)
r_on = untell_text(doc, tier="lite", max_iters=2, seed=1, polish=True)
out["polish_changes"] = r_off["final"] != r_on["final"] or r_off.get("iterations") != r_on.get("iterations")
out["both_valid"] = bool(r_off["final"].strip()) and bool(r_on["final"].strip())
out["similarity_reported"] = "similarity" in r_on
out["off_final"] = r_off["final"][:60]
out["on_final"] = r_on["final"][:60]
print(json.dumps(out, indent=1))
