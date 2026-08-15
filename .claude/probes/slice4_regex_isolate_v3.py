"""Definitive hang isolation via subprocess + stderr capture.

One subprocess per INPUT; each pattern's label is written to stderr before its
scan (flushed). A timed-out child is killed and its captured stderr shows the
last pattern that started = the hang culprit. No queues, no races.
"""
from __future__ import annotations

import subprocess
import sys

INPUTS = {
    "backticks_100k": "`" * 100_000,
    "dollar_50k": "$" * 50_000,
    "parens_30k": "(" * 30_000,
    "a_repeat_200k": "a" * 200_000,
    "ambiguous_run": ("ab" * 50_000) + "!",
    "wide_x_100k": "x" * 100_000,
}

CHILD = r"""
import sys, time
sys.path.insert(0, r"{root}")
from untell.scripts.preserve import _PATTERNS
text = open(r"{fname}", encoding="utf-8").read()
t0 = time.monotonic()
for label, pat in _PATTERNS:
    sys.stderr.write(f"START {{label}} {{time.monotonic()-t0:.1f}}s\n")
    sys.stderr.flush()
    total = 0
    for m in pat.finditer(text):
        total += m.end() - m.start()
    sys.stderr.write(f"DONE {{label}}\n")
sys.stderr.write("ALL DONE\n")
"""


def main() -> int:
    import os
    import tempfile

    root = os.path.dirname(os.path.abspath(__file__))
    tmpdir = tempfile.mkdtemp(prefix="slice4_regex_")
    for name, text in INPUTS.items():
        fname = os.path.join(tmpdir, name + ".txt")
        with open(fname, "w", encoding="utf-8") as fh:
            fh.write(text)
        code = CHILD.format(root=root, fname=fname)
        p = subprocess.Popen(
            [sys.executable, "-u", "-c", code],
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
        )
        try:
            _, err = p.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            p.kill()
            _, err = p.communicate()
            lines = [ln for ln in err.decode(errors="replace").splitlines() if ln]
            print(f"HANG: {name}  full stderr follows:")
            print("\n".join(lines))
            continue
        lines = err.decode(errors="replace").splitlines()
        ok = [ln for ln in lines if ln.startswith("DONE")]
        print(f"ok: {name}  patterns done: {len(ok)} ({lines[-1] if lines else '?'})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())