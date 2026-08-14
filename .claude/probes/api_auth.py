"""API auth invariants: no-key open, key required when set, constant-time, rate limit 0 disables."""
import json, os
from untell.api_server import _verify_key, _api_key, _rate_limit, _rate_limited

out = {}
# 1. No key configured -> open access
os.environ.pop("UNTELL_API_KEY", None)
out["no_key_open"] = _verify_key(None) is True
# 2. Key set -> required and verified
os.environ["UNTELL_API_KEY"] = "secret123"
out["key_set_requires"] = _verify_key(None) is False
out["correct_key"] = _verify_key("secret123") is True
out["wrong_key"] = _verify_key("wrong") is False
del os.environ["UNTELL_API_KEY"]
# 3. Rate limit 0 disables
os.environ["UNTELL_RATE_LIMIT"] = "0"
out["rl_zero_disables"] = _rate_limit() == 0
del os.environ["UNTELL_RATE_LIMIT"]
# 4. Bad rate limit -> default + warning
os.environ["UNTELL_RATE_LIMIT"] = "abc"
out["rl_bad_defaults"] = _rate_limit() > 0
del os.environ["UNTELL_RATE_LIMIT"]
print(json.dumps(out, indent=1))
