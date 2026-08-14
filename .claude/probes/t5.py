"""t5_paraphrase: availability gating, deterministic property."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.t5_paraphrase import T5ParaphraseRewriter

out = {}
# default construction: deterministic beam search
rw = T5ParaphraseRewriter()
out["default_deterministic"] = rw.deterministic is True
# sampled construction: not deterministic
rw2 = T5ParaphraseRewriter(sample=True)
out["sampled_not_det"] = rw2.deterministic is False
out["available_bool"] = isinstance(rw.available(), bool)
print(json.dumps(out, indent=1))
