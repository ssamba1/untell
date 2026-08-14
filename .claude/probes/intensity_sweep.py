"""_intensity_sweep invariants over the FULL parameter space: base always present, in-range, monotone."""
import json
from untell.rewriter.composite import _intensity_sweep

violations = []
for n in range(1, 12):
    for base in [0.0, 0.1, 0.25, 0.4, 0.5, 0.7, 0.9, 1.0, 1.5]:
        out = _intensity_sweep(base, n)
        if len(out) != n:
            violations.append(f"n={n} base={base}: len {len(out)} != {n}")
            continue
        if not any(abs(v - base) < 1e-9 for v in out):
            # base below 0.4 or above 1.0 is clamped; the CLAIM is base present when in-range
            if 0.4 <= base <= 1.0:
                violations.append(f"n={n} base={base}: base missing {out}")
        if any(v < 0.4 or v > 1.0 for v in out):
            violations.append(f"n={n} base={base}: out of range {out}")
        # monotone non-decreasing
        if any(out[i] > out[i+1] + 1e-9 for i in range(len(out)-1)):
            violations.append(f"n={n} base={base}: not sorted {out}")
print(json.dumps({"violations": violations[:10], "total_violations": len(violations)}, indent=1))
