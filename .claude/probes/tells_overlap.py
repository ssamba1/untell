"""Tell overlap: a span matched by 2+ patterns must count ONCE, claimed by the longest."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.tells import score_tells

# "it is important to note that" is a formulaic_transition AND contains "important" (ai_vocab?)
probes = [
    "It is important to note that the system works well for every team here.",
    "Moreover, the results demonstrate a robust approach to the challenge.",
    "The data clearly shows that we are excited to share this groundbreaking result.",
]
out = {}
for t in probes:
    r = score_tells(t)
    out[t[:35]] = {"tells": r["tells"], "by_cat": {k: v for k, v in r.get("by_category", {}).items() if v},
                   "rate": round(r["tells_per_100w"], 1)}
print(json.dumps(out, indent=1))
