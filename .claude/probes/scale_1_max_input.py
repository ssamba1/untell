"""scale_1_max_input.py — binary-search the largest doc untell_text can process at lite tier.

Each attempt runs in a FRESH subprocess (the .venv python) so an OOM or hang
kills only that attempt. env: PYTHONPATH= (Hermes venv shadows pydantic_core)
and UNTELL_LITE_NO_TORCH=1 (force stdlib lite path, no model downloads).

Usage: python scale_1_max_input.py
"""
import json
import os
import subprocess
import sys
import time

REPO = r"C:\Users\Admin\Humanize"
PY = os.path.join(REPO, ".venv", "Scripts", "python.exe")
CHILD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scale_1_max_input.py")
TIMEOUT = 150  # seconds per attempt (parent-side hard kill)
SIZES = [10_000, 100_000, 1_000_000]  # start points for binary search

# Varied prose-ish sentences so the doc is not one repeated pattern (which would
# be an adversarial worst case for difflib; we measure that separately in scale_5).
_TEMPLATES = [
    "The experiment measured variance across three conditions, and the results confirmed the hypothesis.",
    "Researchers observed a modest but consistent effect in the second cohort of participants.",
    "Further analysis revealed that the control group differed significantly from the treatment group.",
    "These findings suggest that the mechanism operates through a cascade of intermediate signals.",
    "A follow-up study replicated the outcome using an independent sample and identical instrumentation.",
    "The authors note that limitations in the sampling frame may constrain the generalizability of the results.",
    "Discussion of the implications centered on practical applications for clinical settings.",
    "Nevertheless, the magnitude of the observed effect warrants cautious interpretation.",
]


def make_doc(n_chars: int) -> str:
    parts, total = [], 0
    i = 0
    while total < n_chars:
        s = _TEMPLATES[i % len(_TEMPLATES)] + " "
        parts.append(s)
        total += len(s)
        i += 1
    return "".join(parts)[:n_chars]


def run_attempt(n_chars: int) -> dict:
    env = {**os.environ, "PYTHONPATH": "", "UNTELL_LITE_NO_TORCH": "1"}
    t0 = time.time()
    try:
        p = subprocess.run(
            [PY, CHILD, str(n_chars)],
            capture_output=True, text=True, timeout=TIMEOUT, env=env, cwd=REPO,
        )
        wall = time.time() - t0
        if p.returncode != 0:
            return {"size": n_chars, "ok": False, "wall": round(wall, 2),
                    "reason": f"exit {p.returncode}", "stderr": p.stderr[-300:]}
        try:
            data = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            return {"size": n_chars, "ok": False, "wall": round(wall, 2),
                    "reason": "bad child output", "stderr": p.stderr[-300:]}
        data["wall"] = round(wall, 2)
        data["ok"] = True
        return data
    except subprocess.TimeoutExpired:
        return {"size": n_chars, "ok": False, "wall": round(time.time() - t0, 2),
                "reason": f"TIMEOUT >{TIMEOUT}s"}


def main():
    # coarse pass: establish upper/lower bounds at 10k / 100k / 1M
    bounds = {}  # size -> ok?
    for s in SIZES:
        r = run_attempt(s)
        bounds[s] = r["ok"]
        print(f"[coarse] {s:>9,} chars -> {'OK' if r['ok'] else 'FAIL'}  wall={r['wall']}s  "
              f"reason={r.get('reason', '')}", flush=True)
        if not r["ok"]:
            print("   child stderr tail:", r.get("stderr", "")[-200:].replace("\n", " | "), flush=True)

    ok_sizes = [s for s in SIZES if bounds[s]]
    fail_sizes = [s for s in SIZES if not bounds[s]]
    if not ok_sizes or not fail_sizes:
        print(json.dumps({"max_ok": max(ok_sizes) if ok_sizes else 0,
                          "bounds": bounds, "note": "no crossing found in coarse pass"}))
        return

    lo = max(ok_sizes)          # known OK
    hi = min(fail_sizes)        # known FAIL
    # bisect up to 4 refinement steps
    for _ in range(4):
        mid = (lo + hi) // 2
        r = run_attempt(mid)
        print(f"[bisect] {mid:>9,} chars -> {'OK' if r['ok'] else 'FAIL'}  wall={r['wall']}s  "
              f"reason={r.get('reason', '')}", flush=True)
        if r["ok"]:
            lo = mid
        else:
            hi = mid
        if hi - lo < 5000:
            break

    print(json.dumps({
        "max_workable_chars": lo,
        "first_fail_chars": hi,
        "bounds": {str(k): v for k, v in bounds.items()},
        "note": "score_text truncates at 50k chars; untell_text rewrites the WHOLE doc "
                "(this ceiling is the rewrite+gate path, max_iters=1, best_of=1)",
    }))


if __name__ == "__main__":
    if len(sys.argv) == 2:  # child mode
        n = int(sys.argv[1])
        env = {**os.environ, "PYTHONPATH": "", "UNTELL_LITE_NO_TORCH": "1"}
        os.environ.update(env)
        from untell.scripts.run import untell_text

        doc = make_doc(n)
        t0 = time.time()
        try:
            res = untell_text(doc, tier="lite", max_iters=1, best_of=1, seed=42)
            dt = time.time() - t0
            out = {"size": n, "elapsed": round(dt, 3),
                   "final_len": len(res.get("final", "")), "iterations": res.get("iterations"),
                   "flagged": res.get("flagged"), "tier": res.get("tier"),
                   "similarity": res.get("similarity")}
        except MemoryError:
            out = {"size": n, "elapsed": round(time.time() - t0, 3), "error": "MemoryError"}
        except Exception as exc:
            out = {"size": n, "elapsed": round(time.time() - t0, 3), "error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(out), flush=True)
    else:
        main()
