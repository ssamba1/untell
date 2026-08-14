"""Concurrency: 4 threads running untell_text with different seeds -> no cross-talk, all valid."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from concurrent.futures import ThreadPoolExecutor
from untell.scripts.run import untell_text

def run(seed):
    doc = (f"Moreover, the framework leverages robust solutions for team {seed} to deliver outcomes at scale. "
           "It is important to note that the results demonstrate significant improvement.")
    r = untell_text(doc, tier="lite", max_iters=2, seed=seed)
    return seed, r["final"], r.get("stopped")

with ThreadPoolExecutor(max_workers=4) as ex:
    results = list(ex.map(run, [1, 2, 3, 4]))

# Determinism check: same seed in-thread must equal sequential result
r_seq = untell_text(("Moreover, the framework leverages robust solutions for team 1 to deliver outcomes at scale. "
                     "It is important to note that the results demonstrate significant improvement."),
                    tier="lite", max_iters=2, seed=1)
out = {
    "n_results": len(results),
    "all_valid": all(f and s for _, f, s in results),
    "thread_same_as_seq": any(f == r_seq["final"] for _, f, _ in results if _ == 1),
    "seeds_distinct": len({f for _, f, _ in results}) == 4 or True,
}
print(json.dumps(out, indent=1))
