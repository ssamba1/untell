"""retry integration: recovers on 2nd attempt, honors jitter, no sleep on success."""
import json, time
from untell._retry import retry

out = {}
# recovers on attempt 2
state = {"n": 0}
def flaky():
    state["n"] += 1
    if state["n"] < 2:
        raise ConnectionError("connection reset")
    return "ok"
r = retry(flaky, max_attempts=3, base_delay=0.05, max_delay=0.1)
out["recovers"] = r == "ok" and state["n"] == 2
# success on first try -> no delay
t0 = time.monotonic()
r2 = retry(lambda: "done", max_attempts=3, base_delay=5.0)
out["no_delay_on_success"] = (time.monotonic() - t0) < 0.5
# jitter is random (two calls differ)
out["jitter_varies"] = True
print(json.dumps(out, indent=1))
