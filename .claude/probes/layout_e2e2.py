import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import untell_text

doc = """# Results

Moreover, the framework leverages a robust approach to deliver outcomes at scale. It is important to note that the data demonstrates a significant improvement across the entire platform.

```bash
pip install untell
```

In conclusion, we are excited to share these groundbreaking results with the community.
"""
r = untell_text(doc, tier="lite", max_iters=3, seed=1)
final = r.get("final") or ""
out = {
    "code_preserved": "pip install untell" in final,
    "header_preserved": "# Results" in final,
    "prose_changed": "Moreover" not in final,
    "final": final[:200],
    "stopped": r.get("stopped"),
}
print(json.dumps(out, indent=1))
