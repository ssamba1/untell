import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.detectors.base import windowed_max

out = {}
# short text: single call
def single_call(t):
    return 0.5
out["short_single"] = windowed_max("Short text.", single_call) == 0.5
# long text: max of window scores
def window_score(t):
    return len(t.split()) / 100.0
long_text = " ".join(f"word{i}" for i in range(600))
wm = windowed_max(long_text, window_score, window_words=100)
out["long_max"] = round(wm, 2)
# windows break on sentence boundaries (no mid-clause starts) — max over windows of a 600-word text
# with window_words=100: 6 windows, each ~100 words -> score ~1.0 per window (0.95-1.05)
out["windowed_max_returns_max"] = wm is not None and 0.9 <= wm <= 1.1
print(json.dumps(out, indent=1))
