import sys, os, json
sys.path.insert(0, "/home/user/untell")
os.environ.setdefault("UNTELL_CORPUS_DIR", "/tmp/claude-0/-home-user-untell/3e0b1f88-0a73-52df-abb0-f51a6b6448de/scratchpad/m4cache")
from eval.datasets import load_m4
from eval.subgroup_audit import _usable_score, wilson
from untell.scripts.score import score_text
STEMS = ("arxiv_chatGPT","arxiv_davinci","arxiv_bloomz","wikipedia_chatgpt","reddit_chatGPT",
         "peerread_cohere","peerread_llama")
rows = [r for r in load_m4(STEMS, per_file=250) if r["language"] == "en"]
scored = []
for r in rows:
    s = _usable_score(score_text(r["text"], tier="lite", threshold=0.30))
    if s is not None:
        scored.append((s, r["is_ai"]))
H = [s for s, ai in scored if not ai]; A = [s for s, ai in scored if ai]
print(f"{len(scored)} scored: {len(H)} human, {len(A)} machine", flush=True)
# AUROC by rank (Mann-Whitney), ties at 0.5
import bisect
As = sorted(A)
wins = sum(bisect.bisect_left(As, h) + 0.5*(bisect.bisect_right(As, h)-bisect.bisect_left(As, h))
           for h in H)
auroc = 1 - wins/(len(H)*len(A))
print(f"AUROC = {auroc:.4f}", flush=True)
print(f"\n{'thr':>6} {'FPR':>18} {'FNR':>18}  usable?")
for thr in (0.20,0.30,0.40,0.45,0.50,0.60,0.70,0.775,0.90):
    fp = sum(1 for s in H if s >= thr); fn = sum(1 for s in A if s < thr)
    fpr, fnr = fp/len(H), fn/len(A)
    fl, fh = wilson(fp, len(H)); nl, nh = wilson(fn, len(A))
    ok = "YES" if fpr < 0.05 and fnr < 0.25 else "no"
    print(f"{thr:>6} {fpr:7.1%} [{fl:.1%}-{fh:.1%}] {fnr:7.1%} [{nl:.1%}-{nh:.1%}]  {ok}")
json.dump({"auroc": round(auroc,4), "human_n": len(H), "ai_n": len(A)},
          open('/tmp/claude-0/-home-user-untell/3e0b1f88-0a73-52df-abb0-f51a6b6448de/scratchpad/m4_roc.json','w'))
