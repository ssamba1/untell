"""Correct invariant: HIGH tells rate must correlate with flagged; LOW rate must not contradict.
Human baseline ~3-5 tells/100w. A doc with 20+ tells/100w scoring 0.0 would be a real contradiction."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.tells import score_tells
from untell.scripts.score import score_text

docs = {
    "human": open(".claude/corpora/hc3-human.txt", encoding="utf-8").read()[:2000],
    "ai_heavy": ("Moreover, the framework leverages a robust approach to delivery at scale. Furthermore, "
                 "it is important to note that this underscores the pivotal integration for every team. "
                 "Additionally, the platform empowers users to streamline their daily workflows considerably. "
                 "In conclusion, organizations must harness these seamless solutions today. "
                 "It should be noted that the results were significant. Ultimately, the data demonstrates clearly."),
}
out = {}
for name, d in docs.items():
    t = score_tells(d)
    s = score_text(d, tier="lite")
    rate = t.get("tells_per_100w", 0)
    flagged = s.get("flagged")
    # invariant: rate > 10 must be flagged; rate < 1 may be either (short text noise)
    verdict = "ok"
    if rate > 10 and not flagged:
        verdict = "DEFECT: high tell rate not flagged"
    if rate < 1 and flagged and t.get("words", 0) > 100:
        verdict = "ok (length/other signal)"
    out[name] = {"words": t.get("words"), "rate": round(rate, 2), "flagged": flagged, "verdict": verdict}
print(json.dumps(out, indent=1))
