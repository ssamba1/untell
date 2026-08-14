import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.score import MAX_INPUT_CHARS

# 1. Over-cap handling: does score_text truncate and SAY so?
from untell.scripts.score import score_text
big = ("The system utilizes a comprehensive methodology throughout the year. " * 3000)
s = score_text(big, tier="lite")
out = {"cap": MAX_INPUT_CHARS, "input_chars": len(big),
       "truncation_mentioned": bool(s.get("warning")) and ("truncat" in (s.get("warning") or "").lower())}
print(json.dumps(out))
