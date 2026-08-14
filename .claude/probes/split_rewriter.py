"""Rewriter on the quoted-period text: no dangling fragments in output."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.structural import StructuralRewriter
from untell.text_split import split_sentences

rw = StructuralRewriter()
text = 'He said "the meeting is at 3." and left. Then the team agreed.'
out = {}
s = split_sentences(text)
out["split_n"] = len(s)
out["no_fragment"] = all(len(x.split()) >= 3 for x in s)
r = rw.rewrite(text, {"max": 0.9}, 0.3)
out["rewrite_valid"] = bool(r.strip()) and "and left" in r
out["rewrite_snippet"] = r[:70]
print(json.dumps(out, indent=1))
