"""Real contract: n distinct values, base present, all in [0.4, 1.0]. Order irrelevant."""
import json
from untell.rewriter.composite import _intensity_sweep

viol = []
for n in range(1, 12):
    for k in range(0, 61):
        base = round(0.40 + k * 0.01, 2)
        out = _intensity_sweep(base, n)
        if len(out) != n: viol.append(f"len n={n} base={base}")
        if len(set(round(v,6) for v in out)) != n: viol.append(f"dupe n={n} base={base}: {[round(v,4) for v in out]}")
        if any(v < 0.4 - 1e-9 or v > 1.0 + 1e-9 for v in out): viol.append(f"range n={n} base={base}")
        if not any(abs(v - base) < 1e-6 for v in out): viol.append(f"base missing n={n} base={base}: {[round(v,4) for v in out]}")
print(json.dumps({"violations": viol[:8], "total": len(viol)}, indent=1))
