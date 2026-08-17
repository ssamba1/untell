"""CLI conformance matrix: every console script in ``pyproject.toml``.

For each entry point (``module:main``) the matrix asserts the same four contracts a
shell script would rely on:

1. ``--help`` exits 0 and names the command.
2. an unknown flag exits 2 with a message (never silently accepted).
3. missing required arguments exit 2 with a message — or, for commands with no required
   arguments, that the no-args invocation is a documented valid one (covered by the
   minimal-invocation check below).
4. a minimal valid invocation exits 0 (or the command's documented verdict code, where
   the exit code *is* the answer — e.g. ``untell-verify`` returns 1 when a checker
   fails, ``untell-prove`` 2 when nothing ran).

Entry points are exercised as real subprocesses (``python -c "import M; raise
SystemExit(M.main(argv))"``) — byte-equivalent to the console-script shim, and the only
robust surface here: the venv's installed ``.exe`` shims can lag ``pyproject.toml``
(13 of 24 existed at the time of writing), so testing the shims would test install
state, not this repo.

Measured on this machine under ``UNTELL_LITE_NO_TORCH=1``: every fast command below
completes in <2s; the slow ones are marked ``slow`` and run the real workload
(``untell-audit`` ~3min, ``untell-compare`` ~2min, ``untell-prove`` ~2min,
``untell-surrogate --smoke`` ~1.5min, ``untell-detector-audit`` ~2min).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEXT = "This is a plain sentence about nothing at all."


def _console_scripts() -> dict[str, str]:
    """Parse ``[project.scripts]`` from pyproject.toml: name -> "module:function"."""
    py = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    scripts = dict(re.findall(r'^(untell[\w-]*)\s*=\s*"([^"]+)"', py, re.M))
    assert scripts, "no console scripts found — did the pyproject layout change?"
    return scripts


# --- minimal valid invocation per script -----------------------------------------------
# `argv` is passed to the entry point's main(); None means "no minimal invocation exists in
# this environment" and the entry's `expect` documents the clean refusal instead.
# `slow` marks invocations that run the real (model/corpus) workload rather than a smoke path.
MINIMAL: dict[str, dict] = {
    "untell": {"argv": ["tells", TEXT], "expect": 0},
    "untell-score": {"argv": ["--tier", "lite", "-q", TEXT], "expect": 0},
    "untell-loop": {"argv": [TEXT, "--tier", "lite", "--max-iters", "1", "--best-of", "1"], "expect": 0},
    "untell-humanize": {"argv": [TEXT, "--tier", "lite", "--max-iters", "1", "--best-of", "1"], "expect": 0},
    "untell-verify": {"argv": ["-q", TEXT, "--tier", "lite"], "expect": 0},
    "untell-prove": {
        "argv": [TEXT, "--max-iters", "1", "--best-of", "1"],
        "expect": 2,  # no commercial keys: "nothing ran" is exit 2, and it is the documented code
        "slow": True,
    },
    "untell-sentences": {"argv": [TEXT], "expect": 0},
    "untell-tells": {"argv": [TEXT], "expect": 0},
    "untell-voice": {
        # same file for sample and draft -> distance 0 -> "same voice" -> exit 0
        "argv": ["--sample", "__SAMPLE__", "--draft", "__SAMPLE__"],
        "expect": 0,
        "files": ["__SAMPLE__"],
    },
    "untell-compare": {"argv": ["--n", "1", "--tier", "lite"], "expect": 0, "slow": True},
    "untell-mcp": {"argv": [], "expect": 0, "stdin_closed": True, "silent_ok": True},
    # The audit's exit code IS its verdict: 0 = every claim checks out, 1 = findings
    # reported (currently FAIL on stale doc counts — docs/why-best-open-repo.md and
    # docs/humanizer-census.md — queued for the human's `untell-audit --fix-counts`).
    "untell-audit": {"argv": [], "expect": (0, 1), "slow": True},
    "untell-latex": {"argv": ["__TEX__"], "expect": 0, "files": ["__TEX__"]},
    "untell-ceiling": {
        "argv": ["--n", "1", "--max-iters", "1", "--tier", "lite", "--rewriter", "composite", "--best-of", "1"],
        "expect": 0,
        "slow": True,
    },
    "untell-detector-audit": {"argv": [], "expect": 0, "slow": True},
    "untell-distill": {
        "argv": ["--n", "1", "--tier", "lite", "--best-of", "1", "--out", "__OUT__"],
        "expect": 0,
        "files": ["__OUT__"],
        "slow": True,
    },
    "untell-surrogate": {"argv": ["--smoke", "--out", "__OUT__"], "expect": 0, "files": ["__OUT__"], "slow": True},
    "untell-eval-policy": {
        "argv": [],
        "expect": 2,  # no trained policy in this environment: the documented clean refusal
    },
    "untell-server": {"argv": ["--port", "__PORT__"], "expect": "startup", "server": True},
    "untell-humanness": {"argv": [TEXT, "--tier", "lite"], "expect": 0},
    "untell-scrub": {"argv": [TEXT], "expect": 0},
    "untell-numbers": {
        "argv": ["There were 3 cats and 2 dogs.", "There were three cats and two dogs."],
        "expect": 0,
    },
    "untell-hedges": {"argv": ["It may be possible.", "It might be possible."], "expect": 0},
    "untell-explain": {"argv": [TEXT], "expect": 0},
    "untell-batch": {"argv": ["__DIR__", "--dry-run", "--tier", "lite"], "expect": 0, "files": ["__DIR__"]},
    # watch is a long-running loop; a bounded invocation is the documented clean run.
    "untell-watch": {"argv": ["__DIR__", "--timeout", "2", "--poll-interval", "0.1", "--tier", "lite"], "expect": 0, "files": ["__DIR__"]},
}

# Commands whose no-args invocation is a documented VALID run (not a missing-argument
# error): the dispatcher runs the demo, daemons bind, eval scripts run their default
# workload. Their "missing required args" contract is covered by their minimal check.
NO_REQUIRED_ARGS = {
    "untell", "untell-compare", "untell-mcp", "untell-audit", "untell-ceiling",
    "untell-detector-audit", "untell-distill", "untell-surrogate", "untell-server",
}


def _run(target: str, argv: list[str], *, timeout: int, stdin_closed: bool = False) -> subprocess.CompletedProcess:
    module, _, fn = target.partition(":")
    code = f"import {module} as m; raise SystemExit(m.{fn}({argv!r}))"
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    # Subprocesses must not write .pyc files: killed subprocesses on Windows can leave
    # half-written bytecode that a later import trips over (observed during this slice's
    # probing — transient rc=1 import failures after timed-out kills).
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["UNTELL_LITE_NO_TORCH"] = "1"
    stdin = subprocess.DEVNULL if stdin_closed else None
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, env=env, timeout=timeout, stdin=stdin,
    )


# Entry points that share one main() and therefore one parser prog. `untell-humanize` is the
# PRIMARY name (pyproject.toml comment; README), `untell-loop` its alias — so the loop's help
# names the primary, and both forms must accept either name in the usage line.
ALIASES: dict[str, set[str]] = {
    "untell-loop": {"untell-humanize"},
    "untell-humanize": {"untell-loop"},
}


@pytest.mark.parametrize("script", sorted(_console_scripts()))
def test_help_exits_zero_and_names_the_command(script):
    target = _console_scripts()[script]
    p = _run(target, ["--help"], timeout=30)
    assert p.returncode == 0, (
        f"{script} --help exited {p.returncode}:\n{p.stdout[:500]}\n{p.stderr[:500]}"
    )
    names = {script} | ALIASES.get(script, set())
    assert any(n in (p.stdout + p.stderr) for n in names), (
        f"{script} --help output does not name the command (or its alias):\n{p.stdout[:500]}"
    )


@pytest.mark.parametrize("script", sorted(_console_scripts()))
def test_unknown_flag_exits_two_with_a_message(script):
    target = _console_scripts()[script]
    p = _run(target, ["--definitely-not-a-real-flag-xyz"], timeout=60)
    assert p.returncode == 2, (
        f"{script} accepted an unknown flag (rc={p.returncode}):\n{p.stdout[:300]}\n{p.stderr[:300]}"
    )
    assert (p.stdout + p.stderr).strip(), f"{script}: unknown flag produced no message"


@pytest.mark.parametrize("script", sorted(_console_scripts()))
def test_missing_required_args_exit_two_with_a_message(script):
    if script in NO_REQUIRED_ARGS:
        pytest.skip(f"{script} has no required arguments — no-args is a documented valid run")
    target = _console_scripts()[script]
    p = _run(target, [], timeout=30)
    assert p.returncode == 2, (
        f"{script} with no args exited {p.returncode} (expected 2):\n"
        f"{p.stdout[:300]}\n{p.stderr[:300]}"
    )
    assert (p.stdout + p.stderr).strip(), f"{script}: no-args produced no message"


def _make_files(script: str, argv: list[str]) -> list[str]:
    """Materialise temp files for placeholders in the minimal invocation."""
    tmp = Path(tempfile.mkdtemp(prefix=f"cli_matrix_{script}_"))
    out = []
    for _, arg in enumerate(argv):
        if arg == "__SAMPLE__":
            f = tmp / "sample.txt"
            f.write_text(
                "I walk to work every morning and enjoy the quiet streets. "
                "Coffee first, then the news, then the day begins. " * 4,
                encoding="utf-8",
            )
            out.append(str(f))
        elif arg == "__TEX__":
            f = tmp / "paper.tex"
            f.write_text(
                "\\documentclass{article}\n\\begin{document}\n"
                "As shown by Smith (2020), the effect holds \\citep{smith2020}.\n"
                "\\end{document}\n",
                encoding="utf-8",
            )
            out.append(str(f))
        elif arg == "__OUT__":
            out.append(str(tmp / "out.jsonl"))
        elif arg == "__DIR__":
            d = tmp / "tree"
            d.mkdir()
            (d / "a.txt").write_text(
                "This is a plain sentence about nothing at all.\n", encoding="utf-8"
            )
            out.append(str(d))
        elif arg == "__PORT__":
            out.append("0")
        else:
            out.append(arg)
    return out


@pytest.mark.parametrize("script", sorted(s for s, spec in MINIMAL.items() if not spec.get("slow")))
def test_minimal_valid_invocation(script):
    _assert_minimal(script)


@pytest.mark.slow
@pytest.mark.parametrize("script", sorted(s for s, spec in MINIMAL.items() if spec.get("slow")))
def test_minimal_valid_invocation_slow(script):
    _assert_minimal(script)


def _assert_minimal(script: str) -> None:
    spec = MINIMAL[script]
    argv = _make_files(script, list(spec["argv"]))
    target = _console_scripts()[script]
    timeout = 420 if spec.get("slow") else 60

    if spec.get("server"):
        # The server never exits: assert it STARTS (binds and prints the banner), then stop it.
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["UNTELL_LITE_NO_TORCH"] = "1"
        code = f"import {target.partition(':')[0]} as m; raise SystemExit(m.main({argv!r}))"
        proc = subprocess.Popen(
            [sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, env=env,
        )
        try:
            startup = ""
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                startup += line
                if "Uvicorn running" in line:
                    break
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
        assert "Uvicorn running" in startup, f"{script} did not reach its startup banner:\n{startup[:800]}"
        return

    p = _run(target, argv, timeout=timeout, stdin_closed=spec.get("stdin_closed", False))
    assert p.returncode == spec["expect"] or (
        isinstance(spec["expect"], tuple) and p.returncode in spec["expect"]
    ), (
        f"{script} minimal invocation exited {p.returncode} (expected {spec['expect']}):\n"
        f"{p.stdout[:600]}\n{p.stderr[:600]}"
    )
    if not spec.get("silent_ok"):
        assert (p.stdout or p.stderr).strip(), f"{script}: minimal invocation produced no output"


def test_every_console_script_has_a_matrix_entry():
    """The matrix must cover every script in pyproject.toml — a new entry point that
    ships without a minimal-invocation contract would be invisible to this file."""
    missing = [s for s in _console_scripts() if s not in MINIMAL]
    assert not missing, f"console scripts with no minimal-invocation spec: {missing}"
