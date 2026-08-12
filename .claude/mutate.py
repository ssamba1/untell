"""Break one line of a module on purpose and see whether any test notices.

A test that passes against a deliberately broken module proves nothing about that module.
This repo has already paid for that lesson several times: five tests asserted the buggy
behaviour they were written to catch, and a quoting fix in a sibling project survived 27
review passes because its test mocked the engine and could not tell a valid escape from an
invalid one. Reading a test cannot tell you which kind it is. Breaking the code can.

So this walks a source file, applies one small textual mutation at a time (a comparison
flipped, a boolean swapped, a constant nudged), runs the tests that mention the module, and
reports every mutation the suite did NOT catch. Each survivor is a coverage gap with a
mechanical proof attached — no judgement call, which is the point when the agent driving it
is small and fast.

    python .claude/mutate.py untell/scripts/scrub.py --max 12
    python .claude/mutate.py untell/layout.py --tests tests/test_layout_blocks.py

No dependencies beyond pytest. Deliberately not mutmut or cosmic-ray: adding a dependency to
run unattended is outside what this loop is allowed to decide on its own.
"""

from __future__ import annotations

import argparse
import atexit
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / ".claude" / "survivors.md"
PY = sys.executable

# Word-boundary swaps only, and only ones that keep the file parseable. A mutation that fails
# to import is killed by every test for the wrong reason and tells you nothing.
OPERATORS: list[tuple[str, str, str]] = [
    (r"(?<![<>=!-])<=(?!=)", "<", "boundary: <= -> <"),
    (r"(?<![<>=!-])>=(?!=)", ">", "boundary: >= -> >"),
    (r"(?<![<>=!-])<(?![=<])", "<=", "boundary: < -> <="),
    # `-` excluded on every `>` operator: `->` in a return annotation is not a comparison,
    # and mutating it produces a mutant that fails to parse.
    (r"(?<![<>=!-])>(?![=>])", ">=", "boundary: > -> >="),
    (r"(?<![<>=!-])==(?!=)", "!=", "logic: == -> !="),
    (r"(?<![<>=!-])!=(?!=)", "==", "logic: != -> =="),
    (r"\band\b", "or", "logic: and -> or"),
    (r"\bor\b", "and", "logic: or -> and"),
    (r"\bTrue\b", "False", "constant: True -> False"),
    (r"\bFalse\b", "True", "constant: False -> True"),
    (r"\bnot in\b", "in", "membership: not in -> in"),
    (r"\bis not\b", "is", "identity: is not -> is"),
]

NUMBER = re.compile(r"(?<![\w.])(\d+)(?![\w.])")


def mutable_lines(text: str) -> set[int]:
    """Line numbers that are executable code, not comments or docstrings.

    Mutating prose produces survivors that mean nothing, and a loop that reports meaningless
    survivors trains its operator to ignore the report.
    """
    out: set[int] = set()
    in_doc = False
    delim = ""
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if in_doc:
            if delim in line:
                in_doc = False
            continue
        if line.startswith(("#", "@")) or not line:
            continue
        for d in ('"""', "'''"):
            if line.startswith(d):
                # A one-line docstring opens and closes on the same line.
                if not (len(line) > 5 and line.endswith(d)):
                    in_doc, delim = True, d
                break
        else:
            out.add(i)
    return out


def mask(line: str) -> str:
    """Blank out string literals and trailing comments, preserving every column.

    Without this, `help="Text to scrub (or use --file)"` yields an `or -> and` mutant and
    `# never crash on a non-UTF-8 stdout` yields `8 -> 9`. Both are edits to prose: no test
    can ever kill them, so every run would report them as survivors and the real survivors
    would be lost in the noise. Matching happens on the mask, splicing on the real line.
    """
    out = []
    quote = ""
    esc = False
    for ch in line:
        if quote:
            out.append("\0")
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            out.append("\0")
            continue
        if ch == "#":
            out.extend("\0" * (len(line) - len(out)))
            break
        out.append(ch)
    return "".join(out)


def candidates(path: Path) -> list[tuple[int, str, str, str]]:
    text = path.read_text(encoding="utf-8")
    live = mutable_lines(text)
    found: list[tuple[int, str, str, str]] = []
    for n, line in enumerate(text.splitlines(), start=1):
        # The __main__ guard is scaffolding: no test imports it, so mutating it always
        # survives and always means nothing.
        if n not in live or "__name__" in line:
            continue
        masked = mask(line)
        for pattern, repl, label in OPERATORS:
            m = re.search(pattern, masked)
            if m:
                found.append((n, line[: m.start()] + repl + line[m.end() :], label, line))
        m = NUMBER.search(masked)
        if m and m.group(1) not in {"0", "1"}:
            bumped = line[: m.start()] + str(int(m.group(1)) + 1) + line[m.end() :]
            found.append((n, bumped, f"constant: {m.group(1)} -> {int(m.group(1)) + 1}", line))
    return found


def record_survivors(module: str, survivors: list[tuple[int, str, str]]) -> int:
    """Append survivors to the ledger, skipping ones already listed.

    Without this, `--max 15` on a module with 200 mutable lines re-finds the same easy
    survivors every visit and never reaches the rest. The ledger is what makes a lane over
    sixteen modules converge instead of circling.
    """
    if not LEDGER.exists():
        LEDGER.write_text(
            "# Mutation survivors\n\n"
            "Lines no test pins, each found by breaking it and watching the suite stay green.\n"
            "Append-only; a human deletes a row once it has a killing test, or marks it\n"
            "unkillable with the reason. Written by `mutate.py --record`.\n\n"
            "| module | line | mutation | source |\n| --- | --- | --- | --- |\n",
            encoding="utf-8",
        )
    seen = LEDGER.read_text(encoding="utf-8")
    fresh = [s for s in survivors if f"| {module} | {s[0]} | {s[1]} |" not in seen]
    with LEDGER.open("a", encoding="utf-8") as f:
        for n, label, src in fresh:
            f.write(f"| {module} | {n} | {label} | `{src[:80].replace('|', '/')}` |\n")
    return len(fresh)


def pick_tests(path: Path, explicit: list[str]) -> list[str]:
    """Test files that import this module, not merely ones that mention its name.

    Matching the bare stem selected 96 files for `scrub.py` — most of them saying the word in
    a docstring — and every one of those would be re-run for every mutant. The import path is
    the honest signal for "this file exercises that module".
    """
    if explicit:
        return explicit
    dotted = ".".join(path.relative_to(ROOT).with_suffix("").parts)
    package, name = dotted.rsplit(".", 1)
    patterns = (
        dotted,                          # untell.scripts.scrub
        f"from {package} import {name}",  # from untell.scripts import scrub
        f"import {name}",                 # bare, for a conftest-style import
    )
    return [
        str(t.relative_to(ROOT))
        for t in sorted((ROOT / "tests").glob("test_*.py"))
        if any(pat in t.read_text(encoding="utf-8", errors="ignore") for pat in patterns)
    ]


def run_tests(tests: list[str], timeout: int) -> tuple[bool, str]:
    start = time.monotonic()
    try:
        p = subprocess.run(
            [PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *tests],
            cwd=ROOT,
            capture_output=True,
            # Explicit, not `text=True`: that decodes with the console codepage, and a single
            # byte cp1252 cannot map kills the reader thread, leaving `.stdout` None with a
            # return code of 0. Here that would read as "tests passed" for every mutant - the
            # harness would report a clean sweep having verified nothing.
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    tail = next(iter(reversed((p.stdout or "").strip().splitlines())), "no output")
    return p.returncode == 0, f"{tail}  [{time.monotonic() - start:.0f}s]"


def main() -> int:
    # Each mutant costs a full pytest run, so a quiet hour looks identical to a hang. Line
    # buffering keeps the per-mutant verdicts arriving live even when stdout is a pipe, which
    # is how the loop always runs it.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("module", help="source file to mutate, e.g. untell/scripts/scrub.py")
    ap.add_argument("--tests", nargs="*", default=[], help="test files (default: any naming it)")
    ap.add_argument("--max", type=int, default=15, help="mutants to try")
    ap.add_argument("--seed", type=int, default=0, help="sampling seed; same seed = same run")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--list", action="store_true", help="show candidates and exit")
    ap.add_argument("--record", action="store_true", help="append survivors to the ledger")
    a = ap.parse_args()

    path = (ROOT / a.module).resolve()
    if not path.is_file():
        sys.exit(f"no such file: {a.module}")

    # A crash mid-run must never leave a mutated file behind. The backup is the first thing
    # created and the last thing removed; git is the second net, so refuse a dirty file.
    dirty = subprocess.run(
        ["git", "diff", "--quiet", "--", str(path)], cwd=ROOT, capture_output=True
    ).returncode
    if dirty:
        sys.exit(f"REFUSED: {a.module} has uncommitted changes. Commit or stash first.")

    found = candidates(path)
    if a.list:
        for n, _, label, src in found:
            print(f"{a.module}:{n}: {label}   |   {src.strip()[:90]}")
        print(f"\n{len(found)} candidate mutations")
        return 0
    if not found:
        print(f"no mutable constructs in {a.module}")
        return 0

    tests = pick_tests(path, a.tests)
    if not tests:
        sys.exit(f"REFUSED: no test file mentions '{path.stem}'. That IS the finding - "
                 "record it as a coverage gap and write the first test.")
    print(f"module   {a.module}")
    print(f"tests    {len(tests)} file(s): {', '.join(tests[:4])}{' ...' if len(tests) > 4 else ''}")
    if len(tests) > 6:
        # Every mutant pays for the whole selection. A grep-wide match on a common word drags
        # in files that never exercise the module, and the pass runs out of hour before it
        # runs out of mutants.
        print(f"WARNING  {len(tests)} test files is a lot to run {a.max} times. Consider "
              f"--tests with the 2-3 that actually exercise this module.")

    backup = Path(tempfile.gettempdir()) / f"{path.name}.mutate-backup"
    shutil.copy2(path, backup)
    original = path.read_text(encoding="utf-8")
    atexit.register(lambda: path.write_text(original, encoding="utf-8"))

    try:
        ok, tail = run_tests(tests, a.timeout)
        if not ok:
            sys.exit(f"REFUSED: the tests are already failing ({tail}). A mutant cannot be "
                     "distinguished from a pre-existing failure. Fix the red first.")
        print(f"baseline green: {tail}\n")

        sample = found if len(found) <= a.max else random.Random(a.seed).sample(found, a.max)
        sample.sort(key=lambda c: c[0])
        lines = original.splitlines(keepends=True)
        survivors = []

        for i, (n, mutated, label, src) in enumerate(sample, start=1):
            patched = list(lines)
            patched[n - 1] = mutated + ("\n" if not mutated.endswith("\n") else "")
            path.write_text("".join(patched), encoding="utf-8")
            killed, tail = run_tests(tests, a.timeout)
            path.write_text(original, encoding="utf-8")
            verdict = "TIMEOUT " if tail == "TIMEOUT" else ("killed  " if not killed else "SURVIVED")
            print(f"[{i}/{len(sample)}] {verdict} {a.module}:{n}  {label}")
            if killed and tail != "TIMEOUT":
                survivors.append((n, label, src.strip()))

        print(f"\n{len(survivors)} survived of {len(sample)} tried")
        for n, label, src in survivors:
            print(f"  SURVIVED {a.module}:{n}  {label}")
            print(f"           {src[:100]}")
        if survivors:
            print("\nEach survivor is a line the suite does not pin. Write ONE test that fails "
                  "against the mutation and passes against the original.")
            if a.record:
                print(f"recorded {record_survivors(a.module, survivors)} new survivor(s) in "
                      f"{LEDGER.relative_to(ROOT)}")
        return 0
    finally:
        path.write_text(original, encoding="utf-8")
        backup.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
