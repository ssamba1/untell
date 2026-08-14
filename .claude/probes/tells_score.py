"""tells vs score agreement: the two catalogs must not contradict on real corpus text."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.tells import score_tells
from untell.scripts.score import score_text

# Corpus samples: real human + real AI from the loop's own corpora
import random
docs = []
for path in [".claude/corpora/hc3-human.txt", ".claude/corpora/hc3-short.txt"]:
    try:
        text = open(path, encoding="utf-8").read()
        docs.append(text[:2000])
    except OSError:
        pass
# add AI-flavored synthetic
docs.append("Moreover, the framework leverages a robust approach to delivery at scale. Furthermore, it is important to note that this underscores the pivotal integration for every team. In conclusion, organizations must harness these seamless solutions today.")

out = {}
for i, d in enumerate(docs):
    if len(d.split()) < 10: continue
    t = score_tells(d)
    s = score_text(d, tier="lite")
    out[f"doc{i}"] = {
        "words": t.get("words"),
        "tells": t.get("tells"),
        "tells_per_100w": round(t.get("tells_per_100w", 0), 3),
        "score_max": round(s.get("max", 0), 3),
        "flagged": s.get("flagged"),
        # A text with 0 tells and score ~0.0 is consistent (both say human);
        # a text with MANY tells but score 0.0 would be a contradiction (detector blind to tells)
        "tells_vs_score": "consistent" if (t.get("tells", 0) > 0) == (s.get("max", 0) >= 0.3) or t.get("tells", 0) == 0 else "CONTRADICTION",
    }
print(json.dumps(out, indent=1))
