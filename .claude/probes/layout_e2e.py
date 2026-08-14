"""End-to-end: untell_text on a multi-block markdown doc — fenced code, list, math, prose all preserved."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import untell_text

doc = """# Report Header

The system reads the input file and processes each record in sequence. Moreover, the framework leverages a robust approach to delivery at scale.

## Method

```python
def process(data):
    return [x * 2 for x in data]
```

- First item in the list
- Second item with *emphasis*

The results were significant, and it is important to note that the team agreed on the interpretation.

$$\int_0^1 x^2 dx = \frac{1}{3}$$
"""
r = untell_text(doc, tier="lite", max_iters=2, seed=1)
final = r.get("final") or ""
out = {
    "code_block_preserved": "```python" in final and "return [x * 2 for x in data]" in final,
    "math_preserved": "\int_0^1" in final,
    "list_markers_preserved": "- First item in the list" in final,
    "header_preserved": "# Report Header" in final,
    "prose_changed": "Moreover" not in final or "leverages" not in final,
    "no_sentinels_leaked": "⟦" not in final,
}
print(json.dumps(out, indent=1))
