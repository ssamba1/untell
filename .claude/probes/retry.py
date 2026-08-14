"""retry invariants: attempt counts, retryable classification, delay cap."""
import json, time
from untell._retry import retry, _is_retryable

out = {}
# 1. max_attempts=1 -> exactly 1 call
calls = {"n": 0}
def boom():
    calls["n"] += 1
    raise ConnectionError("connection reset")
try:
    retry(boom, max_attempts=1)
except ConnectionError:
    pass
out["max1_single_call"] = calls["n"] == 1

# 2. Non-retryable -> raised immediately, 1 call
calls2 = {"n": 0}
def boom2():
    calls2["n"] += 1
    raise ValueError("not transient")
try:
    retry(boom2, max_attempts=3)
except ValueError:
    pass
out["nonretryable_single_call"] = calls2["n"] == 1

# 3. Retryable exhausted -> re-raised, called max_attempts times
calls3 = {"n": 0}
def boom3():
    calls3["n"] += 1
    raise ConnectionError("try again later")
try:
    retry(boom3, max_attempts=3, base_delay=0.01, max_delay=0.05)
except ConnectionError:
    pass
out["retryable_exhausted"] = calls3["n"] == 3

# 4. Delay cap: max_delay honored even with large base
start = time.monotonic()
try:
    retry(boom3, max_attempts=3, base_delay=5.0, max_delay=0.1)
except ConnectionError:
    pass
elapsed = time.monotonic() - start
out["delay_capped"] = elapsed < 1.0

# 5. Classification
out["classify_conn"] = _is_retryable(ConnectionError("connection refused"))
out["classify_http"] = _is_retryable(RuntimeError("HTTP 429 too many requests"))
out["classify_timeout"] = _is_retryable(RuntimeError("operation timed out"))
out["classify_value"] = not _is_retryable(ValueError("bad input"))
print(json.dumps(out, indent=1))
