import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import untell_text

out = {}
t = "Moreover, the framework leverages robust solutions to deliver outcomes at scale."
for best_of in (1, 3):
    try:
        r = untell_text(t, tier="lite", max_iters=2, seed=1, best_of=best_of)
        out[f"best_of_{best_of}"] = {
            "ran": True,
            "has_final": bool(r.get("final", "").strip()),
            "final_len": len(r.get("final", "")),
        }
    except Exception as e:
        out[f"best_of_{best_of}"] = {"ran": False, "error": f"{type(e).__name__}: {str(e)[:50]}"}
print(json.dumps(out, indent=1))
