import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
os.environ["UNTELL_DISABLE_MAGE"] = "1"
from untell.scripts.score import _short_roster_note
from untell.detectors.base import all_detectors

out = {}
names = {d.name for d in all_detectors() if d.tier in ("lite", "full")}
scores = {n: 0.5 for n in names if n != "mage"}
note = _short_roster_note("full", "full", scores)
out["note_fires"] = note is not None
out["note_text"] = note[:120] if note else None
del os.environ["UNTELL_DISABLE_MAGE"]
print(json.dumps(out, indent=1)[:500])
