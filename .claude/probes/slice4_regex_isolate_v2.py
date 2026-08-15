"""Definitive per-(pattern, input) hang isolation.

One child per (pattern, input); the child writes the pattern label to stderr
BEFORE scanning and a watchdog thread os._exit(1)s after 20s. The parent's
stderr shows exactly which pair hung. No queue, no drain race.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import sys
import time

INPUTS = {
    "backticks_100k": "`" * 100_000,
    "dollar_50k": "$" * 50_000,
    "parens_30k": "(" * 30_000,
    "a_repeat_200k": "a" * 200_000,
    "ambiguous_run": ("ab" * 50_000) + "!",
    "wide_x_100k": "x" * 100_000,
}


def child(args):
    label, pat, text = args
    import re

    def _die():
        time.sleep(20)
        os._exit(99)

    threading = __import__("threading")
    threading.Thread(target=_die, daemon=True).start()
    sys.stderr.write(f"SCAN {label}\n")
    sys.stderr.flush()
    n = 0
    for m in pat.finditer(text):
        n += m.end() - m.start()
    sys.stderr.write(f"DONE {label} spans={n}\n")
    sys.stderr.flush()


def main() -> int:
    from untell.scripts.preserve import _PATTERNS

    ctx = mp.get_context("spawn")
    tasks = [
        (label, pat, INPUTS[name])
        for name, text in INPUTS.items()
        for label, pat in _PATTERNS
    ]
    hung = []
    ok = []
    for t in tasks:
        p = ctx.Process(target=child, args=(t,))
        p.start()
        p.join(25)
        if p.is_alive():
            p.terminate()
            p.join()
            print(f"HANG {t[0]} on input-start {t[2][:30]!r}", flush=True)
            hung.append(t)
        else:
            ok.append(t)
    print(f"\n{len(ok)} ok, {len(hung)} HANG")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())