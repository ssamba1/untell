"""tell rate vs length: is the rate stable for REPEATED identical tells (the degenerate case)?"""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.tells import score_tells

# A sentence with 1 tell repeated k times
base = "It is important to note that the system works well here. "
out = {}
for k in (1, 2, 4, 8, 12):
    t = base * k
    r = score_tells(t)
    out[k] = {"words": r["words"], "tells": r["tells"], "rate": round(r["tells_per_100w"], 2)}
print(json.dumps(out, indent=1))
