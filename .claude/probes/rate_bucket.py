"""Rate bucket: limit+1 rejected, window expiry resets, per-credential isolation."""
import json, os
from unittest.mock import MagicMock
import untell.api_server as A

os.environ["UNTELL_RATE_LIMIT"] = "3"
req = MagicMock(); req.client.host = "1.2.3.4"
A._rate_buckets.clear()
out = {}
r1 = [A._rate_limited(req, "clientA") for _ in range(3)]
r2 = A._rate_limited(req, "clientA")
out["3_allowed_then_rejected"] = r1 == [None, None, None] and r2 is not None
out["rejection_is_seconds"] = isinstance(r2, int) and r2 >= 1
# per-credential isolation: different client not limited
out["other_cred_not_limited"] = A._rate_limited(req, "clientB") is None
# window expiry resets (force old bucket)
A._rate_buckets["clientA"] = (__import__("time").monotonic() - A._RATE_WINDOW_SECONDS - 1, 99)
out["window_expiry_resets"] = A._rate_limited(req, "clientA") is None
del os.environ["UNTELL_RATE_LIMIT"]
print(json.dumps(out, indent=1))
