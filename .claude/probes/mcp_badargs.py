"""_bad_args: refusal semantics for each validation type."""
import json
from untell.mcp_server import _bad_args

out = {}
out["bad_tier"] = _bad_args(tier=("bogus", "tier"))
out["bad_threshold"] = _bad_args(threshold=("abc", "probability"))
out["ok"] = _bad_args(tier=("full", "tier"), threshold=(0.3, "probability"))
out["none_value"] = _bad_args(text=(None, "text"))
print(json.dumps(out, indent=1))
