"""Rewriter output quality sweep on REAL corpus text: grammar faults + doubled words + fragments."""
import json, os, re
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.structural import StructuralRewriter
from untell.scripts.tells import score_tells
from untell.text_split import split_sentences

rw = StructuralRewriter()
text = open(".claude/corpora/hc3-human.txt", encoding="utf-8").read()
sents = [s for s in split_sentences(text) if len(s.split()) >= 8][:60]

faults = {"doubled_word": [], "empty_out": [], "unchanged": [], "lowercase_start_after_period": []}
emitted_tells = []
doubled_re = re.compile(r"\b(\w+)\s+\1\b", re.I)
cap_re = re.compile(r"[.!?]\s+[a-z]")
for s in sents:
    out = rw.rewrite(s, {"max": 0.9}, 0.3)
    if not out or not out.strip():
        faults["empty_out"].append(s[:50]); continue
    if out == s:
        faults["unchanged"].append(s[:50]); continue
    if doubled_re.search(out):
        faults["doubled_word"].append((s[:40], out[:60]))
    # tell check on the output
    t = score_tells(out)
    if t.get("tells_per_100w", 0) > 12:
        emitted_tells.append((s[:40], round(t["tells_per_100w"],1)))
print(json.dumps({
    "sentences_swept": len(sents),
    "doubled_word": len(faults["doubled_word"]),
    "empty_out": len(faults["empty_out"]),
    "unchanged": len(faults["unchanged"]),
    "samples_doubled": faults["doubled_word"][:3],
    "high_tell_outputs": len(emitted_tells),
    "high_tell_samples": emitted_tells[:3],
}, indent=1))
