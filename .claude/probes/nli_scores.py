import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.entailment import contradiction_score, entailment_score

out = {}
a = "The system runs faster than the old version."
b = "The system runs faster than the old version."
out["contra_identical"] = contradiction_score(a, b)
out["entail_identical"] = entailment_score(a, b)
c = "The system runs slower than the old version."
out["contra_negation"] = contradiction_score(a, c)
out["entail_negation"] = entailment_score(a, c)
d = "The weather is nice today."
out["contra_unrelated"] = contradiction_score(a, d)
out["entail_unrelated"] = entailment_score(a, d)
out["all_in_range"] = all(
    v is None or 0.0 <= v <= 1.0
    for v in (out["contra_identical"], out["entail_identical"], out["contra_negation"],
              out["entail_negation"], out["contra_unrelated"], out["entail_unrelated"])
)
print(json.dumps(out, indent=1))
