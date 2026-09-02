import sys; sys.path.insert(0, "/home/user/untell")
import json, os, collections
os.environ.setdefault("UNTELL_CORPUS_DIR", "/tmp/claude-0/-home-user-untell/3e0b1f88-0a73-52df-abb0-f51a6b6448de/scratchpad/m4cache")
from eval.datasets import load_m4
from eval.subgroup_audit import equalised_odds
STEMS = ("arxiv_chatGPT","arxiv_davinci","arxiv_bloomz","wikipedia_chatgpt","reddit_chatGPT",
         "peerread_cohere","peerread_llama","germanwikipedia_chatgpt","id-newspaper_chatGPT",
         "urdu_chatGPT")
rows = load_m4(STEMS, per_file=250)
print(f"{len(rows)} rows", collections.Counter(r["is_ai"] for r in rows), flush=True)
for axis in ("language", "generator", "domain"):
    rep = equalised_odds(rows, tier="lite", threshold=0.30, axes=(axis,))
    print(f"\n===== {axis} =====", flush=True)
    print(json.dumps(rep, indent=1)[:4000], flush=True)
