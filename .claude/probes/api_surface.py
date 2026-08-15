import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from fastapi.testclient import TestClient
from untell.api_server import app

out = {}
client = TestClient(app)
# /health
r = client.get("/health")
out["health_200"] = r.status_code == 200
# /score with valid body
r = client.post("/score", json={"text": "The system reads the file and processes the records in order.", "tier": "lite"})
out["score_200"] = r.status_code == 200
if r.status_code == 200:
    d = r.json()
    out["score_keys"] = sorted(d.keys())
# /tells
r = client.post("/tells", json={"text": "Moreover, the framework leverages robust solutions.", "tier": "lite"})
out["tells_200"] = r.status_code == 200
if r.status_code == 200:
    d = r.json()
    out["tells_count"] = d.get("tells")
# /scrub
r = client.post("/scrub", json={"text": "The\u200bsystem\u200breads the file."})
out["scrub_200"] = r.status_code == 200
if r.status_code == 200:
    d = r.json()
    out["scrub_changed"] = d.get("changed")
# /ceiling shape
r = client.post("/ceiling", json={"text": "The system reads the file and processes the records in order.", "tier": "lite", "repeats": 1})
out["ceiling_200"] = r.status_code == 200
if r.status_code == 200:
    d = r.json()
    out["ceiling_keys"] = sorted(d.keys())
# invalid tier -> 422
r = client.post("/score", json={"text": "x", "tier": "bogus"})
out["bogus_422"] = r.status_code == 422
print(json.dumps(out, indent=1))
