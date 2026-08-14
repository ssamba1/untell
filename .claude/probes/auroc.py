"""auroc: perfect separation 1.0, inverted 0.0, ties half, empty None."""
import json
from eval.detector_audit import auroc

out = {}
out["perfect"] = auroc([0.9, 0.8], [0.2, 0.1]) == 1.0
out["inverted"] = auroc([0.1, 0.2], [0.9, 0.8]) == 0.0
out["ties_half"] = auroc([0.5], [0.5]) == 0.5
out["mixed"] = round(auroc([0.9, 0.3], [0.2, 0.4]), 4)
out["empty"] = auroc([], [0.5]) is None
# all equal -> 0.5 (ties everywhere)
out["all_equal"] = auroc([0.7, 0.7], [0.7, 0.7]) == 0.5
print(json.dumps(out, indent=1))
