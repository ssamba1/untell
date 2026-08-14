"""EnsembleRewriter: output must be >= its members (never worse than best member) — but NOT worse than input on selection key."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.ensemble import EnsembleRewriter
from untell.rewriter.base import selection_key
from untell.scripts.score import score_text

# Build a 2-member ensemble: structural + surgical
from untell.rewriter.structural import StructuralRewriter
from untell.rewriter.surgical import SurgicalRewriter

rw = EnsembleRewriter([("structural", StructuralRewriter()), ("surgical", SurgicalRewriter(max_subs=6))])
docs = [
    "Moreover, the framework leverages robust solutions to deliver outcomes at scale.",
    "It is important to note that the results underscore the pivotal role of the team.",
    "The system reads the file first. The parser splits it into records. The loader writes them to the store.",
]
out = {}
for i, d in enumerate(docs):
    r = rw.rewrite(d, {"tier": "lite"})
    base = selection_key(score_text(d, tier="lite"))
    cand = selection_key(score_text(r, tier="lite"))
    out[f"doc{i}"] = {"changed": r != d, "base": round(base[0], 4), "cand": round(cand[0], 4),
                      "not_worse": cand <= base, "snippet": r[:60]}
print(json.dumps(out, indent=1))
