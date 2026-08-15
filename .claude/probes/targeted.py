import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.targeted import TargetedRewriter, split_sentences

out = {}
out["split_2"] = split_sentences("First sentence. Second sentence.") == ["First sentence. ", "Second sentence."]
out["split_1"] = len(split_sentences("Only one here.")) == 1
# non-scoreable tier defers to inner wholesale
rw = TargetedRewriter(min_score=0.30)
t = "First flagged sentence here. Second plain sentence."
r = rw.rewrite(t, {"tier": "bogus"}, 0.30)
out["defer_runs"] = isinstance(r, str) and len(r) > 0
# single sentence with sentinel protection
t2 = "The trial enrolled 123 patients in the study."
r2 = rw.rewrite(t2, {"tier": "lite"}, 0.30)
out["single_valid"] = isinstance(r2, str) and len(r2) > 0
# two sentences where inner is harmless
t3 = "The system reads the file. The parser splits it."
r3 = rw.rewrite(t3, {"tier": "lite"}, 0.30)
out["multi_valid"] = isinstance(r3, str) and len(r3) > 0 and "reads the file" in r3
print(json.dumps(out, indent=1))
