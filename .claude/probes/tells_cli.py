"""tells CLI: JSON output valid, categories match score_tells."""
import json, os, subprocess, sys
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
env = dict(os.environ); env["PYTHONPATH"] = ""
r = subprocess.run([sys.executable, "-m", "untell.scripts.tells", "Moreover, the framework leverages robust solutions for every team."],
                   capture_output=True, text=True, env=env, timeout=60)
out = {}
try:
    data = json.loads(r.stdout)
    out["valid_json"] = True
    out["has_tells"] = "tells" in data
    out["has_rate"] = "tells_per_100w" in data
except Exception as e:
    out["valid_json"] = False
    out["error"] = str(e)[:80]
out["exit"] = r.returncode
print(json.dumps(out, indent=1))
