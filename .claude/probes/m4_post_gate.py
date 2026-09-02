import sys, os, json, collections
sys.path.insert(0, "/home/user/untell")
os.environ.setdefault("UNTELL_CORPUS_DIR", "/tmp/claude-0/-home-user-untell/3e0b1f88-0a73-52df-abb0-f51a6b6448de/scratchpad/m4cache")
from eval.datasets import load_m4
from eval.subgroup_audit import equalised_odds, _usable_score
from untell.scripts.score import score_text
STEMS = ("arxiv_chatGPT","arxiv_davinci","arxiv_bloomz","wikipedia_chatgpt","reddit_chatGPT",
         "peerread_cohere","peerread_llama","germanwikipedia_chatgpt","id-newspaper_chatGPT",
         "urdu_chatGPT","arabic_chatGPT","russian_chatGPT",
         "bulgarian_true_and_fake_news_chatGPT")
rows = load_m4(STEMS, per_file=200)
ab, tot = collections.Counter(), collections.Counter()
for r in rows:
    tot[r["language"]] += 1
    if _usable_score(score_text(r["text"], tier="lite", threshold=0.30)) is None:
        ab[r["language"]] += 1
print("POST-GATE ABSTENTIONS:", flush=True)
for l in sorted(tot): print(f"  {l}: {ab[l]}/{tot[l]} = {ab[l]/tot[l]:.1%}", flush=True)
for axis in ("language","domain"):
    print(f"\n===== {axis} =====", flush=True)
    print(json.dumps(equalised_odds(rows, tier="lite", threshold=0.30, axes=(axis,)), indent=1),
          flush=True)
# English only, crossed: does the domain gap hold within one language?
en = [r for r in rows if r["language"] == "en"]
print(f"\n===== english domain x generator (n={len(en)}) =====", flush=True)
print(json.dumps(equalised_odds(en, tier="lite", threshold=0.30,
                                axes=("domain","generator","domain*generator")), indent=1),
      flush=True)
