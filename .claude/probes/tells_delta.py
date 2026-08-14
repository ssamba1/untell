"""tells_delta: reported tells_before/after must match score_tells on final text."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import untell_text
from untell.scripts.tells import score_tells

doc = ("Moreover, the framework leverages robust solutions to deliver outcomes at scale. "
       "It is important to note that the results demonstrate significant improvement. "
       "In conclusion, we are excited to share these findings.")
r = untell_text(doc, tier="lite", max_iters=3, seed=1)
out = {
    "reported_before": r.get("tells_before"),
    "computed_before": score_tells(doc).get("tells"),
    "reported_after": r.get("tells_after"),
    "computed_after": score_tells(r["final"]).get("tells"),
    "before_consistent": r.get("tells_before") == score_tells(doc).get("tells"),
    "after_consistent": r.get("tells_after") == score_tells(r["final"]).get("tells"),
}
print(json.dumps(out, indent=1))
