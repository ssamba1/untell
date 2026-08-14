"""importance: ranks words, returns (word, score) pairs, no crash on weird input."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.attacks import importance

out = {}
r = importance("The framework leverages robust solutions for every team.", 5)
out["type"] = type(r).__name__
out["is_pairs"] = all(isinstance(x, (tuple, list)) and len(x) == 2 for x in r)
out["top_word"] = r[0][0] if r else None
out["n"] = len(r)
# empty
out["empty"] = importance("", 3)
# 1 word
out["one_word"] = importance("Hello", 3)
print(json.dumps(out, indent=1)[:500])
