import json
from untell.rewriter.composite import _intensity_sweep

viol = []
for n in range(1, 12):
    for k in range(0, 61):
        base = round(0.40 + k * 0.01, 2)
        out = _intensity_sweep(base, n)
        if len(out) != n: viol.append(f"len n={n} base={base}")
        if len(set(out)) != len(out): viol.append(f"dupe n={n} base={base}: {[round(v,3) for v in out]}")
        if any(v < 0.4 - 1e-9 or v > 1.0 + 1e-9 for v in out): viol.append(f"range n={n} base={base}")
        if not any(abs(v - base) < 1e-9 for v in out): viol.append(f"base missing n={n} base={base}")
        if any(out[i] > out[i+1] + 1e-9 for i in range(len(out)-1)): viol.append(f"unsorted n={n} base={base}: {[round(v,3) for v in out]}")
print(json.dumps({"violations": viol[:10], "total": len(viol)}, indent=1))
