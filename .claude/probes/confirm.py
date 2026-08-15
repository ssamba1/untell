import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
import untell.scripts.run as R

# confirm: a noisy re-flag demotes 'passed' to 'passed_unconfirmed'
calls = {"n": 0}
def fake_score(text, **kw):
    calls["n"] += 1
    if calls["n"] == 1:
        return {"max": 0.10, "mean": 0.08, "detectors": {"a": 0.10}, "tier": "lite", "scored": True, "flagged": False}
    return {"max": 0.35, "mean": 0.30, "detectors": {"a": 0.35}, "tier": "lite", "scored": True, "flagged": True}

orig = R.score_text
R.score_text = fake_score
try:
    r0 = R.untell_text("Some input text long enough to score.", tier="lite", max_iters=2, seed=1, confirm=0)
    calls["n"] = 0
    r2 = R.untell_text("Some input text long enough to score.", tier="lite", max_iters=2, seed=1, confirm=2)
    out = {
        "confirm0_stopped": r0.get("stopped"),
        "confirm2_stopped": r2.get("stopped"),
        "confirm2_calls": calls["n"],
        "demoted": r2.get("stopped") == "passed_unconfirmed",
    }
finally:
    R.score_text = orig
print(json.dumps(out, indent=1))
