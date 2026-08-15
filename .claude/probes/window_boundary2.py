import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.detectors.base import windowed_max, WINDOW_WORDS

out = {}
# max not mean: first window 0.1, second 0.9 (threshold at 300 < 320)
def w2(t):
    n = len(t.split())
    return 0.9 if n > 300 else 0.1
out["max_taken"] = round(windowed_max(" ".join(f"y{i}" for i in range(WINDOW_WORDS * 2)), w2), 2)
# empty text
out["empty"] = windowed_max("", lambda t: 0.5)
print(json.dumps(out, indent=1))
