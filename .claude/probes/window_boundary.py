import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.detectors.base import windowed_max, WINDOW_WORDS

out = {}
out["window"] = WINDOW_WORDS
# exactly at window -> 1-2 calls
calls = {"n": 0}
def w1(t):
    calls["n"] += 1
    return 0.3
t_at = " ".join(f"w{i}" for i in range(WINDOW_WORDS))
windowed_max(t_at, w1)
out["at_window_calls"] = calls["n"]
# 2x window -> 2 calls
calls["n"] = 0
t_2x = " ".join(f"x{i}" for i in range(WINDOW_WORDS * 2))
windowed_max(t_2x, w1)
out["two_x_calls"] = calls["n"]
# empty -> graceful
out["empty"] = windowed_max("", w1)
# max not mean: window scores 0.1, 0.9 -> returns 0.9
def w2(t):
    n = len(t.split())
    return 0.9 if n > WINDOW_WORDS else 0.1
out["max_taken"] = round(windowed_max(" ".join(f"y{i}" for i in range(WINDOW_WORDS * 2)), w2), 2)
print(json.dumps(out, indent=1))
