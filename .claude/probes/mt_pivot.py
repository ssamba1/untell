"""mt_pivot: sentinel survival + determinism + layout preservation."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.mt_pivot import MTPivotRewriter
from untell.scripts.preserve import lock

rw = MTPivotRewriter()
if not rw.available():
    print(json.dumps({"available": False}))
else:
    text = "The system reads the file first. It parses each record carefully. The loader writes them to the store."
    masked, mapping = lock(text)
    out = rw.rewrite(masked, {"tier": "lite"}, 0.3)
    out2 = rw.rewrite(masked, {"tier": "lite"}, 0.3)
    sentinels = [k for k in mapping]
    survived = all(s in out for s in sentinels)
    print(json.dumps({
        "available": True,
        "deterministic": out == out2,
        "sentinel_survival": survived,
        "changed": out != masked,
        "out_snippet": out[:70],
    }, indent=1))
