import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
import untell.scripts.run as R

# detector_thresholds: named detector above its own gate vetoes the pass
calls = {"n": 0}
def fake_score(text, **kw):
    calls["n"] += 1
    return {"max": 0.20, "mean": 0.15, "detectors": {"perplexity_burstiness": 0.20, "mage": 0.10},
            "tier": "lite", "scored": True, "flagged": False}

orig = R.score_text
R.score_text = fake_score
try:
    # no gate: max 0.20 < 0.30 -> passes
    r0 = R.untell_text("Some input text long enough to score cleanly here.", tier="lite", max_iters=2, seed=1)
    calls["n"] = 0
    # gate: mage must be < 0.05, but it's 0.10 -> vetoed
    r1 = R.untell_text("Some input text long enough to score cleanly here.", tier="lite", max_iters=2, seed=1,
                       detector_thresholds={"mage": 0.05})
    calls["n"] = 0
    # gate met: mage < 0.15 -> passes
    r2 = R.untell_text("Some input text long enough to score cleanly here.", tier="lite", max_iters=2, seed=1,
                       detector_thresholds={"mage": 0.15})
    out = {
        "no_gate_stopped": r0.get("stopped"),
        "gate_veto_stopped": r1.get("stopped"),
        "gate_met_stopped": r2.get("stopped"),
        "veto_worked": r0.get("stopped") == "passed" and r1.get("stopped") != "passed" and r2.get("stopped") == "passed",
    }
finally:
    R.score_text = orig
print(json.dumps(out, indent=1))
