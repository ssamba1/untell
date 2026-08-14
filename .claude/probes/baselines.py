"""baselines: rewrite strength bounds, noop/single_pass contracts, LoopResult shape."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from eval.baselines import rewrite, noop, single_pass, LoopResult

out = {}
# 1. strength 0 normalizes whitespace but keeps content words
t = "The system reads\nthe file.\n\nThe parser splits it."
r0 = rewrite(t, 0.0)
out["s0_normalizes"] = "\n" not in r0
out["s0_keeps_words"] = "system" in r0 and "parser" in r0
# 2. strength 1 merges more (shorter output, more commas)
r1 = rewrite("The system reads the file. The parser splits it. The loader writes it.", 1.0)
out["s1_merges"] = r1.count(",") > rewrite("The system reads the file. The parser splits it. The loader writes it.", 0.0).count(",")
# 3. noop returns LoopResult with text == input
n = noop("Some input text here for the test.")
out["noop_shape"] = isinstance(n, LoopResult) and n.text == "Some input text here for the test."
# 4. single_pass runs the rewrite once
sp = single_pass("The system reads the file. The parser splits it into records. The loader writes them to the store.")
out["single_pass_ran"] = isinstance(sp, LoopResult) and sp.text != ""
print(json.dumps(out, indent=1))
