"""Measure, record, and compare — without changing anything.

The audit lanes make the repo harder to break. They cannot tell you whether it still works,
because "works" here is a number with a spread: the free rewriters are randomised, so one run
carries roughly +/-0.02 on the score and +/-0.08 on the flagged rate, wider than most real
changes. A single run is not evidence, and a small model reading one will report a win.

This lane edits nothing. It runs a named measurement at fixed settings, checks the result is
alive before believing it, appends it to a ledger, and compares against the last run of the
SAME recipe using the spread each run reports. Drift beyond noise gets said out loud; drift
inside it gets recorded and called noise.

    python .claude/research.py list
    python .claude/research.py run lite-builtin
    python .claude/research.py show lite-builtin

Every row carries its corpus, its tier and its repeat count, because a number without those
is a number about nothing. The ledger is data a human can cite; this script never edits the
documents that quote it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / ".claude" / "measurements.jsonl"
PY = sys.executable

# Fixed settings per recipe: a measurement whose parameters drift is not comparable with the
# one before it, which is the whole point of keeping the argv here rather than in a prompt.
#
# `metrics` are the fields tracked over time. `spread` names the field reporting this run's
# own standard deviation, and is what decides whether a change is real. `liveness` are
# conditions that must hold for the numbers to describe anything at all — a dead rewriter
# produces post == pre and sails through every comparison looking stable.
RECIPES: dict[str, dict] = {
    "lite-builtin": {
        "why": "cheap, reproducible, no model download: proves the pipeline still runs end to end",
        "argv": ["-m", "eval.ceiling", "--rewriter", "composite", "--tier", "lite",
                 "--repeats", "3", "--json"],
        "metrics": ["pre_flagged_rate", "post_flagged_rate", "pre_mean_max", "post_mean_max"],
        "spread": "post_mean_max_stdev",
        "liveness": ["rewriter_available", "rewrote", "n"],
        "minutes": 5,
    },
    "lite-hc3": {
        "why": "same cheap tier against REAL generated text; the builtin corpus is measurably easier",
        "argv": ["-m", "eval.ceiling", "--dataset", "hc3", "--n", "10", "--rewriter", "composite",
                 "--tier", "lite", "--repeats", "3", "--json"],
        "metrics": ["pre_flagged_rate", "post_flagged_rate", "pre_mean_max", "post_mean_max"],
        "spread": "post_mean_max_stdev",
        "liveness": ["rewriter_available", "rewrote", "n"],
        "minutes": 20,
    },
    "full-hc3-composite": {
        "why": "the headline number: real detectors, real text, the default rewriter",
        "argv": ["-m", "eval.ceiling", "--dataset", "hc3", "--n", "6", "--rewriter", "composite",
                 "--tier", "full", "--repeats", "3", "--workers", "2", "--json"],
        "metrics": ["pre_flagged_rate", "post_flagged_rate", "pre_mean_max", "post_mean_max"],
        "spread": "post_mean_max_stdev",
        "liveness": ["rewriter_available", "rewrote", "n"],
        "minutes": 90,
    },
    "full-hc3-neural": {
        "why": "the frontier, and four times as variable as composite - never quote it from one run",
        "argv": ["-m", "eval.ceiling", "--dataset", "hc3", "--n", "6", "--rewriter", "neural",
                 "--tier", "full", "--repeats", "3", "--workers", "2", "--json"],
        "metrics": ["pre_flagged_rate", "post_flagged_rate", "pre_mean_max", "post_mean_max"],
        "spread": "post_mean_max_stdev",
        "liveness": ["rewriter_available", "rewrote", "n"],
        "minutes": 120,
    },
    "full-hc3-max": {
        "why": "best-of-all-backends; the selector here once shipped as a no-op because a "
               "detector saturated at exactly 1.0 and `cand < best` never fired",
        "argv": ["-m", "eval.ceiling", "--dataset", "hc3", "--n", "6", "--rewriter", "max",
                 "--tier", "full", "--repeats", "3", "--workers", "2", "--json"],
        "metrics": ["pre_flagged_rate", "post_flagged_rate", "pre_mean_max", "post_mean_max"],
        "spread": "post_mean_max_stdev",
        "liveness": ["rewriter_available", "rewrote", "n"],
        "minutes": 120,
    },
    "detector-audit": {
        "why": "detectors AT the shipped threshold, on labelled pairs - AUROC hides calibration, "
               "and a detector flagging most HUMAN text can still separate the classes",
        "argv": ["-m", "eval.detector_audit", "--pairs", "20", "--dataset", "hc3", "--json"],
        "metrics": [],
        "spread": "",
        "liveness": [],
        "minutes": 30,
    },
    "tells-auroc": {
        "why": "per-tell discrimination on paired text; one category once pointed the wrong way "
               "and inverted the aggregate",
        "argv": ["-m", "eval.tells_auroc", "--dataset", "hc3", "--pairs", "40", "--json"],
        "metrics": [],
        "spread": "",
        "liveness": [],
        "minutes": 20,
    },
}


def load(recipe: str | None = None) -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if recipe is None or row.get("recipe") == recipe:
            out.append(row)
    return out


def flat_numbers(obj, prefix: str = "") -> dict[str, float]:
    """Every number in the result, flattened, so a recipe with no declared metrics is still
    comparable run to run. Declared metrics get reported; the rest are kept for later."""
    out: dict[str, float] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flat_numbers(v, f"{prefix}{k}."))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out[prefix.rstrip(".")] = float(obj)
    return out


def compare(recipe: str, result: dict) -> list[str]:
    """Say what moved, and whether it moved further than this measurement's own noise."""
    spec = RECIPES[recipe]
    history = load(recipe)
    if not history:
        return ["first run of this recipe - nothing to compare against yet"]
    prev = history[-1]
    spread = float(result.get(spec["spread"]) or 0) if spec["spread"] else 0.0
    prev_spread = float(prev.get("raw", {}).get(spec["spread"]) or 0) if spec["spread"] else 0.0
    # Two runs each carry their own spread; the band that matters is the pair's, not one's.
    band = 2 * max(spread, prev_spread, 0.01)

    lines = []
    for key in spec["metrics"] or sorted(flat_numbers(result))[:6]:
        now = flat_numbers(result).get(key, result.get(key))
        was = prev.get("metrics", {}).get(key)
        if now is None or was is None:
            continue
        delta = float(now) - float(was)
        verdict = "MOVED" if abs(delta) > band else "noise"
        lines.append(f"  {key:22} {was:.3f} -> {float(now):.3f}  ({delta:+.3f}, {verdict})")
    lines.append(f"  band: +/-{band:.3f}  (2x the wider of the two runs' reported spread)")
    return lines


def cmd_run(name: str, timeout_minutes: int | None) -> int:
    spec = RECIPES[name]
    budget = (timeout_minutes or spec["minutes"] * 2) * 60
    print(f"recipe   {name}")
    print(f"why      {spec['why']}")
    print(f"argv     python {' '.join(spec['argv'])}")
    print(f"expect   about {spec['minutes']} minutes; killing at {budget // 60}\n")

    start = time.monotonic()
    try:
        p = subprocess.run(
            [PY, *spec["argv"]],
            cwd=ROOT,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=budget,
        )
    except subprocess.TimeoutExpired:
        sys.exit(f"REFUSED to record: {name} did not finish inside {budget // 60} minutes. "
                 "A partial measurement is not a measurement.")
    took = time.monotonic() - start
    if p.returncode != 0:
        print((p.stderr or "")[-1500:])
        sys.exit(f"REFUSED to record: {name} exited {p.returncode}. Record the pass as 'clean' "
                 "with a note naming the failure; do not invent numbers for it.")

    text = (p.stdout or "").strip()
    start_brace = text.find("{")
    try:
        result = json.loads(text[start_brace:])
    except (json.JSONDecodeError, ValueError):
        print(text[-1500:])
        sys.exit(f"REFUSED to record: {name} did not emit parseable JSON.")

    # Liveness before belief. The previous version of this check in CI compared post against
    # pre and reported "flagged rate unchanged" while the rewriter had not loaded at all.
    for field in spec["liveness"]:
        value = result.get(field)
        if not value:
            sys.exit(f"REFUSED to record: {field}={value!r} - these numbers describe nothing. "
                     "That is itself the finding: write it to the queue.")

    numbers = flat_numbers(result)
    metrics = {k: numbers.get(k, result.get(k)) for k in spec["metrics"]}
    row = {
        "recipe": name,
        "seconds": round(took, 1),
        "argv": spec["argv"],
        "metrics": {k: v for k, v in metrics.items() if v is not None},
        "raw": {k: v for k, v in result.items() if not isinstance(v, (list, dict))},
    }

    print("result:")
    for k, v in (row["metrics"] or dict(list(numbers.items())[:8])).items():
        print(f"  {k:22} {v}")
    print("\nagainst the last run of this recipe:")
    for line in compare(name, result):
        print(line)

    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    print(f"\nappended to {LEDGER.relative_to(ROOT)} ({len(load(name))} run(s) of {name})")
    print("If something MOVED, write it to .claude/human-queue.md with this output. Do not "
          "edit any document that quotes a number.")
    return 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list")
    r = sub.add_parser("run")
    r.add_argument("recipe", choices=sorted(RECIPES))
    r.add_argument("--timeout-minutes", type=int, default=None)
    s = sub.add_parser("show")
    s.add_argument("recipe", choices=sorted(RECIPES))
    a = ap.parse_args()

    if a.cmd == "run":
        return cmd_run(a.recipe, a.timeout_minutes)
    if a.cmd == "show":
        for row in load(a.recipe):
            print(f"{row['seconds']:>7.0f}s  {row['metrics']}")
        return 0
    for name, spec in RECIPES.items():
        runs = len(load(name))
        print(f"{name:20} ~{spec['minutes']:>3}min  {runs} run(s)   {spec['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
