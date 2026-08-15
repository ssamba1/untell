import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import untell_text

# clean text: margin 0 -> stops early (passed); margin 0.3 (below threshold by headroom) -> same or more iters
clean = ("We tried a few approaches and the last one finally worked. The numbers came out better "
         "than we hoped, though the first batch was a mess. Our intern fixed the parser and "
         "everything started passing again. It took most of the week but we got there in the end.")
out = {}
r0 = untell_text(clean, tier="lite", max_iters=3, seed=1, margin=0.0)
r1 = untell_text(clean, tier="lite", max_iters=3, seed=1, margin=0.25)
out["margin0_stopped"] = r0.get("stopped")
out["margin1_stopped"] = r1.get("stopped")
out["margin0_iters"] = r0.get("iterations")
out["margin1_iters"] = r1.get("iterations")
out["both_valid"] = bool(r0.get("final", "").strip()) and bool(r1.get("final", "").strip())
print(json.dumps(out, indent=1))
