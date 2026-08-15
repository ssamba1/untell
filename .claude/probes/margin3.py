import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
import untell.scripts.run as R

# Patch score_text to return controlled values, then observe the loop's stop decision.
calls = {"n": 0}
def fake_score(text, **kw):
    calls["n"] += 1
    return {"max": 0.10, "mean": 0.08, "detectors": {"perplexity_burstiness": 0.10},
            "tier": "lite", "scored": True, "flagged": False, "warning": None}

orig = R.score_text
R.score_text = fake_score
try:
    r = R.untell_text("Some input text that is long enough to score cleanly here.", tier="lite", max_iters=3, seed=1, margin=0.05)
    out = {"stopped": r.get("stopped"), "iterations": r.get("iterations"), "calls": calls["n"]}
    # margin 0.05 with max 0.10: needs < 0.25 -> passes immediately
    out["passes_margin"] = r.get("stopped") == "passed"
finally:
    R.score_text = orig
print(json.dumps(out, indent=1))
