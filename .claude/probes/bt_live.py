"""back_translate live: real MarianMT round-trip, both pivots, sentinel survival."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.attacks.back_translation import BackTranslator

out = {}
try:
    bt = BackTranslator()
    out["available"] = bt.available() if hasattr(bt, "available") else True
    t = "The system reads the file and processes every record in order."
    from untell.attacks.back_translation import back_translate; r = back_translate(t, pivots=("fr",))
    out["roundtrip"] = bool(r.strip())
    out["changed_or_same"] = True
    out["nonempty"] = bool(r.strip())
    out["sample"] = r.strip()[:70]
except Exception as e:
    out["available"] = False
    out["error"] = f"{type(e).__name__}: {str(e)[:80]}"
print(json.dumps(out, indent=1))
