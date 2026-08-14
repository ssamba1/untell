"""fuzz_worker.py — chunk executor for the untell fuzz probe.

Runs inside a fresh subprocess (so crashes/hangs are isolated from the
orchestrator) and executes `cases.jsonl` cases for ONE surface, appending one
JSON result line per case to `out.jsonl` as it goes (incremental — a crash or
kill leaves a prefix the driver can read to locate the offending case).

Usage:
    python fuzz_worker.py <surface> <cases.jsonl> <out.jsonl> <case_timeout_s>

Surfaces:
    score     -> untell.scripts.score.score_text (str / bytes / type / param)
    loop      -> untell.scripts.run.untell_text  (default composite rewriter)
    preserve  -> preserve.lock / restore round-trips + adversarial restore
    tells     -> untell.scripts.tells.score_tells / looks_non_english
    cli       -> run one CLI main() in-process with the case's argv

Per-case execution happens in a daemon thread with a timeout. That catches
most hangs (anything that releases the GIL — stdin blocking, network, sleeps).
A GIL-holding hang (regex catastrophe) stalls the whole process; the DRIVER
detects that via a chunk wall-clock deadline and binary-searches the chunk.

IMPORTANT: run with PYTHONPATH= and UNTELL_LITE_NO_TORCH=1 (Hermes venv
shadows pydantic_core; torch import costs ~10s on first call).
"""
from __future__ import annotations

import faulthandler
import io
import json
import os
import sys
import threading
import time
import traceback


def _capture_exc() -> tuple[str, str]:
    tb = traceback.format_exc()
    lines = tb.splitlines()
    # first line + the untell/ site frames (skip deep site-packages spam)
    head = lines[0] if lines else "?"
    site = [l for l in lines if "untell" in l or l.startswith("  File")]
    return head, "\n".join(site[:12])


# ---------------------------------------------------------------------------
# Case runners. Each returns a result dict (JSON-safe).
# ---------------------------------------------------------------------------

def run_score_case(case: dict) -> dict:
    from untell.scripts.score import score_text
    value = _materialise(case.get("text"))
    tier = case.get("tier", "lite")
    threshold = case.get("threshold", 0.3)
    res = score_text(value, tier=tier, threshold=threshold)
    return {"ok": True, "tier": res.get("tier"), "max": res.get("max")}


def run_loop_case(case: dict) -> dict:
    from untell.scripts.run import untell_text
    text = _materialise(case.get("text"))
    kwargs = {
        "tier": case.get("tier", "lite"),
        "max_iters": case.get("max_iters", 2),
        "best_of": case.get("best_of", 1),
        "seed": case.get("seed", 7),
        "rewriter": None,  # default composite path (~0.8s); structural is 66s/call
    }
    if "threshold" in case:
        kwargs["threshold"] = case["threshold"]
    if "scrub" in case:
        kwargs["scrub"] = case["scrub"]
    if "confirm" in case:
        kwargs["confirm"] = case["confirm"]
    res = untell_text(text, **kwargs)
    return {"ok": True, "stopped": res.get("stopped"), "err": res.get("error"),
            "iterations": res.get("iterations")}


def run_preserve_case(case: dict) -> dict:
    from untell.scripts.preserve import lock, restore
    kind = case.get("kind")
    if kind == "roundtrip":
        text = _materialise(case["text"])
        masked, mapping = lock(text)
        back = restore(masked, mapping)
        return {"ok": True, "same": back == text,
                "masked": masked, "back": back, "orig": text}
    if kind == "adversarial":
        text = _materialise(case["text"])
        masked, mapping = lock(text)
        merged = dict(mapping)
        merged.update(case.get("mapping", {}))  # inject fake/type-wrong entries
        back = restore(masked, merged)
        return {"ok": True, "same": back == text, "back": back, "orig": text}
    # type-malformed
    fn = case.get("fn", "lock")
    arg = _materialise(case.get("arg"))
    if fn == "lock":
        masked, mapping = lock(arg)
    else:
        back = restore(arg, {"⟦HZ0000⟧": "x"})
    return {"ok": True}


def run_tells_case(case: dict) -> dict:
    from untell.scripts.tells import score_tells, looks_non_english
    kind = case.get("kind")
    if kind == "bytes" or kind == "type":
        value = _materialise(case["text"])
        r = score_tells(value, include_matches=True)
        return {"ok": True, "tells": r.get("total")}
    text = _materialise(case["text"])
    r = score_tells(text, include_matches=case.get("include_matches", False))
    non_en = looks_non_english(text)
    return {"ok": True, "tells": r.get("total"), "non_en": bool(non_en)}


def run_cli_case(case: dict) -> dict:
    """Run one CLI main() in-process with the case argv; capture stdout."""
    argv = case.get("argv", [])
    which = case.get("which", "score")
    if which == "untell":
        from untell.scripts.cli import main
    elif which == "loop":
        from untell.scripts.run import main
    else:
        from untell.scripts.score import main
    buf = io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = buf, buf
    try:
        code = main(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else -1
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    out = buf.getvalue()
    return {"ok": True, "code": code, "out_tail": out[-400:],
            "traceback": "Traceback (most recent call last)" in out}


_SURFACES = {
    "score": run_score_case,
    "loop": run_loop_case,
    "preserve": run_preserve_case,
    "tells": run_tells_case,
    "cli": run_cli_case,
}


def _materialise(spec) -> object:
    """Mirror of fuzz_corpus.materialise (worker must not import corpus from a
    path the driver controls — keep the worker self-contained)."""
    if isinstance(spec, dict):
        if "b" in spec:
            import base64
            return base64.b64decode(spec["b"])
        if "t" in spec:
            return {"none": None, "int": 7, "float": 1.5, "nan": float("nan"),
                    "inf": float("inf"), "list": [1, "x"], "dict": {"k": "v"},
                    "set": {1, 2}, "tuple": (1, 2), "bytes_empty": b"",
                    "bytearray": bytearray(b"x"), "complex": 1 + 2j,
                    "object": object(), "bool": True,
                    "bytes": b"\xff\x00"}[spec["t"]]
        if "v" in spec:
            return spec["v"]
    return spec


def main() -> int:
    surface = sys.argv[1]
    cases_path = sys.argv[2]
    out_path = sys.argv[3]
    case_timeout = float(sys.argv[4])
    runner = _SURFACES[surface]

    faulthandler.enable()
    out_f = open(out_path, "a", encoding="utf-8")
    start_wall = time.time()

    with open(cases_path, "r", encoding="utf-8") as f:
        cases = [json.loads(l) for l in f if l.strip()]

    for idx, case in enumerate(cases):
        result: dict = {"i": idx, "status": "ok"}
        holder: dict = {}
        t0 = time.time()

        def _run():
            try:
                holder["r"] = runner(case)
            except BaseException as exc:  # noqa: BLE001 — fuzz: capture everything
                head, site = _capture_exc()
                holder["r"] = {"exc": f"{type(exc).__name__}: {exc}",
                               "head": head, "site": site,
                               "exc_type": type(exc).__name__}

        th = threading.Thread(target=_run, daemon=True)
        th.start()
        th.join(case_timeout)
        elapsed = time.time() - t0
        if th.is_alive():
            result["status"] = "hang_thread"
            result["elapsed"] = round(elapsed, 2)
        else:
            result.update(holder.get("r") or {})
            result["elapsed"] = round(elapsed, 3)
            if result["status"] == "ok" and "exc" in result:
                result["status"] = "exception"
            if elapsed > case_timeout * 0.6:
                result["slow"] = True
        # keep payloads small but sufficient for repro
        for key in ("text", "argv", "tier", "threshold", "max_iters", "kind",
                    "fn", "mapping", "include_matches", "scrub", "best_of",
                    "confirm", "seed", "which"):
            if key in case:
                val = case[key]
                if key == "text" and isinstance(val, dict) and "v" in val:
                    result["input_preview"] = val["v"][:120]
                elif key == "argv":
                    result["argv"] = val
                else:
                    result[key] = val
        out_f.write(json.dumps(result, ensure_ascii=True, default=str) + "\n")
        out_f.flush()
        if idx % 25 == 0:
            sys.stderr.write(f"[worker {surface}] {idx + 1}/{len(cases)} "
                             f"elapsed={time.time() - start_wall:.0f}s\n")
            sys.stderr.flush()

    out_f.close()
    sys.stderr.write(f"[worker {surface}] DONE {len(cases)} cases\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
