"""stopped semantics: below-threshold text -> passed; above -> max_iters; empty -> early."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import untell_text

out = {}
# 1. Clean human text -> stops passed (no rewrite needed)
clean = "The team ran the experiment and recorded the results. They published the findings in the spring. The data was clear and the conclusion followed naturally."
r = untell_text(clean, tier="lite", max_iters=3, seed=1)
out["clean_stopped"] = r.get("stopped")
out["clean_flagged"] = r.get("flagged")
# 2. AI text with max_iters=1 -> max_iters (or passed if 1 iter cleared it)
ai = ("Moreover, the framework leverages robust solutions to deliver outcomes at scale. "
      "It is important to note that the results demonstrate significant improvement.")
r2 = untell_text(ai, tier="lite", max_iters=1, seed=1)
out["ai_iters1_stopped"] = r2.get("stopped")
out["ai_iters1_final_changed"] = r2["final"] != ai
# 3. Empty text -> handles gracefully
r3 = untell_text("", tier="lite", max_iters=2, seed=1)
out["empty_final"] = repr(r3.get("final"))
out["empty_stopped"] = r3.get("stopped")
print(json.dumps(out, indent=1))
