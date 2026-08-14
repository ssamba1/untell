"""How often does the sweep emit duplicate intensities (wasted draws) across the contract space?"""
import json
from untell.rewriter.composite import _intensity_sweep

dupe_cases = []
for n in range(2, 9):
    for k in range(0, 61):  # base from 0.40 to 1.00 in 0.01 steps
        base = round(0.40 + k * 0.01, 2)
        out = _intensity_sweep(base, n)
        if len(set(out)) != len(out):
            dupe_cases.append((base, n, [round(v,2) for v in out]))
print(json.dumps({
    "dupe_cases": len(dupe_cases),
    "samples": dupe_cases[:8],
    "default_best_of3": _intensity_sweep(0.7, 3),
}, indent=1))
