import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from fastapi.testclient import TestClient
from untell.api_server import app

client = TestClient(app)
out = {}
# /tells correct shape
r = client.post("/tells", json={"text": "Moreover, the framework leverages robust solutions."})
out["tells_200"] = r.status_code == 200
if r.status_code == 200:
    d = r.json()
    out["tells_count"] = d.get("tells")
    out["tells_keys"] = sorted(d.keys())
# /ceiling correct shape
r = client.post("/ceiling", json={"tier": "lite", "threshold": 0.3, "max_iters": 1, "rewriter": "surgical", "n": 1})
out["ceiling_200"] = r.status_code == 200
if r.status_code == 200:
    d = r.json()
    out["ceiling_keys"] = sorted(d.keys())
# /scrub correct shape
r = client.post("/scrub", json={"text": "The\u200bsystem\u200breads the file."})
out["scrub_200"] = r.status_code == 200
if r.status_code == 200:
    d = r.json()
    out["scrub_changed"] = d.get("changed", d.get("hidden_chars_removed"))
# /sentences correct shape
r = client.post("/sentences", json={"text": "Moreover, the framework leverages robust solutions. The system works fine.", "tier": "lite"})
out["sentences_200"] = r.status_code == 200
if r.status_code == 200:
    d = r.json()
    out["sentences_flagged"] = d.get("flagged", [])
print(json.dumps(out, indent=1))
