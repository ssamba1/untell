"""Compare benchmark results against the previous baseline from gh-pages."""
from __future__ import annotations

import json
import sys

try:
    with open("prev.json") as f:
        prev = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    print("No previous benchmark found — saving baseline.")
    sys.exit(0)

with open("benchmark-result.json") as f:
    cur = json.load(f)

print("=== BENCHMARK COMPARISON ===")
regressions = []
for strategy, prev_rate in prev.get("bypass_rates", {}).items():
    cur_rate = cur.get("bypass_rates", {}).get(strategy, 0)
    delta = cur_rate - prev_rate
    arrow = "↑" if delta > 0.05 else ("↓" if delta < -0.05 else "→")
    print(f"  {strategy:15} {prev_rate:.0%} → {cur_rate:.0%}  {arrow}")
    if cur_rate < prev_rate - 0.1:
        regressions.append(strategy)

if regressions:
    print(f"REGRESSION detected: {regressions}")
    sys.exit(1)
else:
    print("No regressions — all clear.")
