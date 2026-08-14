"""prove: structure contract via stubs on prove's own bindings."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
import eval.prove as P

orig_text = P.untell_text
orig_verify = P.verify
P.verify = lambda text, threshold=0.3: {"passes_all": False, "results": [{"name": "x", "passed": False}]}
try:
    P.untell_text = lambda *a, **k: {"error": "no rewriter configured", "iterations": 0, "final": None}
    r = P.prove("Some text to prove.")
    out = {
        "error_structured": "error" in r and "before" in r,
        "before_passes": r.get("before", {}).get("passes_all") is False,
        "error_keys": sorted(r.keys()),
    }
    P.untell_text = lambda *a, **k: {"final": "humanized out", "iterations": 2}
    r2 = P.prove("Some text to prove.")
    out["success_keys"] = sorted(r2.keys())
    out["passes_after"] = "passes_all" in r2 and r2.get("passes_all") is False
    out["humanized_flow"] = r2.get("humanized") == "humanized out"
finally:
    P.untell_text = orig_text
    P.verify = orig_verify
print(json.dumps(out, indent=1))
