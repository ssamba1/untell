import json, os, subprocess, sys
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.mcp_server import _bad_args

out = {}
t = "Moreover, the framework leverages robust solutions to deliver outcomes at scale."
# CLI path
r = subprocess.run(
    [sys.executable, "-m", "untell.scripts.tells", t],
    capture_output=True, text=True, env={**os.environ, "PYTHONPATH": ""}, timeout=120
)
out["cli_rc"] = r.returncode
out["cli_has_count"] = "tells" in r.stdout or "Tells" in r.stdout
# REST path
from fastapi.testclient import TestClient
from untell.api_server import app
client = TestClient(app)
rr = client.post("/tells", json={"text": t})
out["rest_200"] = rr.status_code == 200
out["rest_tells"] = rr.json().get("tells") if rr.status_code == 200 else None
# MCP path: (value, kind) tuple shape
bad = _bad_args(threshold=("abc", "probability"))
out["mcp_bad_refusal"] = isinstance(bad, dict) and "error" in bad
ok = _bad_args(threshold=(0.3, "probability"))
out["mcp_valid_none"] = ok is None
print(json.dumps(out, indent=1))
