"""Cross-process determinism: same input+seed, different PYTHONHASHSEED. Stdlib lite path."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import untell_text

DOC = ("Moreover, the framework leverages a robust approach to delivery at scale across the whole "
       "programme. Furthermore, it is important to note that this underscores the pivotal integration "
       "for every team. The system utilizes a comprehensive methodology throughout the year. "
       "Additionally, the platform empowers users to streamline their daily workflows considerably. "
       "In conclusion, organizations must harness these seamless solutions today.")

r = untell_text(DOC, tier="lite", max_iters=2, rewriter="structural", best_of=3, seed=42)
print(json.dumps({"changed": r.get("changed"), "final": r.get("final"),
                  "similarity": r.get("similarity"), "post_max": (r.get("post") or {}).get("max")}))
