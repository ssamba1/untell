"""config._try_yaml: untell.yaml parsed; bad yaml falls back gracefully."""
import json, os, tempfile, pathlib
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.config import _try_yaml

out = {}
# 1. Valid yaml parsed
with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
    f.write("threshold: 0.42\nmax_iters: 7\ntier: lite\n")
    p = f.name
r = _try_yaml(pathlib.Path(p))
out["valid_parsed"] = r == {"threshold": 0.42, "max_iters": 7, "tier": "lite"}
# 2. Missing file -> {}
out["missing_empty"] = _try_yaml(pathlib.Path("/nonexistent/x.yaml")) == {}
# 3. Bad yaml -> {} (graceful)
with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
    f.write("threshold: [unclosed\n  bad: {yaml\n")
    p2 = f.name
out["bad_graceful"] = _try_yaml(pathlib.Path(p2)) == {}
os.unlink(p); os.unlink(p2)
print(json.dumps(out, indent=1))
