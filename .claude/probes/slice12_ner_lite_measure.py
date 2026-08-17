"""Slice-12 probe: re-measure preserve-NER spacy+torch load on lite at CURRENT HEAD.

Runs lock()/score_text(tier='lite') in a FRESH subprocess (so no module is imported
before the probe starts), with UNTELL_LITE_NO_TORCH=1 set or unset, and reports:
  - wall time of the first lock() call
  - which heavy modules (torch/transformers/spacy/thinc) landed in sys.modules
  - how many entity spans were locked
"""
import importlib.util
import json
import os
import subprocess
import sys
import time

PROBE = r"""
import json, os, sys, time
t0 = time.perf_counter()
from untell.scripts.preserve import _spacy_entity_spans, lock
t_import = time.perf_counter() - t0

text = ("Alice met Bob at the ACME office in Berlin on Monday. "
        "As Smith (2020) reported, 47% of cases rose $500, and 1.2e-3 m is small.")

t0 = time.perf_counter()
spans = _spacy_entity_spans(text)
t_spans = time.perf_counter() - t0

t0 = time.perf_counter()
masked, mapping = lock(text)
t_lock = time.perf_counter() - t0

heavy = {m: (m in sys.modules) for m in ("torch", "transformers", "spacy", "thinc")}
print(json.dumps({
    "lite_pinned": os.environ.get("UNTELL_LITE_NO_TORCH") == "1",
    "t_import_preserve": round(t_import, 3),
    "t_first_spans_call": round(t_spans, 3),
    "t_first_lock_call": round(t_lock, 3),
    "n_entity_spans": len(spans),
    "n_locked_spans": len(mapping),
    "heavy_in_sys_modules": heavy,
}))
"""


def run(label: str, env_extra: dict) -> dict:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    # env_extra with value None means "explicitly UNSET this var"
    for k, v in list(env_extra.items()):
        if v is None:
            env.pop(k, None)
            del env_extra[k]
    env.update(env_extra)
    t0 = time.perf_counter()
    out = subprocess.run(
        [sys.executable, "-c", PROBE],
        capture_output=True, text=True, env=env, timeout=300,
    )
    wall = time.perf_counter() - t0
    result = {"label": label, "wall_total": round(wall, 3), "rc": out.returncode}
    if out.returncode != 0:
        result["stderr_tail"] = out.stderr[-800:]
        return result
    result.update(json.loads(out.stdout.strip().splitlines()[-1]))
    return result


def main():
    results = []
    # (1) lite path with the env var pinned — the documented lite contract
    results.append(run("UNTELL_LITE_NO_TORCH=1 (lite)", {"UNTELL_LITE_NO_TORCH": "1"}))
    # (2) same call with the env var UNSET — what lite used to pay / full tier pays
    results.append(run("env unset (full/torch)", {"UNTELL_LITE_NO_TORCH": None}))
    print(json.dumps(results, indent=2))
    for r in results:
        if "stderr_tail" in r:
            print(f"\n--- {r['label']} stderr ---\n{r['stderr_tail']}", file=sys.stderr)
    # also report whether the heavy libs exist in this venv (so the "not imported" is meaningful)
    print("installed:", {m: importlib.util.find_spec(m) is not None
                         for m in ("torch", "transformers", "spacy", "thinc", "en_core_web_sm")})


if __name__ == "__main__":
    main()
