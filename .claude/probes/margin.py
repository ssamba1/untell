import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import _passed

out = {}
# margin 0: max < threshold passes
out["margin0_pass"] = _passed({"max": 0.29, "detectors": {"a": 0.29}}, 0.3, 0.0)
out["margin0_boundary_fail"] = not _passed({"max": 0.30, "detectors": {"a": 0.30}}, 0.3, 0.0)
# margin 0.05: needs max < 0.25
out["margin_headroom"] = _passed({"max": 0.29, "detectors": {"a": 0.29}}, 0.3, 0.05) is False
out["margin_below"] = _passed({"max": 0.24, "detectors": {"a": 0.24}}, 0.3, 0.05)
# all_checkers_failed -> never pass
out["all_failed"] = not _passed({"all_checkers_failed": True, "max": 0.1, "detectors": {"a": 0.1}}, 0.3, 0.0)
# no signal -> never pass
out["no_signal"] = not _passed({"max": 0.1, "detectors": {"a": None}}, 0.3, 0.0)
print(json.dumps(out, indent=1))
