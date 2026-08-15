import json, os, re
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.structural import _TRANSITIONS_RE

out = {}
# all 21 transition words fire at sentence start
words = ["Moreover", "Furthermore", "Additionally", "Overall", "In conclusion", "In summary",
         "Notably", "Importantly", "Consequently", "Therefore", "Thus", "Hence",
         "Ultimately", "Nevertheless", "Nonetheless", "Accordingly", "Subsequently",
         "Arguably", "Indeed", "Essentially", "In essence"]
out["all_21_fire"] = sum(1 for w in words if _TRANSITIONS_RE.match(f"{w}, the system works."))
# mid-sentence occurrence NOT stripped (pattern is ^-anchored)
out["mid_not_stripped"] = not _TRANSITIONS_RE.match("The system works, moreover, it is fast.")
# lowercase fires (IGNORECASE)
out["lowercase_fires"] = bool(_TRANSITIONS_RE.match("moreover, the system works."))
print(json.dumps(out, indent=1))
