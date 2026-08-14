"""scrub CLI: hidden chars removed, JSON valid, exit 0."""
import json, subprocess, sys, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
env = dict(os.environ); env["PYTHONPATH"] = ""
dirty = "The system works well\u200b here. Clean text after."
r = subprocess.run([sys.executable, "-m", "untell.scripts.run", "scrub", "--json", dirty],
                   capture_output=True, text=True, env=env, timeout=60)
out = {}
try:
    d = json.loads(r.stdout)
    out["valid_json"] = True
    out["zwsp_removed"] = "\u200b" not in d.get("text", "")
    out["keys"] = sorted(d.keys())
except Exception as e:
    out["valid_json"] = False
    out["error"] = str(e)[:80]
    out["stdout"] = r.stdout[:150]
out["exit"] = r.returncode
print(json.dumps(out, indent=1))
