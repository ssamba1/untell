import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from fastapi.testclient import TestClient
from untell.api_server import app

client = TestClient(app)
r = client.post("/tells", json={"text": "Moreover, the framework leverages robust solutions.", "tier": "lite"})
print("tells status:", r.status_code)
print("tells body:", r.text[:200])
r2 = client.post("/ceiling", json={"text": "The system reads the file and processes the records in order.", "tier": "lite", "repeats": 1})
print("ceiling status:", r2.status_code)
print("ceiling body:", r2.text[:200])
r3 = client.post("/scrub", json={"text": "The\u200bsystem\u200breads the file."})
print("scrub status:", r3.status_code)
print("scrub body:", r3.text[:200])
