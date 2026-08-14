"""Novel invariants: lock idempotency + restore exactness + similarity symmetry."""
import json
from untell.scripts.preserve import lock, restore
from untell.scripts.quality import similarity

CASES = [
    "The effect held (Smith, 2019; Jones, 2020) across every site tested. See https://example.com/a and 12 March 2019.",
    "Model ABCDEF1 shipped in 2024 with CD4+ cells at 37.5 C. The digest was a3f5b2c9d8e14f6072b3c4d5e6f70819.",
    "Call np.float64 at 3 p.m. (e.g. two of them). Use --tier full or set UNTELL_ENABLE_RADAR=1.",
]
results = {}
for i, t in enumerate(CASES):
    m1, map1 = lock(t)
    m2, map2 = lock(m1)   # lock on masked text: sentinels must be claimed first
    restored = restore(m2, map2)
    results[f"case{i}_lock_idempotent"] = (m1 == m2)
    results[f"case{i}_restore_exact"] = (restored == t)

# similarity symmetry: sim(a,b) == sim(b,a)?
a = "The system utilizes a comprehensive methodology throughout the year."
b = "The system uses a wide-ranging methodology throughout the year."
s_ab = similarity(a, b)
s_ba = similarity(b, a)
results["sim_symmetric"] = (s_ab == s_ba)
results["sim_ab"] = round(s_ab, 6)
results["sim_ba"] = round(s_ba, 6)
print(json.dumps(results, indent=1))
