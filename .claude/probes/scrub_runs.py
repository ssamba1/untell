"""scrub must run even when the rewriter declines (below-threshold text with hidden chars)."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import untell_text

dirty = "The team ran the experiment and recorded the results. " * 6 + "\u200b\u200b\u200b" + " They published the findings."
r = untell_text(dirty, tier="lite", max_iters=2, seed=1)
out = {
    "zwsp_removed": "\u200b" not in (r.get("final") or ""),
    "changed": r.get("changed"),
    "final_snippet": (r.get("final") or "")[150:200],
}
print(json.dumps(out, indent=1))
