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
    "lite-raid": {
        "why": "same settings, different corpus. Nine results in this project's history "
               "generalised from one corpus before anyone varied it",
        "argv": ["-m", "eval.ceiling", "--dataset", "raid", "--n", "10", "--rewriter",
                 "composite", "--tier", "lite", "--repeats", "3", "--json"],
        "metrics": ["pre_flagged_rate", "post_flagged_rate", "pre_mean_max", "post_mean_max"],
        "spread": "post_mean_max_stdev",
        "liveness": ["rewriter_available", "rewrote", "n"],
        "minutes": 25,
    },
    "lite-mage": {
        "why": "a third corpus, so a claim can be checked against three rather than argued from one",
        "argv": ["-m", "eval.ceiling", "--dataset", "mage", "--n", "10", "--rewriter",
                 "composite", "--tier", "lite", "--repeats", "3", "--json"],
        "metrics": ["pre_flagged_rate", "post_flagged_rate", "pre_mean_max", "post_mean_max"],
        "spread": "post_mean_max_stdev",
        "liveness": ["rewriter_available", "rewrote", "n"],
        "minutes": 25,
    },
    "lite-hc3-surgical": {
        "why": "rewriter sweep: the cheapest backend, as the floor to measure the others against",
        "argv": ["-m", "eval.ceiling", "--dataset", "hc3", "--n", "10", "--rewriter", "surgical",
                 "--tier", "lite", "--repeats", "3", "--json"],
        "metrics": ["pre_flagged_rate", "post_flagged_rate", "pre_mean_max", "post_mean_max"],
        "spread": "post_mean_max_stdev",
        "liveness": ["rewriter_available", "rewrote", "n"],
        "minutes": 20,
    },
    "lite-hc3-structural": {
        "why": "rewriter sweep: the one whose clause-joining once tripped the contradiction veto "
               "on every candidate it produced",
        "argv": ["-m", "eval.ceiling", "--dataset", "hc3", "--n", "10", "--rewriter", "structural",
                 "--tier", "lite", "--repeats", "3", "--json"],
        "metrics": ["pre_flagged_rate", "post_flagged_rate", "pre_mean_max", "post_mean_max"],
        "spread": "post_mean_max_stdev",
        "liveness": ["rewriter_available", "rewrote", "n"],
        "minutes": 20,
    },
    "lite-hc3-targeted": {
        "why": "rewriter sweep: detector-directed rewriting, the one whose leverage the tell "
               "catalogue predicts but has never been measured against composite",
        "argv": ["-m", "eval.ceiling", "--dataset", "hc3", "--n", "10", "--rewriter", "targeted",
                 "--tier", "lite", "--repeats", "3", "--json"],
        "metrics": ["pre_flagged_rate", "post_flagged_rate", "pre_mean_max", "post_mean_max"],
        "spread": "post_mean_max_stdev",
        "liveness": ["rewriter_available", "rewrote", "n"],
        "minutes": 25,
    },
    "lite-hc3-ensemble": {
        "why": "rewriter sweep: all free backends, selection included - the lane where a "
               "saturating detector once made selection a no-op",
        "argv": ["-m", "eval.ceiling", "--dataset", "hc3", "--n", "10", "--rewriter", "ensemble",
                 "--tier", "lite", "--repeats", "3", "--json"],
        "metrics": ["pre_flagged_rate", "post_flagged_rate", "pre_mean_max", "post_mean_max"],
        "spread": "post_mean_max_stdev",
        "liveness": ["rewriter_available", "rewrote", "n"],
        # MEASURED 2026-08-13/14: every backend the ensemble runs has now been timed on this exact
        # recipe shape (n=10, repeats=3, lite) — composite 841s, targeted 810s, structural 357s,
        # surgical 204s — and ensemble runs ALL of them plus selection, so the old 30-minute
        # estimate was ~3x short. The program run killed it at 90 minutes (3x budget) with the
        # measurement unfinished. A second run was killed at 120 minutes (2x the 60-minute
        # estimate) while a sibling fleet run of the same recipe shared the machine. A THIRD run
        # (2026-08-14, solo start, ~1h of light sibling holdout contention) was killed at 180
        # minutes (2x the 90-minute estimate) still unfinished — 3 repeats of 4 backends plus
        # selection genuinely exceeds 3 hours. The recipe needs n=6 or repeats=2 to be runnable
        # in a session; as defined it is a multi-hour measurement best left to the fleet runner
        # with a 240m budget. 150 is the estimate; the program runner's 3x budget covers it.
        "minutes": 150,
    },
    "compare-hc3": {
        "why": "this pipeline against the other humanizers on the same text - the only "
               "measurement that says whether the wall is ours or everyone's",
        "argv": ["-m", "eval.compare_humanizers", "--dataset", "hc3", "--n", "10",
                 "--tier", "lite", "--json"],
        "metrics": [],
        "spread": "",
        "liveness": [],
        # MEASURED 2026-08-13: killed at the 60-minute budget (2x the 30-minute estimate) with
        # the run unfinished. Pass 14's "timed out after 10 min" was an agent-imposed cap, not
        # the recipe's budget — the real recipe runs 5 techniques x 10 texts, two of which are
        # untell_text loops (max_iters=5, best_of=3) plus a marian back-translation, each draw
        # a full detector pass. 60 is the floor; the sibling run in the same session also
        # exceeded 30 minutes before the machine was free.
        "minutes": 60,
    },
    "claims-audit": {
        "why": "re-checks every documented claim that CAN be re-checked, and reports how many "
               "cannot - the drift lane, mechanised",
        "argv": ["-m", "untell.scripts.audit", "--json"],
        "metrics": [],
        "spread": "",
        "liveness": [],
        # MEASURED 2026-08-13 (twice): the full audit completes in ~7 minutes (423s and 443s),
        # including the internal pytest --collect-only. Pass 8's ">30 min" was measured while
        # the loop's own parallel pytest suite was fighting the audit's subprocess for the
        # machine; on an idle machine it is a 7-minute run. 15 is a comfortable ceiling.
        "minutes": 15,
    },
    "length-short": {
        "why": "openings only. Detectors used to read the first few hundred words and nothing "
               "else, so this is the length every old result was really about",
        "argv": ["-m", "eval.ceiling", "--file", ".claude/corpora/hc3-short.txt",
                 "--rewriter", "composite", "--tier", "lite", "--repeats", "3", "--json"],
        "needs": [".claude/corpora/hc3-short.txt"],
        "metrics": ["pre_flagged_rate", "post_flagged_rate", "pre_mean_max", "post_mean_max"],
        "spread": "post_mean_max_stdev",
        "liveness": ["rewriter_available", "rewrote", "n"],
        "minutes": 20,
    },
    "length-long": {
        "why": "past where detectors used to stop reading. If windowed scoring holds, this "
               "should not be systematically easier than the short bucket - and nothing has "
               "re-checked that by length since the fix",
        "argv": ["-m", "eval.ceiling", "--file", ".claude/corpora/hc3-long.txt",
                 "--rewriter", "composite", "--tier", "lite", "--repeats", "3", "--json"],
        "needs": [".claude/corpora/hc3-long.txt"],
        "metrics": ["pre_flagged_rate", "post_flagged_rate", "pre_mean_max", "post_mean_max"],
        "spread": "post_mean_max_stdev",
        "liveness": ["rewriter_available", "rewrote", "n"],
        "minutes": 25,
    },
    "human-false-positives": {
        "why": "HUMAN text only, scored at the shipped threshold. An audit once reported AUROC "
               "0.999 while that threshold flagged 95% of human writing - separation is not "
               "calibration, and only this recipe can see the difference",
        "argv": ["-m", "eval.ceiling", "--file", ".claude/corpora/hc3-human.txt",
                 "--rewriter", "composite", "--tier", "lite", "--repeats", "3", "--json"],
        "needs": [".claude/corpora/hc3-human.txt"],
        "metrics": ["pre_flagged_rate", "pre_mean_max"],
        "spread": "post_mean_max_stdev",
        "liveness": ["n"],
        "minutes": 25,
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
        # MEASURED 2026-08-13: pure tell-catalogue scoring, no model loading — 40 pairs (80
        # documents) completed in 6.5s. The 20-minute estimate was a guess carried over from the
        # model-backed recipes; this one is a regex pass and finishes before the first torch import.
        "minutes": 1,
    },
}


# A family is a set of recipes that differ in exactly one thing, so the comparison between
# them means something. Sweeping one is the only way to answer "which rewriter is the wall"
# or "does this number survive a change of corpus" — questions no single run can address.
FAMILIES: dict[str, list[str]] = {
    "rewriters": ["lite-hc3", "lite-hc3-surgical", "lite-hc3-structural",
                  "lite-hc3-targeted", "lite-hc3-ensemble"],
    "corpora": ["lite-hc3", "lite-raid", "lite-mage"],
    "tiers": ["lite-hc3", "full-hc3-composite"],
    "lengths": ["length-short", "lite-hc3", "length-long"],
    "full-rewriters": ["full-hc3-composite", "full-hc3-neural", "full-hc3-max"],
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


INSTRUMENTS = ROOT / ".claude" / "instruments.json"

# Cheapest and most diagnostic first, so a program that is interrupted has still answered
# something. The full-tier recipes are excluded by default: each is one to two hours, and a
# chain of them would occupy the machine for a working day without being asked.
PROGRAM_ORDER = [
    "lite-hc3", "lite-hc3-surgical", "lite-hc3-structural", "lite-hc3-targeted",
    "lite-hc3-ensemble", "length-short", "length-long", "human-false-positives",
    "lite-raid", "lite-mage", "claims-audit", "detector-audit", "tells-auroc", "compare-hc3",
]
PROGRAM_FULL = ["full-hc3-composite", "full-hc3-max", "full-hc3-neural"]


def cmd_program(include_full: bool, budget_multiplier: float) -> int:
    """Run every unmeasured recipe in order, and keep going when one fails.

    Measuring one recipe per pass is right for the loop; it is wrong for a machine that is
    free for the next several hours. This is the same measurements in the same order, resumable
    by construction — a recipe with a result is skipped, so an interrupted program continues
    where it stopped rather than starting over.
    """
    queue = [n for n in PROGRAM_ORDER + (PROGRAM_FULL if include_full else []) if not load(n)]
    if not queue:
        print("every recipe in the program already has a result. `report` shows them.")
        return 0

    total = sum(RECIPES[n]["minutes"] for n in queue)
    print(f"{len(queue)} recipe(s) to run, roughly {total} minutes if the estimates hold:")
    for n in queue:
        print(f"  {n:24} ~{RECIPES[n]['minutes']:>3}min")
    print()

    done, failed = [], []
    for i, name in enumerate(queue, start=1):
        print(f"\n{'=' * 70}\n[{i}/{len(queue)}] {name}\n{'=' * 70}")
        budget = int(RECIPES[name]["minutes"] * budget_multiplier)
        try:
            cmd_run(name, budget)
            done.append(name)
        except SystemExit as exc:
            # A refusal is information, not a reason to stop: the next recipe measures
            # something else. Two in a row means the machine or the environment is the
            # problem, and continuing would just produce more of the same failure.
            print(f"[{i}/{len(queue)}] {name} did not record: {exc}")
            failed.append(name)
            if len(failed) >= 2 and failed[-2:] == [queue[i - 2], name]:
                print("\nTwo consecutive failures - stopping. Fix the cause before burning "
                      "hours on the rest.")
                break

    print(f"\n{'=' * 70}\nprogram finished: {len(done)} recorded, {len(failed)} refused")
    for n in done:
        print(f"  recorded  {n}  ({load(n)[-1]['seconds']:.0f}s)")
    for n in failed:
        print(f"  REFUSED   {n}")
    print("\nCompare families with: research.py table rewriters | lengths | corpora")
    return 0


def cmd_calibrate(name: str) -> int:
    """Run a recipe twice unchanged and find out whether it can detect anything.

    A measurement that returns the same numbers whatever you do is a liveness check, not an
    instrument. That distinction cost a false finding here: a loosened similarity gate came
    back identical to four decimals on a seeded three-paragraph corpus, and every knob would
    have been recorded as "no effect" through it. Ask the question of the instrument before
    asking it of the subject.
    """
    spec = RECIPES[name]
    print(f"calibrating {name} - two identical runs, ~{spec['minutes'] * 2} minutes total\n")
    all_before = load(name)  # FULL history, for the cross-run spread check
    before = len(all_before)
    for i in (1, 2):
        print(f"--- run {i} of 2 ---")
        cmd_run(name, None)
    runs = load(name)[before:]
    if len(runs) < 2:
        sys.exit("REFUSED: fewer than two runs completed; nothing to compare.")

    a, b = runs[-2]["metrics"], runs[-1]["metrics"]
    moved = {k: round(float(b[k]) - float(a[k]), 6)
             for k in a if k in b and a[k] is not None and b[k] is not None}
    print("\nrun-to-run, nothing changed in between:")
    for k, v in moved.items():
        print(f"  {k:22} {v:+.6f}")

    # A determinism claim cannot come from a 2-run window: two consecutive runs can both
    # land in the same stable cluster while the process genuinely moves between clusters
    # (measured on lite-hc3: runs 0.5871/0.5887/0.5887/0.5625/0.5887 — run 4 moved 0.0262
    # below the cluster, invisible to a last-two comparison). Compare against the FULL
    # run history instead: deterministic means every metric's min-max spread across all
    # runs is zero, not just the latest pair.
    history = load(name)
    if len(history) >= 2:
        keys = sorted({k for r in history for k in r.get("metrics", {})
                       if r["metrics"][k] is not None})
        spread = {k: max(r["metrics"][k] for r in history) -
                  min(r["metrics"][k] for r in history) for k in keys}
        print("\nfull-history min-max spread (all runs):")
        for k, v in spread.items():
            print(f"  {k:22} {v:.6f}")
        deterministic = all(v == 0.0 for v in spread.values())
    else:
        deterministic = all(v == 0 for v in moved.values())

    record = json.loads(INSTRUMENTS.read_text(encoding="utf-8")) if INSTRUMENTS.exists() else {}
    record[name] = {"deterministic": deterministic, "run_to_run": moved,
                    "reported_spread": runs[-1]["raw"].get(spec["spread"])}
    INSTRUMENTS.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    if deterministic:
        print(f"\n{name} is DETERMINISTIC: identical output with nothing changed. Good for "
              "liveness, useless for comparison - a real effect and no effect look the same "
              "through it. Recorded, and the experiment lane will now refuse it.")
    else:
        print(f"\n{name} moves on its own. Any claimed effect must clear that, not just the "
              "spread reported within a single run.")
    return 0


def cmd_report() -> int:
    """Everything the loop knows, in one screen, so 24/7 work stays readable."""
    def count(path: Path) -> int:
        """Data rows in a markdown table. The header and the separator are not findings, and
        a digest that counts them reports one more of everything than exists."""
        if not path.exists():
            return 0
        rows = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if line.strip().startswith("|") and len(cells) > 2 and "---" not in line:
                first = cells[0]
                rows += 1 if (first.isdigit() or "/" in first or "." in first) else 0
        return rows

    base = ROOT / ".claude"
    print("MEASUREMENTS")
    for name in RECIPES:
        history = load(name)
        if not history:
            continue
        m = history[-1]["metrics"]
        cells = "  ".join(f"{k.split('_')[0]}/{k.split('_')[-1]}={v}" for k, v in m.items())
        print(f"  {name:22} {len(history)} run(s)  {cells}")
    unmeasured = [n for n in RECIPES if not load(n)]
    if unmeasured:
        print(f"  not measured yet ({len(unmeasured)}): {', '.join(unmeasured)}")

    exp = base / "experiments.jsonl"
    rows = [json.loads(x) for x in exp.read_text(encoding="utf-8").splitlines()
            if x.strip()] if exp.exists() else []
    print(f"\nEXPERIMENTS  {len(rows)} run(s)")
    for r in rows:
        real = [k for k, v in r["deltas"].items() if abs(v) > r["band"]]
        print(f"  {r['knob']:24} {r['recipe']:14} "
              f"{'MOVED: ' + ', '.join(real) if real else 'nothing beyond noise'}")

    print(f"\nSURVIVORS    {count(base / 'survivors.md')} unpinned line(s)")
    print(f"PASSES       {count(base / 'audit-log.md')} recorded")
    queued = 0
    if (base / "human-queue.md").exists():
        # The file's own format example is a `## ` heading too; counting it would report a
        # backlog of one on a queue that is empty.
        queued = sum(1 for line in (base / "human-queue.md").read_text(encoding="utf-8").splitlines()
                     if line.startswith("## ") and "<date>" not in line)
    print(f"FOR A HUMAN  {queued} queue entr(y/ies)")
    return 0


def cmd_run(name: str, timeout_minutes: int | None) -> int:
    spec = RECIPES[name]
    budget = (timeout_minutes or spec["minutes"] * 2) * 60
    print(f"recipe   {name}")
    print(f"why      {spec['why']}")
    print(f"argv     python {' '.join(spec['argv'])}")
    print(f"expect   about {spec['minutes']} minutes; killing at {budget // 60}\n")

    for needed in spec.get("needs", []):
        if not (ROOT / needed).exists():
            bucket = Path(needed).stem.split("-")[-1]
            sys.exit(
                f"REFUSED: {name} measures {needed}, which does not exist yet. Build it:\n"
                f"  python .claude/corpus.py build --dataset hc3 --bucket {bucket} --n 10\n"
                "A recipe that silently falls back to another corpus answers a different "
                "question than the one on its label."
            )

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
    f = sub.add_parser("sweep", help="run every recipe in a family that has no result yet")
    f.add_argument("family", choices=sorted(FAMILIES))
    c = sub.add_parser("table", help="latest result per recipe in a family, side by side")
    c.add_argument("family", choices=sorted(FAMILIES))
    k = sub.add_parser("calibrate", help="two identical runs: can this recipe detect anything?")
    k.add_argument("recipe", choices=sorted(RECIPES))
    sub.add_parser("report", help="every ledger, one screen")
    g = sub.add_parser("program", help="run every unmeasured recipe, in order, resumably")
    g.add_argument("--full", action="store_true", help="include the 1-2 hour full-tier recipes")
    g.add_argument("--budget", type=float, default=3.0,
                   help="multiple of a recipe's estimate before it is killed. The estimates "
                        "were guesses until the first real runs; 3x leaves room for that.")
    a = ap.parse_args()

    if a.cmd == "run":
        return cmd_run(a.recipe, a.timeout_minutes)
    if a.cmd == "calibrate":
        return cmd_calibrate(a.recipe)
    if a.cmd == "report":
        return cmd_report()
    if a.cmd == "program":
        return cmd_program(a.full, a.budget)
    if a.cmd == "sweep":
        # One recipe per pass. A sweep that runs five measurements inside one pass outlives
        # its hour and records nothing; run the next missing one and stop.
        for name in FAMILIES[a.family]:
            if not load(name):
                print(f"family {a.family}: {name} has no result yet\n")
                return cmd_run(name, None)
        print(f"family {a.family} is complete - every recipe has at least one result.")
        print("Compare them with: research.py table " + a.family)
        return 0
    if a.cmd == "table":
        keys = ["pre_flagged_rate", "post_flagged_rate", "pre_mean_max", "post_mean_max"]
        print(f"{'recipe':24} " + " ".join(f"{k[:12]:>12}" for k in keys) + "   runs")
        for name in FAMILIES[a.family]:
            history = load(name)
            if not history:
                print(f"{name:24} {'not measured yet':>54}")
                continue
            m = history[-1]["metrics"]
            cells = " ".join(f"{(m.get(k) if m.get(k) is not None else float('nan')):>12.3f}"
                             for k in keys)
            print(f"{name:24} {cells}   {len(history)}")
        print("\nOne run each is a sketch, not a finding. A difference is only real if it "
              "clears both runs' spread.")
        return 0
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
