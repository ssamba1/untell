import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import untell_text

out = {}
t = ("Moreover, the framework leverages robust solutions to deliver outcomes at scale. "
     "It is important to note that the results demonstrate significant improvement.")
# style via the prompt path needs an LLM rewriter; with composite the style is a hint only.
# Verify style doesn't crash and the loop still runs.
for style in ("casual", "academic", "blunt"):
    try:
        r = untell_text(t, tier="lite", max_iters=1, seed=1, style=style)
        out[style] = {"ran": True, "final": bool(r.get("final", "").strip())}
    except Exception as e:
        out[style] = {"ran": False, "error": f"{type(e).__name__}: {str(e)[:50]}"}
# invalid style -> rejected? (loop may warn or ignore)
try:
    r = untell_text(t, tier="lite", max_iters=1, seed=1, style="nonexistent-style")
    out["invalid_style"] = {"ran": True, "final": bool(r.get("final", "").strip())}
except Exception as e:
    out["invalid_style"] = {"ran": False, "error": f"{type(e).__name__}: {str(e)[:50]}"}
print(json.dumps(out, indent=1))
