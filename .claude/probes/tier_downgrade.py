import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.score import score_text

out = {}
t = "The system reads the file and processes the records in order."
# heavy tier with NO_TORCH -> downgrade path
r = score_text(t, tier="heavy")
out["heavy_tier"] = r.get("tier")
out["heavy_requested"] = r.get("tier_requested")
out["heavy_warning"] = str(r.get("warning"))[:80] if r.get("warning") else None
out["heavy_scored"] = r.get("scored")
# full tier normal
r2 = score_text(t, tier="full")
out["full_tier"] = r2.get("tier")
out["full_max"] = r2.get("max")
print(json.dumps(out, indent=1))
