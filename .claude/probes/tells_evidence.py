"""by_evidence strength: known strong vs weak tells classified correctly."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.tells import score_tells

out = {}
# 'moreover' = formulaic_transition (strong per catalogue)
r = score_tells("Moreover, the framework delivers robust solutions for the team.")
out["strong_tell"] = r.get("by_evidence", {}).get("strong", 0)
# 'delve' = ai_vocab (strong), 'importantly' = filler?
r2 = score_tells("Delve into the data. Importantly, the results were clear to the team.")
out["ai_vocab_strong"] = r2.get("by_evidence", {}).get("strong", 0)
out["weak_present"] = r2.get("by_evidence", {}).get("weak", 0)
print(json.dumps(out, indent=1))
