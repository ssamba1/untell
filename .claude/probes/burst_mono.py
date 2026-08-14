"""Burstiness signal monotonicity: uniform rhythm -> higher P(AI) than varied rhythm, SAME words."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.detectors.perplexity_burstiness import _burstiness, lite_score

# Same 24 words, uniform rhythm vs varied rhythm (reordered into different sentence lengths)
words = "The system reads the file before it parses any record carefully and writes each result to the store".split()
uniform = " ".join(words[:6]) + ". " + " ".join(words[6:12]) + ". " + " ".join(words[12:18]) + ". " + " ".join(words[18:])
varied = " ".join(words[:9]) + ". " + " ".join(words[9:11]) + ". " + " ".join(words[11:20]) + ". " + " ".join(words[20:])
# also a truly uniform repetition
rep = "The team ran the test. " * 8

out = {
    "uniform_cv": round(_burstiness(uniform.split(".")), 4) if len(uniform.split(".")) >= 2 else None,
    "varied_cv": round(_burstiness(varied.split(".")), 4) if len(varied.split(".")) >= 2 else None,
    "uniform_score": round(lite_score(uniform), 4),
    "varied_score": round(lite_score(varied), 4),
    "rep_score": round(lite_score(rep), 4),
    "uniform_gt_varied_score": lite_score(uniform) >= lite_score(varied),
    "rep_high": lite_score(rep) > 0.5,
}
print(json.dumps(out, indent=1))
