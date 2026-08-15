import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.score import _score_with_detectors

out = {}
# fake detectors exercising the defensive layers
class D:
    def __init__(self, name, val):
        self.name = name
        self.tier = "full"
        self.val = val
    def score(self, text):
        return self.val

# NaN detector -> excluded with __error, no NaN poisoning
r = _score_with_detectors([D("nan_det", float("nan")), D("good_det", 0.5)], "x", tier="full")
out["nan_excluded"] = r["detectors"]["nan_det"] is None
out["nan_error"] = "NaN" in r["detectors"].get("nan_det__error", "")
out["max_clean"] = r["max"] == 0.5
# out-of-range raw -> clamped, raw surfaced
r2 = _score_with_detectors([D("big_det", 8500.0)], "x", tier="full")
out["big_clamped"] = r2["detectors"]["big_det"] == 1.0
out["big_raw_surfaced"] = r2.get("out_of_range") or r2["detectors"].get("big_det__raw") is not None or "clamped" in str(r2.get("warning", "")).lower()
# non-numeric -> excluded with error
r3 = _score_with_detectors([D("str_det", "not-a-number")], "x", tier="full")
out["str_excluded"] = r3["detectors"]["str_det"] is None
out["str_error"] = "non-numeric" in r3["detectors"].get("str_det__error", "")
# raising detector -> failed, no crash
r4 = _score_with_detectors([D("raise_det", None)], "x", tier="full")
raise_det = next((k for k in r4 if k.startswith("failed")), None)
out["raise_handled"] = raise_det is not None
print(json.dumps(out, indent=1))
