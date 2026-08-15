import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import _meaning_gate_mode

out = {}
out["nli_on"] = _meaning_gate_mode(True)
out["nli_off"] = _meaning_gate_mode(False)
print(json.dumps(out, indent=1))
