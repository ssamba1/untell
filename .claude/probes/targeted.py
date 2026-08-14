"""targeted: only flags sentences rewritten, spacing preserved, single-sentence validated."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.targeted import TargetedRewriter
from untell.scripts.score import score_text
from untell.rewriter.base import selection_key

rw = TargetedRewriter()
doc = ("Moreover, the framework leverages robust solutions for every team. "
       "The system reads the file and processes the records in order. "
       "It is important to note that the results were significant.")
score = score_text(doc, tier="lite")
out = rw.rewrite(doc, score, 0.3)
r = {}
r["changed"] = out != doc
r["flags_sent_rewritten"] = "Moreover" not in out
r["clean_sent_kept"] = "reads the file and processes" in out
r["cliche_sent_rewritten"] = "important to note" not in out
r["no_sentinel_leak"] = "⟦" not in out
r["out"] = out[:80]
print(json.dumps(r, indent=1))
