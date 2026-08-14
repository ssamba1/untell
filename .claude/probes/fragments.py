"""Fragment detection: does the rewriter emit sentence fragments (no finite verb / orphaned subordinate clause)?"""
import json, os, re
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.rewriter.structural import StructuralRewriter
from untell.text_split import split_sentences

rw = StructuralRewriter()
text = open(".claude/corpora/hc3-human.txt", encoding="utf-8").read()
sents = [s for s in split_sentences(text) if len(s.split()) >= 8][:60]

FINITE = re.compile(r"\b(?:is|are|was|were|has|have|had|do|does|did|will|would|can|could|may|might|shall|should|must|am|be|been|being|seems?|appears?|becomes?|remains?)\b", re.I)
SUBORD = re.compile(r"^(?:although|though|while|because|since|whereas|unless|if|when|where|as|even though|despite)\b", re.I)

fragments = []
for s in sents:
    out = rw.rewrite(s, {"max": 0.9}, 0.3, intensity=1.0)
    if not out or out == s:
        continue
    for sent in split_sentences(out):
        w = sent.strip().rstrip(".!?").strip()
        if not w or len(w.split()) < 4:
            continue
        # fragment = starts with subordinator AND has no finite verb, or no finite verb at all
        no_finite = not FINITE.search(w)
        if no_finite or SUBORD.match(w) and not FINITE.search(w):
            fragments.append((s[:40], out[:80], sent[:60]))
print(json.dumps({
    "swept": len(sents),
    "possible_fragments": len(fragments),
    "samples": fragments[:6],
}, indent=1))
