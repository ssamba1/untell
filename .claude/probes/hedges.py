"""hedges: dropped hedge classes, polarity kept, negation count."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.hedges import dropped_hedges, certainty_kept, polarity_kept, negation_count

out = {}
# Dropping 'might' -> 'will' should flag a dropped hedge
src = "The results might suggest a clear improvement in the group."
cand = "The results will suggest a clear improvement in the group."
out["dropped_hedge"] = dropped_hedges(src, cand)
out["certainty_lost"] = not certainty_kept(src, cand)
# Same text keeps everything
out["same_kept"] = dropped_hedges(src, src) == [] and certainty_kept(src, src)
# Negation flip caught
a = "The data does not support the conclusion."
b = "The data supports the conclusion."
out["negation_flip"] = not polarity_kept(a, b)
out["neg_counts"] = (negation_count(a), negation_count(b))
print(json.dumps(out, indent=1))
