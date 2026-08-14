"""Local model detectors: available()/score() contract — score in [0,1] or None, never raises."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.detectors.hc3_roberta import HC3RobertaDetector
from untell.detectors.mage import MageDetector
from untell.detectors.fast_detectgpt import FastDetectGPTDetector

out = {}
for cls in (HC3RobertaDetector, MageDetector, FastDetectGPTDetector):
    try:
        d = cls()
        avail = d.available()
        out[d.name] = {"available": avail, "tier": d.tier}
        if avail:
            s = d.score("The system reads the file and processes the records in order.")
            out[d.name]["score"] = round(s, 4) if isinstance(s, (int, float)) else s
            out[d.name]["in_range"] = (s is None) or (0.0 <= s <= 1.0)
    except Exception as e:
        out[cls.__name__] = {"error": f"{type(e).__name__}: {str(e)[:60]}"}
print(json.dumps(out, indent=1))
