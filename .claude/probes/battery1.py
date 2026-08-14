"""Battery 1: cross-surface + shape invariants on the public API."""
import json, os
os.environ["UNTELL_LITE_NO_TORCH"] = "1"
from untell.scripts.run import untell_text
from untell.scripts.score import score_text
from untell.scripts.tells import score_tells

T = "The system utilizes a comprehensive methodology throughout the year. Additionally, the platform empowers users to streamline their daily workflows considerably."

out = {}
# 1. untell_text result keys stable across runs
r1 = untell_text(T, tier="lite", max_iters=1, seed=1)
r2 = untell_text(T, tier="lite", max_iters=1, seed=2)
out["keys_stable_across_seeds"] = sorted(r1) == sorted(r2)

# 2. tells count = sum of by_category counts
t = score_tells(T)
out["tells_eq_sum_categories"] = t["tells"] == sum(t["by_category"].values())

# 3. tells_per_100w consistency
words = len(T.split())
out["tells_per_100w_consistent"] = abs(t["tells_per_100w"] - 100.0 * t["tells"] / max(1, words)) < 1e-9

# 4. score max in [0,1]
s = score_text(T, tier="lite")
out["score_max_in_range"] = 0.0 <= s["max"] <= 1.0

# 5. flagged consistent with threshold
out["flagged_consistent"] = (s["flagged"] == (s["max"] >= s["threshold"]))

# 6. untell_text final round-trips through lock/restore losslessly (layout preserved)
from untell.scripts.preserve import lock, restore
m, mp = lock(r1["final"])
out["final_roundtrips"] = restore(m, mp) == r1["final"]

# 7. similarity reported == fresh computation (when changed)
from untell.scripts.quality import similarity
r3 = untell_text(T, tier="lite", max_iters=2, seed=5, rewriter="structural")
if r3.get("changed"):
    out["similarity_reproducible"] = abs(r3["similarity"] - similarity(T, r3["final"])) < 1e-9
else:
    out["similarity_reproducible"] = True

print(json.dumps(out, indent=1))
