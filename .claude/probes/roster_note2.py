import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.score import _short_roster_note
from untell.detectors.base import all_detectors

out = {}
# full tier with a REAL detector missing from scores (e.g. mage absent)
names = {d.name for d in all_detectors() if d.tier in ("lite", "full")}
scores = {n: 0.5 for n in names if n != "mage"}  # mage deliberately absent
note = _short_roster_note("full", "full", scores)
out["note_fires"] = note is not None
out["note_text"] = note[:100] if note else None
# lite tier -> None (definition of the tier)
out["lite_none"] = _short_roster_note("lite", "lite", scores) is None
print(json.dumps(out, indent=1)[:500])
