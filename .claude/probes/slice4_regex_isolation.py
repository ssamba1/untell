"""Isolate which preserve._PATTERNS entry backtracks on which adversarial input.

Runs ONE input in a child process; the child prints the pattern label (flushed)
before scanning it, so when the child is killed the last printed label is the
culprit. Independent of multiprocessing pool bookkeeping.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys
import time

INPUTS = {
    "backticks_100k": "`" * 100_000,
    "fence_open_50k": "```" * 16_000 + "text",
    "dollar_50k": "$" * 50_000,
    "parens_30k": "(" * 30_000,
    "a_repeat_200k": "a" * 200_000,
    "ambiguous_run": ("ab" * 50_000) + "!",
}


def child(name: str, q):
    from untell.scripts.preserve import _PATTERNS

    text = INPUTS[name]
    t0 = time.monotonic()
    for label, pat in _PATTERNS:
        q.put(f"START {label}")
        total = 0
        for m in pat.finditer(text):
            total += m.end() - m.start()
        q.put(f"DONE {label} {round(time.monotonic() - t0, 2)}s spans={total}")
    q.put("ALL DONE")


def _drain(q):
    lines = []
    while not q.empty():
        try:
            lines.append(q.get_nowait())
        except Exception:
            break
    return lines


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    names = list(INPUTS) if which == "all" else [which]
    ctx = mp.get_context("spawn")
    out = {}
    for name in names:
        q = ctx.Queue()
        p = ctx.Process(target=child, args=(name, q))
        p.start()
        lines = []
        p.join(45)
        lines += _drain(q)
        if p.is_alive():
            p.terminate()
            p.join()
            last_start = [ln for ln in lines if ln.startswith("START ")]
            out[name] = {
                "status": "TIMEOUT 45s",
                "last_started": last_start[-1] if last_start else "none",
            }
        else:
            out[name] = {"status": "ok", "lines": lines}
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())