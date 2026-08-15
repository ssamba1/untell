import json
from untell.scripts.score import _threshold_range_warning

out = {}
out["high"] = _threshold_range_warning(1.5) is not None
out["low"] = _threshold_range_warning(-0.1) is not None
out["in_range"] = _threshold_range_warning(0.3) is None
out["zero"] = _threshold_range_warning(0.0) is None
out["one"] = _threshold_range_warning(1.0) is None
out["none_val"] = _threshold_range_warning(None) is None
out["bool_val"] = _threshold_range_warning(True) is None
print(json.dumps(out, indent=1))
