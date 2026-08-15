import json, os, re
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.structural import _HEDGE_RE, _TRANSITIONS_RE, _PARTICIPIAL_RE

out = {}
# HEDGE: known hedge phrases
hedges = [
    "It is important to note that the results are significant.",
    "The findings demonstrate that the approach works well.",
    "The system facilitates seamless integration of the components.",
    "Moreover, the framework leverages robust solutions.",
]
out["hedge_fires"] = sum(1 for h in hedges if _HEDGE_RE.search(h))
# TRANSITIONS: known transition openers
trans = [
    "Moreover, the system reads the file.",
    "Additionally, the parser splits it.",
    "In conclusion, the results are clear.",
    "However, the loader failed.",
]
out["trans_fires"] = sum(1 for t in trans if _TRANSITIONS_RE.search(t))
# PARTICIPIAL: known trailer
parts = [
    "The results are clear, underscoring its importance.",
    "The data is clean, highlighting the improvement.",
    "The system works, demonstrating the effect.",
]
out["part_fires"] = sum(1 for p in parts if _PARTICIPIAL_RE.search(p))
# plain text no false fires
plain = ["The system reads the file and processes the records.", "The team met on Tuesday to review the plan."]
out["plain_hedge_fp"] = sum(1 for p in plain if _HEDGE_RE.search(p))
out["plain_trans_fp"] = sum(1 for p in plain if _TRANSITIONS_RE.search(p))
out["plain_part_fp"] = sum(1 for p in plain if _PARTICIPIAL_RE.search(p))
print(json.dumps(out, indent=1))
