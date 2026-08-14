"""Exact round-trip + idempotency, done right."""
import json
from untell.scripts.preserve import lock, restore

CASES = [
    "The effect held (Smith, 2019; Jones, 2020) across every site tested. See https://example.com/a and 12 March 2019.",
    "Model ABCDEF1 shipped in 2024 with CD4+ cells at 37.5 C. The digest was a3f5b2c9d8e14f6072b3c4d5e6f70819.",
    "Call np.float64 at 3 p.m. (e.g. two of them). Use --tier full or set UNTELL_ENABLE_RADAR=1.",
]
out = {}
for i, t in enumerate(CASES):
    m1, map1 = lock(t)
    rt1 = restore(m1, map1)                 # canonical: restore with ITS OWN mapping
    m2, map2 = lock(m1)                     # lock the masked text
    rt2 = restore(m2, map2)                 # should give m1 back
    out[f"case{i}_roundtrip_own_map"] = (rt1 == t)
    out[f"case{i}_lock_idempotent"] = (m1 == m2)
    out[f"case{i}_restore_second_returns_first"] = (rt2 == m1)
print(json.dumps(out, indent=1))
