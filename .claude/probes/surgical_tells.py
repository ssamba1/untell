"""surgical rewriter: does any substitution EMIT a catalogued tell? And does it ever break an article?"""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.surgical import SurgicalRewriter
from untell.scripts.tells import score_tells

rw = SurgicalRewriter(max_subs=12)
text = open(".claude/corpora/hc3-human.txt", encoding="utf-8").read()
sents = [s for s in text.replace("\n", " ").split(".") if len(s.split()) >= 8][:40]

emitted = []
for s in sents:
    out = rw.rewrite(s, {"max": 0.9}, 0.3)
    if not out or out == s:
        continue
    before = score_tells(s).get("tells_per_100w", 0)
    after = score_tells(out).get("tells_per_100w", 0)
    if after > before + 1.0:  # materially MORE tells after
        emitted.append((s[:40], out[:60], round(before,1), round(after,1)))
print(json.dumps({
    "swept": len(sents),
    "changed": sum(1 for s in sents if rw.rewrite(s, {"max":0.9}, 0.3) not in (None, s) for _ in [0]),
    "tell_increasing_substitutions": len(emitted),
    "samples": emitted[:4],
}, indent=1))
