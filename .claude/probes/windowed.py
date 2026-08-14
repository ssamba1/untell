"""windowed_max invariants: coverage, no-double-count, abstention, exact-window boundary."""
import json
from untell.detectors.base import windowed_max, _split_to_width

out = {}
# 1. Coverage: every word must appear in exactly one window (no drops, no dupes)
def count_words(text): return len(text.split())
def identity_window(text): return float(count_words(text))  # score = word count
def word_total(text): return count_words(text)
big = " ".join(f"word{i}" for i in range(500))
scores = windowed_max(big, identity_window, window_words=100)
# max window score should be ~100 (each window has ~100 words) — but more importantly, check sum of pieces
pieces = _split_to_width(" ".join(f"w{i}" for i in range(500)), 100)
out["split_to_width_total"] = sum(len(p.split()) for p in pieces)
out["split_to_width_count"] = len(pieces)
# 2. All-None scorer -> None (abstention)
out["all_none_abstains"] = windowed_max("a b c d e", lambda t: None, window_words=2) is None
# 3. NaN windows dropped, max of rest
def nan_second(t): return 0.5 if t.startswith("z") else float("nan")
out["nan_dropped"] = windowed_max("z1 z2 a b c d", nan_second, window_words=2) == 0.5
# 4. Exact window boundary: 100 words = single call
out["exact_boundary_single"] = windowed_max(" ".join(f"w{i}" for i in range(100)), lambda t: 1.0, window_words=100) == 1.0
# 5. 101 words = 2 windows, max picked
def first_word_score(t): return 0.9 if t.startswith("w0") else 0.1
out["two_windows_max"] = windowed_max(" ".join(f"w{i}" for i in range(101)), first_word_score, window_words=100) == 0.9
print(json.dumps(out, indent=1))
