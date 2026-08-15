import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.structural import _merge_sentences

out = {}
# two sentences merge
s = ["The system reads the file.", "The parser splits it.", "The loader writes it."]
m = _merge_sentences(s, rate=1.0)
out["merged"] = len(m) < len(s)
out["all_words_kept"] = "system" in " ".join(m) and "loader" in " ".join(m)
# single sentence unchanged
out["single"] = _merge_sentences(["Only one sentence here."], rate=1.0) == ["Only one sentence here."]
# empty
out["empty"] = _merge_sentences([], rate=1.0) == []
# additive merge uses ', and'
s2 = ["Moreover, the system reads the file.", "The parser splits it."]
m2 = _merge_sentences(s2, rate=1.0, additive={"moreover the system reads the file"})
out["additive_connector"] = ", and" in " ".join(m2) if m2 else False
print(json.dumps(out, indent=1))
