import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.score import score_text, DEFAULT_THRESHOLD, _verdict_threshold

docs = {
    "humanish": open(".claude/corpora/hc3-human.txt", encoding="utf-8").read()[:2000],
    "ai": ("Moreover, the framework leverages a robust approach to delivery at scale. Furthermore, "
           "it is important to note that this underscores the pivotal integration for every team. "
           "In conclusion, organizations must harness these seamless solutions today."),
}
out = {}
for name, d in docs.items():
    s = score_text(d, tier="lite")
    vt = _verdict_threshold(s.get("threshold", DEFAULT_THRESHOLD), s.get("detectors", {}), s.get("detector_modes", {}))
    correct = (s["flagged"] == (s["max"] >= vt))
    out[name] = {"max": round(s["max"], 4), "flagged": s["flagged"], "verdict_threshold": round(vt, 4),
                 "correct_vs_verdict": correct}
print(json.dumps(out, indent=1))
