import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
# ensure no keys present
for k in list(os.environ):
    if "API_KEY" in k or k.startswith("UNTELL_"):
        if k not in ("UNTELL_LITE_NO_TORCH",):
            os.environ.pop(k, None)
from untell.detectors.commercial import OriginalityDetector, _has
from untell.detectors.base import load_detectors

out = {}
out["no_key"] = not _has("ORIGINALITY_API_KEY", "GPTZERO_API_KEY", "COPILEAKS_API_KEY")
d = OriginalityDetector()
out["detector_available_no_key"] = d.available()
detectors = load_detectors("commercial")
out["commercial_roster"] = [x.name for x in detectors]
out["commercial_empty"] = len(detectors) == 0
print(json.dumps(out, indent=1))
