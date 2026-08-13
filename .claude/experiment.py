"""Try a change to a tuning knob, measure both sides, and put it back.

Every knob that could move the flagged rate is RED: a threshold or bar or weight changed by
an unattended loop makes every number anyone has quoted unciteable. But refusing to touch
them also means never learning what they do, and the free-evasion wall is a rewriter-and-
parameter problem, not a test-coverage one.

The way out is to measure without keeping. This applies a candidate value in the working
tree, measures before and after at the same settings with repeats, restores the file, and
writes the pair to a ledger. Nothing RED is ever staged, so the guard never has to make an
exception and there is no branch on which a forbidden change quietly survives.

    python .claude/experiment.py list
    python .claude/experiment.py run quality-bar-0.70 --recipe lite-hc3

What comes out is evidence for a human decision, not a decision. A delta inside the noise
band is reported as noise, and "no effect" is a real result worth the ledger row.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research  # noqa: E402  - sibling script, not a package

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / ".claude" / "experiments.jsonl"

# Real constants, each verified present at the line its pattern matches. Values are chosen to
# probe a direction, not to be adopted: the point is to learn the slope, and a knob with no
# slope is as informative as one with a steep one.
KNOBS: dict[str, dict] = {
    "quality-bar-0.70": {
        "file": "untell/scripts/quality.py",
        "find": r"^DEFAULT_BAR = 0\.76",
        "to": "DEFAULT_BAR = 0.70",
        "asks": "does a looser semantic-similarity gate let better candidates through, or "
                "does it just admit drift?",
    },
    "quality-bar-0.82": {
        "file": "untell/scripts/quality.py",
        "find": r"^DEFAULT_BAR = 0\.76",
        "to": "DEFAULT_BAR = 0.82",
        "asks": "does a stricter gate cost evasion, and how much?",
    },
    "token-bar-0.40": {
        "file": "untell/scripts/quality.py",
        "find": r"^TOKEN_BAR = 0\.50",
        "to": "TOKEN_BAR = 0.40",
        "asks": "faithful paraphrases reword heavily and score low here - is 0.50 rejecting "
                "the rewrites that actually work?",
    },
    "contradiction-bar-0.35": {
        "file": "untell/scripts/entailment.py",
        "find": r"^DEFAULT_CONTRADICTION_BAR = 0\.5",
        "to": "DEFAULT_CONTRADICTION_BAR = 0.35",
        "asks": "a stricter contradiction veto: does it protect meaning without vetoing "
                "everything the structural rewriter emits?",
    },
    "relaxed-sim-0.20": {
        "file": "untell/scripts/entailment.py",
        "find": r"^RELAXED_SIM_BAR = 0\.30",
        "to": "RELAXED_SIM_BAR = 0.20",
        "asks": "how much of the pipeline's output is gated by the relaxed path?",
    },
    "ppl-weight-0.40": {
        "file": "untell/detectors/perplexity_burstiness.py",
        "find": r"^_PPL_WEIGHT = 0\.55",
        "to": "_PPL_WEIGHT = 0.40",
        "asks": "shifting weight from perplexity toward burstiness - does the proxy detector "
                "track the real ones better or worse?",
    },
    "threshold-0.40": {
        "file": "untell/scripts/score.py",
        "find": r"^DEFAULT_THRESHOLD = 0\.30",
        "to": "DEFAULT_THRESHOLD = 0.40",
        "asks": "the shipped threshold itself: what does the flagged rate do on both the AI "
                "and the human side? Never adopt from one run - this one moves every claim.",
    },
}


# A knob question needs an instrument that can move. `lite-builtin` is three hand-written
# paragraphs and the harness seeds them, so it returns the same four numbers to four decimals
# whatever you change — including a loosened similarity gate, which is how this list got
# written. An unattended loop pointed at it would record every knob as "no effect" and be
# wrong seven times.
KNOB_UNSAFE = {
    "lite-builtin": "3 seeded paragraphs: identical to 4dp run to run, so a knob's effect and "
                    "no effect look the same",
}


def sh(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, encoding="utf-8",
        errors="replace", check=False,
    )


def measure(recipe: str, label: str) -> dict:
    spec = research.RECIPES[recipe]
    print(f"\n--- measuring {label} ({recipe}, ~{spec['minutes']}min) ---")
    p = subprocess.run(
        [sys.executable, *spec["argv"]],
        cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace",
        timeout=spec["minutes"] * 120,
    )
    if p.returncode != 0:
        raise RuntimeError(f"{label} measurement exited {p.returncode}: {(p.stderr or '')[-500:]}")
    text = (p.stdout or "").strip()
    result = json.loads(text[text.find("{"):])
    for field in spec["liveness"]:
        if not result.get(field):
            raise RuntimeError(f"{label}: {field} is falsy - the run describes nothing")
    for k in spec["metrics"]:
        print(f"  {k:22} {result.get(k)}")
    return result


def cmd_run(knob: str, recipe: str) -> int:
    if recipe in KNOB_UNSAFE:
        sys.exit(f"REFUSED: --recipe {recipe} cannot answer a knob question - "
                 f"{KNOB_UNSAFE[recipe]}. Use lite-hc3 or a full-tier recipe.")
    spec = KNOBS[knob]
    path = (ROOT / spec["file"]).resolve()
    if sh("diff", "--quiet", "--", str(path)).returncode:
        sys.exit(f"REFUSED: {spec['file']} has uncommitted changes. This script restores the "
                 "file from memory, and it will not gamble with someone else's edit.")

    original = path.read_text(encoding="utf-8")
    if not re.search(spec["find"], original, re.M):
        sys.exit(f"REFUSED: {spec['file']} no longer contains /{spec['find']}/. The knob moved "
                 "or was renamed - fix this entry before trusting any row that used it.")

    print(f"knob     {knob}")
    print(f"asks     {spec['asks']}")
    print(f"change   {spec['file']}: {spec['to']}")
    print(f"recipe   {recipe}")

    try:
        before = measure(recipe, "before")
        path.write_text(re.sub(spec["find"], spec["to"], original, count=1, flags=re.M),
                        encoding="utf-8")
        after = measure(recipe, "after")
    finally:
        # Unconditional: an exception mid-measurement must not leave a RED constant changed on
        # disk where the next pass would commit it without knowing.
        path.write_text(original, encoding="utf-8")
        print("\nrestored", spec["file"])

    metrics = research.RECIPES[recipe]["metrics"]
    spread_key = research.RECIPES[recipe]["spread"]
    band = 2 * max(float(before.get(spread_key) or 0), float(after.get(spread_key) or 0), 0.01)
    deltas = {}
    print("\nresult:")
    for k in metrics:
        b, a = before.get(k), after.get(k)
        if b is None or a is None:
            continue
        d = float(a) - float(b)
        deltas[k] = d
        print(f"  {k:22} {float(b):.3f} -> {float(a):.3f}  ({d:+.3f}, "
              f"{'MOVED' if abs(d) > band else 'noise'})")
    print(f"  band: +/-{band:.3f}")

    row = {"knob": knob, "recipe": recipe, "change": spec["to"], "asks": spec["asks"],
           "before": {k: before.get(k) for k in metrics},
           "after": {k: after.get(k) for k in metrics},
           "deltas": deltas, "band": band}
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    print(f"\nappended to {LEDGER.relative_to(ROOT)}")

    if any(abs(d) > band for d in deltas.values()):
        print("\nSomething moved further than the noise. Write it to .claude/human-queue.md "
              "with this output. Do NOT adopt the value - one experiment at one corpus is a "
              "reason to look, not a reason to ship.")
    else:
        print("\nNothing moved beyond noise. That is a real result: this knob does not do what "
              "it looks like it does at this corpus and tier. Record it and move on.")
    return 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list")
    r = sub.add_parser("run")
    r.add_argument("knob", choices=sorted(KNOBS))
    r.add_argument("--recipe", default="lite-hc3", choices=sorted(research.RECIPES))
    a = ap.parse_args()

    if a.cmd == "run":
        return cmd_run(a.knob, a.recipe)
    done = [json.loads(x)["knob"] for x in
            (LEDGER.read_text(encoding="utf-8").splitlines() if LEDGER.exists() else []) if x.strip()]
    for name, spec in KNOBS.items():
        print(f"{name:24} {done.count(name)} run(s)  {spec['file']}  ->  {spec['to']}")
        print(f"{'':24} {spec['asks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
