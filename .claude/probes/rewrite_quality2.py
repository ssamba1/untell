"""Does the rewriter CREATE doubled words / grammar faults from clean inputs?"""
import json, os, re
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.structural import StructuralRewriter
from untell.text_split import split_sentences

rw = StructuralRewriter()
text = open(".claude/corpora/hc3-human.txt", encoding="utf-8").read()
sents = [s for s in split_sentences(text) if len(s.split()) >= 8][:60]

doubled_re = re.compile(r"\b(\w+)\s+\1\b", re.I)
created = []
intensities = [0.5, 0.8, 1.0]
for s in sents:
    if doubled_re.search(s):  # skip inputs that already have the fault
        continue
    for inten in intensities:
        out = rw.rewrite(s, {"max": 0.9}, 0.3, intensity=inten)
        if out and out != s and doubled_re.search(out):
            m = doubled_re.search(out)
            created.append((s[:50], out[:70], m.group(0), inten))
print(json.dumps({
    "clean_inputs_swept": len(sents),
    "doubled_created": len(created),
    "samples": created[:5],
}, indent=1))
