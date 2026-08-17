"""Slice-12 probe: end-to-end lite scoring under UNTELL_LITE_NO_TORCH=1 at HEAD.

Measures whether the full score_text(tier='lite') path (detectors + quality gate +
preserve re-lock) imports any heavy module, and its wall time. Fresh subprocess.
"""
import json
import os
import subprocess
import sys
import time

PROBE = r"""
import json, os, sys, time
from untell.scripts.score import score_text

t0 = time.perf_counter()
r = score_text(
    "Alice met Bob at the ACME office in Berlin on Monday. "
    "As Smith (2020) reported, 47% of cases rose $500.",
    tier="lite",
)
t_score = time.perf_counter() - t0

heavy = {m: (m in sys.modules) for m in ("torch", "transformers", "spacy", "thinc")}
print(json.dumps({
    "lite_pinned": os.environ.get("UNTELL_LITE_NO_TORCH") == "1",
    "t_score_text_lite": round(t_score, 3),
    "score_keys": sorted(r.keys()) if isinstance(r, dict) else type(r).__name__,
    "heavy_in_sys_modules": heavy,
}))
"""


def run(label: str, env_extra: dict) -> dict:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    for k, v in list(env_extra.items()):
        if v is None:
            env.pop(k, None)
            del env_extra[k]
    env.update(env_extra)
    t0 = time.perf_counter()
    out = subprocess.run([sys.executable, "-c", PROBE], capture_output=True,
                         text=True, env=env, timeout=300)
    wall = time.perf_counter() - t0
    result = {"label": label, "wall_total": round(wall, 3), "rc": out.returncode}
    if out.returncode != 0:
        result["stderr_tail"] = out.stderr[-500:]
        return result
    result.update(json.loads(out.stdout.strip().splitlines()[-1]))
    return result


if __name__ == "__main__":
    results = [run("UNTELL_LITE_NO_TORCH=1 score lite", {"UNTELL_LITE_NO_TORCH": "1"})]
    print(json.dumps(results, indent=2))