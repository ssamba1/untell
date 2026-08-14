"""sentences.py per-sentence score aggregation: invariants on the returned list."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.sentences import score_sentences

out = {}
# 1. Empty input
out["empty"] = score_sentences("")
# 2. Normal paragraph
para = "The system reads the file first. It parses each record carefully. The loader writes them to the store. Then the process repeats for the next batch."
r = score_sentences(para)
out["para_n"] = len(r)
out["para_keys"] = sorted(r[0].keys()) if r else []
out["para_verdicts"] = [s.get("verdict") for s in r]
# 3. Score consistency: per-sentence max should match score_text of that sentence (within rounding)
from untell.scripts.score import score_text
s0 = r[0]["text"]
full = score_text(s0, tier="lite")
out["first_sentence_max"] = r[0].get("max")
out["score_text_max"] = round(full.get("max", 0), 4)
print(json.dumps(out, indent=1))
