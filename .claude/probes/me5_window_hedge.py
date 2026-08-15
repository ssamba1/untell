import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.detectors.base import windowed_max, WINDOW_WORDS

out = {}

# ---------- PROBE 1: windowed_max boundary semantics ----------
# score_window stub records every window it is handed
calls = []

def rec_score(text):
    calls.append(text)
    n = len(text.split())
    return 0.1 + n / 1000.0  # monotonic in window size -> max != mean whenever sizes differ

W = WINDOW_WORDS
assert W == 320, W

# 1a. text exactly at WINDOW_WORDS -> single-call path (1 window, no split)
calls.clear()
r = windowed_max(" ".join(f"w{i}" for i in range(W)), rec_score)
out["exact_320_ncalls"] = len(calls)
out["exact_320_return"] = round(r, 4)
out["exact_320_words_in_window"] = len(calls[0].split()) if calls else None

# 1b. a few words over (one run-on sentence, no terminators) -> _split_to_width: [320, 3]
calls.clear()
r = windowed_max(" ".join(f"x{i}" for i in range(W + 3)), rec_score)
out["over_323_ncalls"] = len(calls)
out["over_323_window_sizes"] = [len(c.split()) for c in calls]
out["over_323_return"] = round(r, 4)

# 1c. 2x window, packed from 10-word sentences -> exactly 2 windows of 320
sentences = [" ".join(f"s{i}w{j}" for j in range(10)) for i in range(64)]  # 64 x 10 = 640 words
calls.clear()
r = windowed_max(". ".join(sentences) + ".", rec_score)
out["twoX_640_ncalls"] = len(calls)
out["twoX_640_window_sizes"] = [len(c.split()) for c in calls]
out["twoX_640_return"] = round(r, 4)

# 1d. MAX not mean: two windows whose scores differ -> must return the higher
def marker_score(text):
    if "HIGH" in text:
        return 0.9
    if "LOW" in text:
        return 0.1
    return 0.5
mixed = " ".join(["LOW"] * 320 + ["HIGH"] * 320)  # 640 words, one run-on -> [320 LOW, 320 HIGH]
calls.clear()
r = windowed_max(mixed, marker_score)
out["max_not_mean_return"] = r
out["max_not_mean_is_max"] = r == 0.9
out["max_not_mean_ncalls"] = len(calls)

# 1e. empty text: no crash; single-call path hands '' to score_window
def empty_stub(text):
    return 0.0 if text == "" else 0.5
r = windowed_max("", empty_stub)
out["empty_return"] = r
# and the None-drop path: score_window returning None -> windowed_max returns None (not crash, not NaN)
def none_stub(text):
    return None
r = windowed_max("some words here", none_stub)
out["all_none_return"] = r

# ---------- PROBE 2: _HEDGE_RE substitution ----------
from untell.rewriter.structural import _HEDGE_RE

def sub(t):
    return _HEDGE_RE.sub(r"\1", t)

out["hedge_could_potentially"] = sub("This could potentially work.")
out["hedge_may_eventually"] = sub("It may eventually arrive.")
out["hedge_case_COULD_POTENTIALLY"] = sub("This COULD POTENTIALLY work.")
# coverage of the full modal/adverb matrix
out["hedge_matrix"] = {
    m + "_" + a: sub(f"X {m} {a} Y.")
    for m in ("could", "may", "might", "would", "can")
    for a in ("potentially", "eventually", "possibly", "likely", "arguably")
}
print(json.dumps(out, indent=1, sort_keys=True))
