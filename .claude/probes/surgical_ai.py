"""surgical on AI-flavored text: fires, and never increases tells."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.surgical import SurgicalRewriter
from untell.scripts.tells import score_tells

rw = SurgicalRewriter(max_subs=12)
docs = [
    "The framework leverages a robust approach to deliver outcomes at scale.",
    "Moreover, it is important to note that the results underscore the pivotal role of innovation.",
    "Utilizing comprehensive methodologies, the team facilitates seamless integration across platforms.",
    "Additionally, the platform empowers users to streamline their workflows considerably.",
]
emitted, changed = [], 0
for s in docs:
    out = rw.rewrite(s, {"max": 0.9}, 0.3)
    if out and out != s:
        changed += 1
        before = score_tells(s).get("tells_per_100w", 0)
        after = score_tells(out).get("tells_per_100w", 0)
        if after > before + 1.0:
            emitted.append((s[:40], out[:60], round(before,1), round(after,1)))
print(json.dumps({"changed": changed, "of": len(docs), "tell_increasing": len(emitted), "samples": emitted[:3]}, indent=1))
