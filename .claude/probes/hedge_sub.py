import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.structural import _HEDGE_RE

out = {}
out["adverb_removed"] = _HEDGE_RE.sub(r"\1", "This could potentially work.")
out["may_kept"] = _HEDGE_RE.sub(r"\1", "It may eventually arrive.")
out["upper_kept"] = _HEDGE_RE.sub(r"\1", "This COULD POTENTIALLY work.")
out["no_match"] = _HEDGE_RE.sub(r"\1", "The system reads the file.")
out["double"] = _HEDGE_RE.sub(r"\1", "It could potentially and may eventually improve.")
print(json.dumps(out, indent=1))
