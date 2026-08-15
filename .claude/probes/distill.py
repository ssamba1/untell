import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from training.distill import distill, _PROMPT

out = {}
r = distill(dataset="sample", n=2, tier="lite")
out["kept"] = r["kept"]
out["total"] = r["total"]
out["rows_have_prompt"] = all("prompt" in row and "humanized" in row for row in r["rows"])
out["prompt_has_text"] = all("{text}" not in row["prompt"] for row in r["rows"])
out["sample_humanized"] = r["rows"][0]["humanized"][:50] if r["rows"] else None
print(json.dumps(out, indent=1))
