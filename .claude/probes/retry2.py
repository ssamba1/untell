import json, os, time
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from unittest.mock import patch
from untell._retry import retry

out = {}
# max_attempts < 1 clamped to 1
calls = {"n": 0}
def boom():
    calls["n"] += 1
    raise ValueError("transient")
with patch("untell._retry._is_retryable", return_value=True):
    try:
        retry(boom, max_attempts=0, base_delay=0.01, max_delay=0.05)
    except ValueError:
        pass
    out["zero_clamped_to_one"] = calls["n"] == 1
# backoff capped at max_delay (not max_delay + 1)
calls["n"] = 0
delays = []
with patch("untell._retry._is_retryable", return_value=True), patch("untell._retry.time.sleep", side_effect=lambda d: delays.append(d)):
    try:
        retry(boom, max_attempts=6, base_delay=2.0, max_delay=5.0)
    except ValueError:
        pass
    out["calls_six"] = calls["n"] == 6
    out["all_capped"] = all(d <= 5.0 for d in delays)
    out["max_delay_exact"] = max(delays) <= 5.0
# first-try success sleeps nothing
calls["n"] = 0
def ok():
    return "fine"
with patch("untell._retry.time.sleep") as s:
    r = retry(ok, max_attempts=3, base_delay=5.0)
    out["first_success"] = r == "fine"
    out["no_sleep"] = not s.called
print(json.dumps(out, indent=1))
