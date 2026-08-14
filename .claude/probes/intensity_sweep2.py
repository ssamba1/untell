"""In-contract bases only (0.4..1.0): all invariants must hold."""
import json
from untell.rewriter.composite import _intensity_sweep

violations = []
for n in range(1, 12):
    for base in [0.4, 0.45, 0.5, 0.55, 0.7, 0.85, 0.9, 0.95, 1.0]:
        out = _intensity_sweep(base, n)
        if len(out) != n:
            violations.append(f"len {len(out)} != {n} at base={base}")
        if not any(abs(v - base) < 1e-9 for v in out):
            violations.append(f"base {base} missing at n={n}: {[round(v,3) for v in out]}")
        if any(v < 0.4 - 1e-9 or v > 1.0 + 1e-9 for v in out):
            violations.append(f"out of range at n={n} base={base}: {[round(v,3) for v in out]}")
        if any(out[i] > out[i+1] + 1e-9 for i in range(len(out)-1)):
            violations.append(f"not sorted at n={n} base={base}")
print(json.dumps({"in_contract_violations": violations[:10], "total": len(violations)}, indent=1))
