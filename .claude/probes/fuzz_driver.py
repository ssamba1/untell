"""fuzz_driver.py — orchestrator for the untell fuzz probe.

Builds randomized case corpora (fuzz_corpus.py), executes them in chunked
subprocesses (fuzz_worker.py) with wall-clock deadlines, isolates hangs by
binary search, runs one-shot CLI subprocess tests, and writes:
  - .claude/probes/fuzz_findings.json   (aggregated machine-readable findings)
  - .claude/probes/fuzz_repro_<surface>_<n>.py  (reproducer scripts)

Run (from repo root):
    PYTHONPATH= UNTELL_LITE_NO_TORCH=1 .venv/Scripts/python.exe \
        .claude/probes/fuzz_driver.py [--quick]

Surfaces (>=300 cases each unless noted):
    score    -> score_text (unicode+bytes+types+params)   730 cases
    loop     -> untell_text (default composite rewriter)  300 cases
    cli      -> 3 CLIs in-process main() fuzz             360 cases + 36 one-shot subprocesses
    preserve -> lock/restore round-trips + adversarial    400 cases
    tells    -> score_tells / looks_non_english           400 cases

Classification:
    DEFECT  real defect  — unhandled exception/hang on valid-ish input
    GAP     defense gap  — exception on malformed input that should be a
                           clean error (exit 2 / {"error": ...})
    OK      by-design    — documented or correct behaviour
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PY = os.path.join(REPO, ".venv", "Scripts", "python.exe")
WORKER = os.path.join(HERE, "fuzz_worker.py")

ENV = dict(os.environ)
ENV["PYTHONPATH"] = ""           # Hermes venv shadows pydantic_core
ENV["UNTELL_LITE_NO_TORCH"] = "1"
ENV["PYTHONUTF8"] = "1"

WARMUP = 16.0                    # first score_text call pays spacy+torch import ~10-15s


def log(msg: str) -> None:
    print(f"[driver] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Chunked engine fuzz
# ---------------------------------------------------------------------------

def run_chunk(surface: str, cases: list[dict], case_timeout: float,
              budget_per_case: float, tag: str) -> list[dict]:
    """Run cases in one worker subprocess. Returns result lines (in order)."""
    cases_path = os.path.join(HERE, f"_fuzz_{tag}.jsonl")
    out_path = os.path.join(HERE, f"_fuzz_{tag}.out.jsonl")
    with open(cases_path, "w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=True) + "\n")
    if os.path.exists(out_path):
        os.remove(out_path)

    deadline = WARMUP + len(cases) * budget_per_case * 2.5 + 30
    t0 = time.time()
    try:
        proc = subprocess.run(
            [PY, WORKER, surface, cases_path, out_path, str(case_timeout)],
            env=ENV, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=deadline, cwd=REPO,
        )
        finished = True
    except subprocess.TimeoutExpired:
        finished = False
        log(f"  CHUNK TIMEOUT after {deadline:.0f}s ({tag}) — killing, "
            f"binary-searching for hang")

    lines: list[dict] = []
    if os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # torn last line from a kill
    log(f"  chunk {tag}: {len(lines)}/{len(cases)} results, finished={finished}, "
        f"wall={time.time() - t0:.0f}s")
    return lines


def _deadline_for(n: int, budget: float) -> float:
    return WARMUP + n * budget * 2.5 + 30


def find_hang(surface: str, cases: list[dict], case_timeout: float,
              budget_per_case: float, tag: str) -> list[int]:
    """Binary-search a chunk whose full run exceeded its deadline. Returns the
    indexes of cases that hang (GIL stall / process-level hang)."""
    lo, hi = 0, len(cases)
    hang_idx: list[int] = []
    depth = 0
    while lo < hi and depth < 12:
        depth += 1
        mid = (lo + hi) // 2
        for half, (a, b) in (("L", (lo, mid)), ("R", (mid, hi))):
            if a >= b:
                continue
            slice_cases = cases[a:b]
            res = run_chunk(surface, slice_cases, case_timeout,
                            budget_per_case, f"{tag}_bin{depth}{half}")
            if len(res) < len(slice_cases) - 1:  # didn't finish all cases
                if len(slice_cases) == 1:
                    hang_idx.append(a)
                else:
                    # recurse into this half
                    lo, hi = a, b
                    break
        else:
            # both halves finished -> earlier timeout was cumulative slowness
            return hang_idx
    return hang_idx


def fuzz_surface(surface: str, cases: list[dict], case_timeout: float,
                 budget_per_case: float, chunk_size: int, tag: str) -> list[dict]:
    all_results: list[dict] = []
    for start in range(0, len(cases), chunk_size):
        chunk = cases[start:start + chunk_size]
        res = run_chunk(surface, chunk, case_timeout, budget_per_case,
                        f"{tag}_{start}")
        if len(res) < len(chunk):
            log(f"  chunk {tag}_{start} incomplete: {len(res)}/{len(chunk)} — "
                f"isolating hang/crash")
            hangs = find_hang(surface, chunk, case_timeout, budget_per_case,
                              f"{tag}_{start}")
            for idx in hangs:
                log(f"  HANG at case index {idx}: "
                    f"{json.dumps(chunk[idx], ensure_ascii=True)[:160]}")
                all_results.append({"i": idx, "status": "hang_isolated",
                                    "case": chunk[idx]})
            # also surface the crash suspect: first missing index
            done = {r["i"] for r in res}
            missing = sorted(i for i in range(len(chunk)) if i not in done)
            if missing and not hangs:
                suspect = missing[0]
                log(f"  CRASH SUSPECT at case index {suspect}: "
                    f"{json.dumps(chunk[suspect], ensure_ascii=True)[:160]}")
                # confirm in isolation
                iso = run_chunk(surface, [chunk[suspect]], case_timeout,
                                budget_per_case, f"{tag}_iso{suspect}")
                if len(iso) == 0:
                    log(f"  CONFIRMED CRASH on case index {suspect}")
                    all_results.append({"i": suspect, "status": "crash",
                                        "case": chunk[suspect]})
                else:
                    log(f"  case {suspect} did not crash in isolation "
                        f"(cumulative state?) — result: {iso[0].get('status')}")
                    all_results.append({"i": suspect, "status": "isolated_ok",
                                        "case": chunk[suspect]})
        all_results.extend(res)
    return all_results


# ---------------------------------------------------------------------------
# One-shot CLI subprocess tests
# ---------------------------------------------------------------------------

def cli_one_shots() -> list[dict]:
    """True subprocess CLI invocations with random args / stdin / timeouts."""
    findings: list[dict] = []
    module_for = {"untell": "untell.scripts.cli",
                  "score": "untell.scripts.score",
                  "loop": "untell.scripts.run"}

    base_cases = {
        "untell": [
            ([], "empty argv -> demo (slow, by design)"),
            (["--help"], "help"),
            (["--tier", "bogus", "hello world"], "bad tier flag"),
            (["score", "--tier", "lite", "this is a short text to score"],
             "subcommand dispatch -> score"),
            (["tells", "a short text with tells"], "subcommand dispatch -> tells"),
            (["\ud800\ud801"], "lone-surrogate argv"),
            (["--file", "C:\\definitely\\not\\here.txt"], "missing file"),
            (["--threshold", "abc", "text"], "bad threshold"),
            (["--seed", "-1", "some text"], "negative seed"),
            (["--check"], "install check"),
            (["x" * 100000], "100KB single token"),
            (["--json", "--tier", "lite", "em dash — and emoji 🎉 text"],
             "unicode json run"),
        ],
        "score": [
            ([], "no input"),
            (["--help"], "help"),
            (["--tier", "bogus", "hello"], "bad tier"),
            (["--tier", "lite", "the committee approved the proposal yesterday"],
             "valid lite run"),
            (["--json", "--tier", "lite", "short"], "json lite run"),
            (["\ud800"], "surrogate argv"),
            (["--file", "nope.txt"], "missing file"),
            (["--threshold", "2.5", "text"], "out-of-range threshold"),
            (["--threshold", "abc", "text"], "non-numeric threshold"),
            (["--tier", "lite", "x" * 200000], "200KB text"),
            (["--quiet", "--tier", "lite", "quiet run"], "quiet run"),
            (["--browser", "zerogpt", "text"], "browser arg (network)"),
        ],
        "loop": [
            ([], "no input"),
            (["--help"], "help"),
            (["--tier", "bogus", "hello"], "bad tier"),
            (["--tier", "lite", "--json", "the committee approved the proposal"],
             "valid lite loop"),
            (["--max-iters", "0", "some text"], "zero iterations"),
            (["--max-iters", "abc", "text"], "non-int iters"),
            (["--file", "nope.txt"], "missing file"),
            (["--seed", "-5", "text"], "negative seed"),
            (["\ud800"], "surrogate argv"),
            (["--best-of", "0", "text"], "best-of zero"),
            (["--margin", "2.0", "--json", "text"], "out-of-range margin"),
            (["--style", "zz", "some text"], "unknown style"),
        ],
    }

    for cli, cases in base_cases.items():
        for argv, desc in cases:
            cmd = [PY, "-m", module_for[cli]] + [a for a in argv]
            timeout = 70 if (cli == "untell" and not argv) else 40
            t0 = time.time()
            try:
                proc = subprocess.run(cmd, env=ENV, capture_output=True,
                                      text=True, encoding="utf-8",
                                      errors="replace", timeout=timeout,
                                      cwd=REPO, stdin=subprocess.DEVNULL)
                stderr = proc.stderr or ""
                tb = "Traceback (most recent call last)" in stderr
                findings.append({
                    "surface": f"cli:{cli}", "argv": argv, "desc": desc,
                    "status": "exception" if tb else "ok",
                    "code": proc.returncode,
                    "elapsed": round(time.time() - t0, 1),
                    "stderr_tail": stderr[-500:],
                })
            except subprocess.TimeoutExpired:
                findings.append({
                    "surface": f"cli:{cli}", "argv": argv, "desc": desc,
                    "status": "hang", "elapsed": round(time.time() - t0, 1),
                    "stderr_tail": "",
                })
            except Exception as exc:  # e.g. subprocess arg-encoding failure
                findings.append({
                    "surface": f"cli:{cli}", "argv": repr(argv), "desc": desc,
                    "status": f"spawn_error:{type(exc).__name__}",
                    "elapsed": round(time.time() - t0, 1),
                    "stderr_tail": str(exc)[:300],
                })
            log(f"  one-shot {cli} {argv[:3]!r} -> "
                f"{findings[-1]['status']} code={findings[-1].get('code')} "
                f"{findings[-1]['elapsed']}s")

    # binary stdin on all three CLIs (reads stdin with utf-8 -> decode error?)
    for cli in ("untell", "score", "loop"):
        cmd = [PY, "-m", module_for[cli]]
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, env=ENV, capture_output=True,
                                  input=b"\xff\xfe\x00\x01binary\x80garbage",
                                  timeout=30, cwd=REPO)
            stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
            tb = "Traceback (most recent call last)" in stderr
            findings.append({
                "surface": f"cli:{cli}:binary-stdin",
                "argv": ["<binary stdin>"], "desc": "binary stdin",
                "status": "exception" if tb else "ok",
                "code": proc.returncode,
                "elapsed": round(time.time() - t0, 1),
                "stderr_tail": stderr[-400:],
            })
        except subprocess.TimeoutExpired:
            findings.append({"surface": f"cli:{cli}:binary-stdin",
                             "argv": ["<binary stdin>"], "desc": "binary stdin",
                             "status": "hang",
                             "elapsed": round(time.time() - t0, 1),
                             "stderr_tail": ""})
        log(f"  one-shot {cli} <binary stdin> -> {findings[-1]['status']}")

    # console-script .exe wrappers (entry-point shim path)
    for exe in ("untell-score.exe", "untell-loop.exe"):
        try:
            proc = subprocess.run([os.path.join(REPO, ".venv", "Scripts", exe),
                                   "--help"], env=ENV, capture_output=True,
                                  timeout=30, cwd=REPO)
            findings.append({
                "surface": f"cli:exe:{exe}", "argv": ["--help"], "desc": "exe shim",
                "status": "ok", "code": proc.returncode,
                "elapsed": 0.0, "stderr_tail": (proc.stderr or "")[-200:],
            })
        except Exception as exc:
            findings.append({"surface": f"cli:exe:{exe}", "argv": ["--help"],
                             "desc": "exe shim",
                             "status": f"spawn_error:{type(exc).__name__}",
                             "elapsed": 0.0, "stderr_tail": str(exc)[:200]})
    return findings


# ---------------------------------------------------------------------------
# Aggregation / classification / reproducers
# ---------------------------------------------------------------------------

def short_input(case: dict) -> str:
    s = json.dumps(case, ensure_ascii=True, default=str)
    return s[:200] + ("…" if len(s) > 200 else "")


def write_reproducer(finding: dict, n: int) -> str:
    """Write a standalone reproducer script with the finding documented."""
    surface = finding.get("surface", "unknown")
    case = finding.get("case") or {}
    path = os.path.join(HERE, f"fuzz_repro_{surface.replace(':', '_')}_{n}.py")
    lines = [
        '"""FUZZ REPRODUCER — generated by fuzz_driver.py (novel probe).',
        "",
        f"Finding #{n}: {finding.get('severity')} — {finding.get('title')}",
        f"Status: {finding.get('status')}",
        f"Input : {short_input(case)}",
        "",
        f"Exception: {finding.get('exc', 'n/a')}",
        "",
        "Run:  PYTHONPATH= UNTELL_LITE_NO_TORCH=1 .venv/Scripts/python.exe "
        ".claude/probes/" + os.path.basename(path),
        '"""',
        "",
        "import sys, traceback",
        "",
    ]
    if surface == "score":
        lines += [
            "from untell.scripts.score import score_text",
            "",
            "TEXT = ...  # see input JSON above — reconstruct from the case",
            "def main():",
            "    try:",
            "        r = score_text(TEXT, tier='lite')",
            "        print('ok', r.get('max'))",
            "    except Exception:",
            "        traceback.print_exc()",
            "        return 1",
            "    return 0",
            "",
            "if __name__ == '__main__':",
            "    sys.exit(main())",
        ]
    elif surface == "loop":
        lines += [
            "from untell.scripts.run import untell_text",
            "",
            "def main():",
            "    try:",
            "        r = untell_text(TEXT, tier='lite', max_iters=2, best_of=1)",
            "        print('ok', r.get('stopped'))",
            "    except Exception:",
            "        traceback.print_exc()",
            "        return 1",
            "    return 0",
            "",
            "if __name__ == '__main__':",
            "    sys.exit(main())",
        ]
    else:
        lines += ["# See findings JSON for the exact case spec.",
                  "raise SystemExit('reconstruct from fuzz_findings.json')"]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def classify(res: dict, surface: str) -> dict | None:
    """Turn a worker result line into a finding, or None if benign."""
    status = res.get("status")
    exc = res.get("exc", "")
    kind = res.get("kind")
    case = {k: res[k] for k in ("text", "argv", "tier", "threshold", "max_iters",
                                "kind", "fn", "mapping", "include_matches",
                                "seed", "which") if k in res}

    if status == "exception":
        exc_type = res.get("exc_type", "?")
        if surface == "score":
            if kind == "str":
                sev, title = "DEFECT", f"score_text raised {exc_type} on str input"
            elif kind in ("bytes", "type"):
                sev, title = "GAP", (f"score_text raised {exc_type} on "
                                     f"{kind} input (typed API, but raw leak)")
            else:  # param
                sev, title = "GAP", f"score_text raised {exc_type} on param variant"
        elif surface == "loop":
            # untell_text on str is the primary surface -> defect unless input
            # is clearly type-malformed (bytes/None text)
            sev, title = "DEFECT", f"untell_text raised {exc_type} on str input"
        elif surface == "preserve":
            if kind == "roundtrip":
                sev, title = "DEFECT", f"lock/restore raised {exc_type} on str"
            else:
                sev, title = "GAP", f"preserve raised {exc_type} on {kind} input"
        elif surface == "tells":
            if kind == "str":
                sev, title = "DEFECT", f"score_tells raised {exc_type} on str"
            else:
                sev, title = "GAP", f"score_tells raised {exc_type} on {kind}"
        else:
            sev, title = "GAP", f"cli main() raised {exc_type}"
        return {"severity": sev, "title": title, "status": status,
                "exc": exc, "case": case, "input_preview": res.get("input_preview"),
                "head": res.get("head"), "site": res.get("site")}

    if status == "hang_thread" or status == "hang_isolated":
        return {"severity": "DEFECT", "title": f"HANG on {surface} input",
                "status": status, "exc": "timeout", "case": case,
                "input_preview": res.get("input_preview"),
                "elapsed": res.get("elapsed")}

    if status == "crash":
        return {"severity": "DEFECT", "title": f"PROCESS CRASH on {surface} input",
                "status": status, "exc": "segfault/hard-kill", "case": case,
                "input_preview": res.get("input_preview")}

    if status == "ok" and surface == "preserve" and res.get("same") is False:
        return {"severity": "GAP", "title": "lock/restore round-trip changed text",
                "status": "mismatch", "exc": "identity violation", "case": case,
                "input_preview": res.get("input_preview")}
    return None


def main() -> int:
    import fuzz_corpus

    quick = "--quick" in sys.argv
    findings: list[dict] = []
    t_start = time.time()

    # ---- Surface 1: score_text ----
    log("building score cases…")
    score_cases = fuzz_corpus.build_score_cases(
        n_str=150 if quick else 300, n_bytes=150 if quick else 300,
        n_type=50 if quick else 100)
    # lump param cases into the unicode chunks (they are cheap)
    str_cases = [c for c in score_cases if c["kind"] == "str"]
    param_cases = [c for c in score_cases if c["kind"] == "param"]
    bytes_cases = [c for c in score_cases if c["kind"] == "bytes"]
    type_cases = [c for c in score_cases if c["kind"] == "type"]
    str_cases += param_cases
    res = fuzz_surface("score", str_cases, 20.0, 0.3, 100, "score_str")
    res += fuzz_surface("score", bytes_cases, 20.0, 0.3, 150, "score_bytes")
    res += fuzz_surface("score", type_cases, 20.0, 0.3, 100, "score_type")
    for r in res:
        f = classify(r, "score")
        if f:
            f["surface"] = "score"
            findings.append(f)
    log(f"score: {len(res)} cases, {sum(1 for f in findings if f['surface']=='score')} findings")

    # ---- Surface 2: untell_text loop ----
    log("building loop cases…")
    loop_cases = fuzz_corpus.build_loop_cases(300 if not quick else 120)
    res = fuzz_surface("loop", loop_cases, 90.0, 4.0, 50, "loop")
    for r in res:
        f = classify(r, "loop")
        if f:
            f["surface"] = "loop"
            findings.append(f)
    log(f"loop: {len(res)} cases, {sum(1 for f in findings if f['surface']=='loop')} findings")

    # ---- Surface 3: CLIs ----
    log("building CLI cases…")
    for which, tag in (("untell", "cli_untell"), ("score", "cli_score"),
                       ("loop", "cli_loop")):
        n = 120 if quick else 150
        cli_cases = fuzz_corpus.build_cli_cases(n, seed=100 + hash(which) % 1000)
        for c in cli_cases:
            c["which"] = which
        # drop demo-triggering argv for `untell` (documented ~28s demo);
        # exercised via one-shot subprocess instead
        if which == "untell":
            cli_cases = [c for c in cli_cases
                         if c.get("argv") and c["argv"][0] not in ("--demo", "-d")]
        res = fuzz_surface("cli", cli_cases, 40.0, 4.0, 150, tag)
        for r in res:
            f = classify(r, "cli")
            if f:
                f["surface"] = f"cli:{which}"
                findings.append(f)
        log(f"cli {which}: {len(res)} cases")

    # ---- Surface 4: preserve lock/restore ----
    log("building preserve cases…")
    pres_cases = fuzz_corpus.build_preserve_cases(400 if not quick else 150)
    res = fuzz_surface("preserve", pres_cases, 20.0, 0.3, 200, "preserve")
    for r in res:
        f = classify(r, "preserve")
        if f:
            f["surface"] = "preserve"
            findings.append(f)
    log(f"preserve: {len(res)} cases, {sum(1 for f in findings if f['surface']=='preserve')} findings")

    # ---- Surface 5: tells scan ----
    log("building tells cases…")
    tells_cases = fuzz_corpus.build_tells_cases(400 if not quick else 150)
    res = fuzz_surface("tells", tells_cases, 20.0, 0.4, 200, "tells")
    for r in res:
        f = classify(r, "tells")
        if f:
            f["surface"] = "tells"
            findings.append(f)
    log(f"tells: {len(res)} cases, {sum(1 for f in findings if f['surface']=='tells')} findings")

    # ---- One-shot CLI subprocess tests ----
    log("running one-shot CLI subprocess tests…")
    one_shots = cli_one_shots()
    for r in one_shots:
        if r["status"] == "exception":
            findings.append({"severity": "GAP",
                             "title": f"CLI traceback ({r['desc']})",
                             "status": "exception", "exc": "traceback on stderr",
                             "case": {"argv": r["argv"]},
                             "site": r["stderr_tail"][-300:]})
        elif r["status"] == "hang":
            findings.append({"severity": "DEFECT",
                             "title": f"CLI hang ({r['desc']})",
                             "status": "hang", "exc": "subprocess timeout",
                             "case": {"argv": r["argv"]},
                             "elapsed": r["elapsed"]})
        elif r["status"].startswith("spawn_error"):
            findings.append({"severity": "GAP",
                             "title": f"CLI spawn failure ({r['desc']})",
                             "status": r["status"], "exc": r["stderr_tail"],
                             "case": {"argv": r["argv"]}})
    log(f"one-shots: {len(one_shots)} runs")

    # ---- Dedupe by (surface, exc, input_preview) ----
    seen = set()
    deduped = []
    for f in findings:
        key = (f["surface"], f["title"], f.get("input_preview") or
               json.dumps(f.get("case", {}), ensure_ascii=True)[:80])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)

    # ---- Reproducers for the top findings ----
    repro_paths = []
    for i, f in enumerate(deduped[:8], start=1):
        if f["status"] in ("exception", "hang", "crash", "mismatch"):
            try:
                p = write_reproducer(f, i)
                repro_paths.append(p)
            except Exception as exc:  # reproducer is best-effort
                log(f"  reproducer {i} failed: {exc}")

    out = {"findings": deduped, "one_shots": one_shots,
           "elapsed_total": round(time.time() - t_start, 1),
           "reproducers": repro_paths}
    with open(os.path.join(HERE, "fuzz_findings.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=True, indent=1, default=str)

    # ---- Print numbered findings ----
    print("\n" + "=" * 78)
    print(f"UNTELL FUZZ — {len(deduped)} unique findings "
          f"({time.time() - t_start:.0f}s)")
    print("=" * 78)
    for i, f in enumerate(deduped, start=1):
        print(f"\n{i}. [{f['severity']}] {f['title']}")
        print(f"   surface : {f['surface']}  status={f['status']}")
        if f.get("input_preview"):
            print(f"   input   : {f['input_preview']!r}")
        elif f.get("case"):
            print(f"   case    : {short_input(f['case'])}")
        if f.get("exc"):
            print(f"   exc     : {f['exc'][:220]}")
        if f.get("head"):
            print(f"   head    : {f['head'][:220]}")
        if f.get("site"):
            print(f"   site    : {f['site'][:400]}")
    print("\nFindings JSON: .claude/probes/fuzz_findings.json")
    if repro_paths:
        print("Reproducers  : " + ", ".join(repro_paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
