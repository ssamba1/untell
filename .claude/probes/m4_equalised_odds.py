import sys, os, json, collections
sys.path.insert(0, "/home/user/untell")
os.environ.setdefault("UNTELL_CORPUS_DIR", "/tmp/claude-0/-home-user-untell/3e0b1f88-0a73-52df-abb0-f51a6b6448de/scratchpad/m4cache")
from eval.datasets import load_m4
from eval.subgroup_audit import equalised_odds, _usable_score
from untell.scripts.score import score_text
STEMS = ("arxiv_chatGPT","arxiv_davinci","arxiv_bloomz","wikipedia_chatgpt","reddit_chatGPT",
         "peerread_cohere","peerread_llama","germanwikipedia_chatgpt","id-newspaper_chatGPT",
         "urdu_chatGPT")
rows = load_m4(STEMS, per_file=250)
# How many rows the detector refuses outright, per language -- the number the old run buried.
refused = collections.Counter()
total = collections.Counter()
for r in rows:
    total[r["language"]] += 1
    if _usable_score(score_text(r["text"], tier="lite", threshold=0.30)) is None:
        refused[r["language"]] += 1
print("ABSTENTIONS (detector produced no score):", flush=True)
for lang in sorted(total):
    print(f"  {lang}: {refused[lang]}/{total[lang]} = {refused[lang]/total[lang]:.1%}", flush=True)
for axis in ("language", "domain", "generator"):
    print(f"\n===== {axis} =====", flush=True)
    print(json.dumps(equalised_odds(rows, tier="lite", threshold=0.30, axes=(axis,)),
                     indent=1), flush=True)
