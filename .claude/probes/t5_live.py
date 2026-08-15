"""t5_paraphrase live: rewrite produces a real paraphrase, deterministic beam."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.t5_paraphrase import T5ParaphraseRewriter

out = {}
try:
    rw = T5ParaphraseRewriter()
    if rw.available():
        t = "The system reads the file and processes every record in order."
        r1 = rw.rewrite(t, {"max": 0.9}, 0.3)
        r2 = rw.rewrite(t, {"max": 0.9}, 0.3)
        out["available"] = True
        out["deterministic"] = r1 == r2
        out["changed"] = r1.strip() != t
        out["nonempty"] = bool(r1.strip())
        out["sample"] = r1.strip()[:70]
    else:
        out["available"] = False
        out["reason"] = "T5 deps not importable in this env"
except Exception as e:
    out["available"] = False
    out["error"] = f"{type(e).__name__}: {str(e)[:80]}"
print(json.dumps(out, indent=1))
