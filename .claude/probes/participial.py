import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.structural import _flatten_participial_trailers

out = {}
t = "The results are clear, underscoring its importance."
r = _flatten_participial_trailers(t)
out["flattened"] = ", underscoring" not in r and ". " in r
out["subject_intro"] = r.endswith("its importance.")
# no participial -> unchanged
t2 = "The results are clear and important."
out["plain_unchanged"] = _flatten_participial_trailers(t2) == t2
# consecutive flattenings use different subjects
t3 = "The results are clear, underscoring its importance, highlighting the need for action."
r3 = _flatten_participial_trailers(t3)
out["two_flattened"] = r3.count(". ") >= 2
print(json.dumps(out, indent=1))
print("sample:", r3[:80])
