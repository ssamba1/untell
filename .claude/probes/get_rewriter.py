import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter import get_rewriter, __all__

out = {"n_exports": len(__all__)}
for name in ("structural", "surgical", "composite", "targeted", "ensemble"):
    rw = get_rewriter(prefer=name)
    out[name] = type(rw).__name__ if rw else None
# unknown name -> None (not a crash)
try:
    rw = get_rewriter(prefer="nonexistent-xyz")
    out["unknown"] = rw
except Exception as e:
    out["unknown"] = f"RAISED {type(e).__name__}"
print(json.dumps(out, indent=1))
