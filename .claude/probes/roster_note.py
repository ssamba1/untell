import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.score import _short_roster_note

out = {}
# full tier with fewer members than expected -> note
out["full_short"] = _short_roster_note("full", "full", {"a": 0.1, "b": 0.2})
out["full_short_str"] = str(_short_roster_note("full", "full", {"a": 0.1, "b": 0.2}))[:80] if _short_roster_note("full", "full", {"a": 0.1, "b": 0.2}) else None
# lite tier short roster -> None (definition of the tier)
out["lite_short"] = _short_roster_note("lite", "lite", {"a": 0.1})
# downgraded tier -> note? (tier downgraded is a different branch per the code comment)
out["downgraded"] = _short_roster_note("full", "lite", {"a": 0.1})
print(json.dumps(out, indent=1)[:600])
