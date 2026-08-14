import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.mcp_server import _bad_args

out = {}
out["style_not_checked_here"] = True  # style check is in the tool fn, not _bad_args
# _bad_args on the tool's params
r = _bad_args(
    tier=("bogus", "tier"),
    threshold=(0.5, "probability"),
    max_iters=(3, "count"),
    confirm=(0, "count_or_zero"),
    seed=(-1, "seed"),
)
out["bad_tier_refused"] = r is not None and "unknown tier" in r.get("error", "")
out["tier_valid"] = _bad_args(tier=("lite", "tier")) is None
out["negative_seed_refused"] = _bad_args(seed=(-1, "seed")) is not None
out["negative_confirm_refused"] = _bad_args(confirm=(-1, "count_or_zero")) is not None
out["zero_confirm_allowed"] = _bad_args(confirm=(0, "count_or_zero")) is None
print(json.dumps(out, indent=1))
