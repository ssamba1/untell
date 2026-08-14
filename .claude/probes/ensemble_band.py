"""Ensemble band semantics: passing candidate outranks failing one within the 0.02 band."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.ensemble import _RANK_EPS

out = {"eps": _RANK_EPS}
# Simulate the selection: candidates with (max, mean)
scored = [
    ((0.30, 0.40), "failing_but_lower_mean"),
    ((0.295, 0.50), "passing_but_higher_mean"),
]
best_max = min(r[0] for r, _ in scored)
near = [(r, t) for r, t in scored if r[0] <= best_max + _RANK_EPS]
passing = [(r, t) for r, t in near if r[0] < 0.30]
near = passing or near
winner = min(near, key=lambda rt: (rt[0][1], rt[0][0]))[1]
out["winner"] = winner
out["passing_outranks"] = winner == "passing_but_higher_mean"
print(json.dumps(out, indent=1))
