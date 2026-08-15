import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.tells import score_tells

out = {}
# NBSP folded: 'in\u00a0conclusion' counts as the tell
r = score_tells("In\u00a0conclusion, the results are significant and robust.")
out["nbsp_folded"] = r["tells"] >= 1
# ZWSP scrubbed: word count not shattered
r2 = score_tells("The system\u200b reads\u200b the\u200b file\u200b and\u200b processes\u200b the\u200b records.")
out["zwsp_scrubbed_words"] = r2["words"] == 9
# plain count
r3 = score_tells("Moreover, the framework leverages robust solutions.")
out["plain_tells"] = r3["tells"]
out["per_100w_exact"] = abs(r3["tells_per_100w"] - round(r3["tells"] / r3["words"] * 100, 2)) < 1e-9
print(json.dumps(out, indent=1))
