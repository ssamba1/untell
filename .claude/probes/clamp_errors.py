"""clamp01 + split_detector_errors: clamping semantics, error sidecar separation."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.detectors.base import clamp01
from untell.scripts.score import split_detector_errors

out = {}
out["clamp_low"] = clamp01(-0.5) == 0.0
out["clamp_high"] = clamp01(1.5) == 1.0
out["clamp_mid"] = clamp01(0.4) == 0.4
out["clamp_edges"] = clamp01(0.0) == 0.0 and clamp01(1.0) == 1.0
# split_detector_errors separates error sidecars
dets = {"a": 0.3, "b__error": "boom", "c": 0.7, "d__error": "bad"}
cleaned = split_detector_errors(dets); live = cleaned.get("detectors", {}); errors = cleaned.get("detector_errors", {})
out["live_excludes_errors"] = set(live.keys()) == {"a", "c"}
out["errors_captured"] = set(errors.keys()) == {"b", "d"}
out["error_msgs"] = errors.get("b")
print(json.dumps(out, indent=1))
