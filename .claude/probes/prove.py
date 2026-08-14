"""prove: structure contract via stubs — no model loading."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
import eval.prove as P
import untell.scripts.verify as V
import untell.scripts.run as R

orig_verify = P.verify
orig_text = R.untell_text
V.verify = lambda text, threshold=0.3: {"passes_all": False, "results": [{"name": "x", "passed": False}]}
R.untell_text = lambda *a, **k: {"error": "no rewriter configured", "iterations": 0, "final": None}
try:
    r = P.prove("Some text to prove.")
    out = {
        "error_structured": "error" in r and "before" in r,
        "before_passes": r.get("before", {}).get("passes_all") is False,
        "keys": sorted(r.keys()),
    }
    # success path
    R.untell_text = lambda *a, **k: {"final": "humanized out", "iterations": 2, "error": None}
    r2 = P.prove("Some text to prove.")
    out["success_keys"] = sorted(r2.keys())
    out["passes_after"] = "passes_all" in r2
finally:
    P.verify = orig_verify
    R.untell_text = orig_text
print(json.dumps(out, indent=1))
