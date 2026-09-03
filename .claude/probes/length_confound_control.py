"""Does document length confound every false-positive rate in this document?

None of Results 1-26 control for it, and untell warns that short text is unreliable. If FPR varies
strongly with length AND the corpora differ in length, then some 'corpus' and 'subgroup' effects
are length effects wearing a label.
"""
import sys, os, json, random, statistics
sys.path.insert(0, "/home/user/untell")
os.environ.setdefault("UNTELL_CORPUS_DIR",
                      "/tmp/claude-0/-home-user-untell/3e0b1f88-0a73-52df-abb0-f51a6b6448de/scratchpad/m4cache")
from untell.scripts.score import score_text
from eval.subgroup_audit import _usable_score, wilson
from eval.datasets import load_labelled

rows = load_labelled("asap"); random.Random(11).shuffle(rows)
scored = []
for r in rows[:1500]:
    s = _usable_score(score_text(r["text"], tier="lite", threshold=0.30))
    if s is not None:
        scored.append((len(r["text"].split()), s))
print(f"{len(scored)} ASAP essays scored")
bands = [(0,200),(200,300),(300,400),(400,550),(550,10**6)]
print(f"\n{'words':>14} {'n':>5} {'FPR@0.30':>10}  95% CI")
out = []
for lo, hi in bands:
    v = [s for w, s in scored if lo <= w < hi]
    if len(v) < 30: continue
    fp = sum(1 for s in v if s >= 0.30)
    l, h = wilson(fp, len(v))
    out.append({"band": f"{lo}-{hi}", "n": len(v), "fpr": round(fp/len(v), 4)})
    print(f"{lo:>6}-{hi if hi<10**6 else '+':<7} {len(v):>5} {fp/len(v):>9.1%}  [{l:.1%}-{h:.1%}]")
# Correlation between length and score
ws = [w for w, s in scored]; ss = [s for w, s in scored]
mw, ms = statistics.mean(ws), statistics.mean(ss)
num = sum((w-mw)*(s-ms) for w, s in scored)
den = (sum((w-mw)**2 for w in ws) * sum((s-ms)**2 for s in ss)) ** 0.5
print(f"\n  Pearson r(words, score) = {num/den:+.3f}   n={len(scored)}")
json.dump(out, open('/tmp/claude-0/-home-user-untell/3e0b1f88-0a73-52df-abb0-f51a6b6448de/scratchpad/length.json','w'), indent=1)
