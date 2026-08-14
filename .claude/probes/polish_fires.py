"""Polish fires when there IS something to polish: use a vocab-heavy final."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import untell_text
from untell.attacks import surgical_substitute

# Count how many times surgical_substitute is called (the polish hook)
calls = {"n": 0}
orig = surgical_substitute
def counting(*a, **k):
    calls["n"] += 1
    return orig(*a, **k)

import untell.attacks as A
A.surgical_substitute = counting
try:
    doc = ("The system utilizes a comprehensive methodology to leverage robust outcomes. "
           "Moreover, it facilitates seamless integration across the entire platform.")
    r = untell_text(doc, tier="lite", max_iters=2, seed=1, polish=True)
    out = {"polish_calls": calls["n"], "final_changed": r["final"] != doc}
finally:
    A.surgical_substitute = orig
print(json.dumps(out, indent=1))
