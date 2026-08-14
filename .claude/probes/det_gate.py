"""detector_thresholds: per-detector gate refuses pass when a named detector is hot."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import untell_text

doc = "The system reads the file and processes the records in order. The results were clear to the team."
out = {}
# threshold high enough that the GLOBAL gate would pass, but detector_thresholds still vetoes
r = untell_text(doc, tier="lite", max_iters=1, seed=1, threshold=0.95,
                detector_thresholds={"perplexity_burstiness": 0.0})
out["det_gate_vetoes"] = r.get("stopped") != "passed"
r2 = untell_text(doc, tier="lite", max_iters=1, seed=1, threshold=0.95)
out["no_gate_passes"] = r2.get("stopped") == "passed"
print(json.dumps(out, indent=1))
