"""Seed determinism: same seed -> byte-identical output; different seeds -> (usually) different."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import untell_text

doc = ("Moreover, the framework leverages robust solutions to deliver outcomes at scale. "
       "It is important to note that the results demonstrate significant improvement. "
       "In conclusion, we are excited to share these findings with the community.")
out = {}
r1 = untell_text(doc, tier="lite", max_iters=3, seed=42)
r2 = untell_text(doc, tier="lite", max_iters=3, seed=42)
r3 = untell_text(doc, tier="lite", max_iters=3, seed=7)
out["same_seed_identical"] = r1["final"] == r2["final"]
out["diff_seed_differs"] = r1["final"] != r3["final"]
out["r1_changed"] = r1["final"] != doc
print(json.dumps(out, indent=1))
