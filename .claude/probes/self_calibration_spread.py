"""Result 21's method, applied to untell's own detector.

RAID makes every submission publish the threshold at which its false-positive rate on human text
is 5%, PER DOMAIN, and the median detector needs those to span 0.610 of its score range. This asks
the same question of the lite tier across every human corpus this repository can reach.
"""
import sys, os, json, csv
sys.path.insert(0, "/home/user/untell")
os.environ.setdefault("UNTELL_CORPUS_DIR",
                      "/tmp/claude-0/-home-user-untell/3e0b1f88-0a73-52df-abb0-f51a6b6448de/scratchpad/m4cache")
from untell.scripts.score import score_text
from eval.subgroup_audit import _usable_score

def scores(texts, cap=400):
    out = []
    for t in texts[:cap]:
        s = _usable_score(score_text(t, tier="lite", threshold=0.30))
        if s is not None:
            out.append(s)
    return out

def threshold_for_fpr(vals, target=0.05):
    """Lowest threshold whose false-positive rate on this human corpus is <= target."""
    v = sorted(vals, reverse=True)
    k = int(len(v) * target)          # how many flags the target allows
    return round(v[k], 4) if k < len(v) else 1.0

import random
from eval.datasets import load_labelled, load_liang, load_m4
corpora = {}

e = load_labelled("ellipse"); random.Random(7).shuffle(e)
corpora["ELLIPSE (ESL student essays)"] = [r["text"] for r in e]
a = load_labelled("asap"); random.Random(7).shuffle(a)
corpora["ASAP (US school essays)"] = [r["text"] for r in a]
lg = [r for r in load_liang() if r["population"] != "toefl_gpt4_polished"]
corpora["Liang (TOEFL/8th/CS224N)"] = [r["text"] for r in lg]
m4 = [r for r in load_m4(("arxiv_chatGPT","wikipedia_chatgpt","reddit_chatGPT","peerread_cohere"),
                         per_file=200) if r["language"] == "en" and not r["is_ai"]]
corpora["M4 (arxiv/wiki/reddit/peerread)"] = [r["text"] for r in m4]
with open('/tmp/claude-0/-home-user-untell/3e0b1f88-0a73-52df-abb0-f51a6b6448de/scratchpad/pelic.csv',
          encoding="utf-8", errors="replace") as fh:
    pel = [r["text"] for r in csv.DictReader(fh) if len((r.get("text") or "").split()) >= 60]
random.Random(7).shuffle(pel)
corpora["PELIC (adult ESL, Pittsburgh)"] = pel

print(f"{'corpus':34} {'n':>5}  {'thr for 5% FPR':>14}  {'FPR @0.30':>10}")
rows = []
for name, texts in corpora.items():
    v = scores(texts)
    if len(v) < 100:
        print(f"{name:34} {len(v):>5}  too few"); continue
    t5 = threshold_for_fpr(v)
    at30 = sum(1 for s in v if s >= 0.30) / len(v)
    rows.append({"corpus": name, "n": len(v), "threshold_5pct_fpr": t5, "fpr_at_shipped_030": round(at30, 4)})
    print(f"{name:34} {len(v):>5}  {t5:>14.4f}  {at30:>9.1%}")
ts = [r["threshold_5pct_fpr"] for r in rows]
print(f"\n  span {max(ts)-min(ts):.4f} of the 0-1 score range   ({min(ts):.4f} - {max(ts):.4f})")
print(f"  RAID's 46 detectors, median span across 8 domains: 0.610")
json.dump(rows, open('/tmp/claude-0/-home-user-untell/3e0b1f88-0a73-52df-abb0-f51a6b6448de/scratchpad/self_calib.json','w'), indent=1)
