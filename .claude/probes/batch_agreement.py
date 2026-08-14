"""batch_score_texts must agree with score_text per item (same max, flagged, warning presence)."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.score import score_text, batch_score_texts

texts = [
    "The system reads the file before anything else happens on the node.",
    "Moreover, the framework leverages robust solutions for every team.",
    "Short.",
    "The team ran the experiment and recorded the results. They published the findings.",
    "",
]
single = [score_text(t, tier="lite") for t in texts]
batch = batch_score_texts(texts, tier="lite")
out = {}
for i, (s, b) in enumerate(zip(single, batch)):
    agree = abs(s.get("max", 0) - b.get("max", 0)) < 1e-6 and s.get("flagged") == b.get("flagged")
    out[f"t{i}"] = {"single_max": round(s.get("max", 0), 4), "batch_max": round(b.get("max", 0), 4),
                    "agree": agree, "single_warn": bool(s.get("warning")), "batch_warn": bool(b.get("warning"))}
print(json.dumps(out, indent=1))
