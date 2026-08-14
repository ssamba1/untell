"""Precise: identical doc, same seed, threaded vs sequential."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from concurrent.futures import ThreadPoolExecutor
from untell.scripts.run import untell_text

DOC = ("Moreover, the framework leverages robust solutions for team 1 to deliver outcomes at scale. "
       "It is important to note that the results demonstrate significant improvement.")

def run(seed):
    r = untell_text(DOC, tier="lite", max_iters=2, seed=seed)
    return seed, r["final"]

r_seq = untell_text(DOC, tier="lite", max_iters=2, seed=1)
with ThreadPoolExecutor(max_workers=4) as ex:
    results = list(ex.map(run, [1, 1, 2, 3]))

threaded_seed1 = [f for s, f in results if s == 1]
out = {
    "seq": r_seq["final"],
    "threaded_seed1": threaded_seed1,
    "thread1_matches_seq": threaded_seed1 == [r_seq["final"]] * len(threaded_seed1),
    "distinct_across_seeds": len({f for _, f in results}) >= 2,
}
print(json.dumps(out, indent=1)[:600])
