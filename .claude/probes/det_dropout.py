"""Dropout selection mode cross-process determinism + subset reproducibility."""
import json, os, hashlib
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
os.environ["UNTELL_SELECT"] = "dropout"
from untell.scripts.run import untell_text

DOC = "The system utilizes a comprehensive methodology throughout the year. Additionally, the platform empowers users to streamline their daily workflows considerably."
r = untell_text(DOC, tier="lite", max_iters=3, rewriter="structural", best_of=3, seed=42)
print(json.dumps({"final": r.get("final"), "changed": r.get("changed")}))
