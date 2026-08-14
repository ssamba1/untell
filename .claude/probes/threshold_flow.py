"""threshold propagation: custom threshold flows into flagged/verdict consistently."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.score import score_text

text = "The system reads the input file and processes each record in sequence. The results were clear to the whole team."
out = {}
for thr in (0.1, 0.3, 0.5, 0.9):
    s = score_text(text, tier="lite", threshold=thr)
    # invariant: flagged must be consistent with the DOCUMENTED threshold-band logic
    out[f"thr_{thr}"] = {"max": round(s["max"], 4), "flagged": s["flagged"],
                         "flag_ge_verdict": s["flagged"] == (s["max"] >= max(thr, 0.45)) if s.get("detector_modes", {}).get("perplexity_burstiness") == "stdlib" else "n/a"}
print(json.dumps(out, indent=1))
