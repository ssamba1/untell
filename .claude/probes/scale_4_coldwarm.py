"""scale_4_coldwarm.py — detector cold-start vs warm latency (fresh subprocess).

Measures, in a fresh interpreter with PYTHONPATH= UNTELL_LITE_NO_TORCH=1:
  import-only time, first score_text (includes all_detectors() roster construction),
  warm score_text calls, and a cold untell_text first call.

Usage: python scale_4_coldwarm.py [child|parent]
"""
import json
import os
import subprocess
import sys
import time

REPO = r"C:\Users\Admin\Humanize"
PY = os.path.join(REPO, ".venv", "Scripts", "python.exe")
THIS = os.path.abspath(__file__)


def child():
    os.environ["PYTHONPATH"] = ""
    os.environ["UNTELL_LITE_NO_TORCH"] = "1"
    doc = "The experiment measured variance across three conditions. " * 10

    t0 = time.perf_counter()
    import untell.scripts.score as sc
    t_import = time.perf_counter() - t0

    t1 = time.perf_counter()
    r1 = sc.score_text(doc, tier="lite")
    t_first = time.perf_counter() - t1

    t2 = time.perf_counter()
    sc.score_text(doc, tier="lite")
    t_warm2 = time.perf_counter() - t2

    t3 = time.perf_counter()
    sc.score_text(doc, tier="lite")
    t_warm3 = time.perf_counter() - t3

    t4 = time.perf_counter()
    from untell.scripts.run import untell_text
    t_import_run = time.perf_counter() - t4

    t5 = time.perf_counter()
    res = untell_text(doc, tier="lite", max_iters=1, best_of=1, seed=7)
    t_untell_cold = time.perf_counter() - t5

    print(json.dumps({
        "import_score_module_s": round(t_import, 3),
        "first_score_text_s": round(t_first, 3),
        "warm_score_2nd_s": round(t_warm2, 4),
        "warm_score_3rd_s": round(t_warm3, 4),
        "import_run_module_s": round(t_import_run, 3),
        "first_untell_text_s": round(t_untell_cold, 3),
        "untell_tier": res.get("tier"),
    }), flush=True)


def parent():
    env = {**os.environ, "PYTHONPATH": "", "UNTELL_LITE_NO_TORCH": "1"}
    # 3 fresh processes -> report median
    rows = []
    for i in range(3):
        t0 = time.time()
        p = subprocess.run([PY, THIS, "child"], capture_output=True, text=True,
                           timeout=180, env=env, cwd=REPO)
        print(f"[run {i+1}] wall={time.time()-t0:.1f}s rc={p.returncode}", flush=True)
        if p.returncode == 0:
            rows.append(json.loads(p.stdout.strip().splitlines()[-1]))
        else:
            print("stderr:", p.stderr[-400:])
    if rows:
        med = rows[len(rows) // 2]
        print(json.dumps({"median_of_3_fresh_processes": med, "all": rows}))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "child":
        child()
    else:
        parent()
