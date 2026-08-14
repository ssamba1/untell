"""Cross-surface parity: CLI score == library score == MCP score on the same text."""
import json, os, subprocess, sys
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
env = dict(os.environ); env["PYTHONPATH"] = ""
text = "The system reads the file first and processes the records in order. The results were clear to the whole team."

# 1. Library
from untell.scripts.score import score_text
lib = score_text(text, tier="lite")

# 2. CLI
r = subprocess.run([sys.executable, "-m", "untell.scripts.score", "--tier", "lite", text],
                   capture_output=True, text=True, env=env, timeout=120)
cli = json.loads(r.stdout)

out = {
    "lib_max": lib.get("max"),
    "cli_max": cli.get("max"),
    "max_match": abs(lib.get("max", 0) - cli.get("max", 0)) < 1e-6,
    "flag_match": lib.get("flagged") == cli.get("flagged"),
    "detectors_match": set(lib.get("detectors", {}).keys()) == set(cli.get("detectors", {}).keys()),
}
print(json.dumps(out, indent=1))
