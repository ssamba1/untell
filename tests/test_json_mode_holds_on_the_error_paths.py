"""`--json` held on the success path and broke on two error paths.

A caller that runs these commands and parses stdout cannot special-case one branch. Two places
answered in something other than JSON while `--json` was set:

  - `untell scrub --json` with no input logged to stderr and left stdout EMPTY, so
    `json.loads(subprocess.check_output(...))` raised JSONDecodeError. Every other JSON-emitting
    command answers `{"error": "no input: ..."}` there. MEASURED, no input, `--json`:

        humanize   {"error": "no input: pass text, --file PATH, or pipe to stdin"}   exit 2
        sentences  {"error": "no input: ..."}                                        exit 2
        tells      {"error": "no input: ..."}                                        exit 2
        scrub      (nothing on stdout)                                               exit 2

  - `untell humanize --json --detector-thresholds <not json>` printed `ERROR: ...` as plain text
    on stdout regardless of the flag — the one situation where the caller most needs to read what
    was wrong with their argument.

Both now emit `{"error": ...}` and keep exit 2.

NOT a defect, checked and dismissed: `untell score` does not accept `--json` at all — it always
emits JSON — so its argparse usage error on that flag is correct behaviour, not a broken contract.
A first pass over this recorded it as a third finding before reading the output rather than the
exit code.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

# Commands that take `--json` and can hit a no-input error path.
_JSON_COMMANDS = ["run", "sentences", "tells", "scrub"]


def _run(module: str, *args: str, stdin: str = "") -> tuple[int, str, str]:
    env = {**os.environ, "UNTELL_LITE_NO_TORCH": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-m", f"untell.scripts.{module}", *args],
        input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(_ROOT), timeout=300,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


class _Terminal(io.TextIOBase):
    """A stdin that says it is a terminal, so the NO-INPUT branch is the one under test.

    A pipe is the wrong instrument here and measuring that cost a wrong turn. With an empty pipe
    the commands do not take the no-input branch at all: `run`, `sentences` and `tells` see an
    empty string and answer "empty input", while `scrub` sees an empty string, scrubs it, and
    exits 0 — correctly, since scrubbing nothing is a well-defined answer. Only a terminal means
    "nothing was supplied".

    Worse, the two are not portable: `< /dev/null` under Git Bash on Windows reports isatty() TRUE,
    so a shell redirect exercised the terminal branch while a `subprocess(input="")` exercised the
    pipe branch, and the same command gave exit 2 and exit 0 in the two runs.
    """

    def isatty(self) -> bool:
        return True

    def read(self, *args, **kwargs):
        raise AssertionError("read() on a terminal blocks; the no-input branch should have fired")


@pytest.mark.parametrize("module", _JSON_COMMANDS)
def test_no_input_under_json_answers_json(module: str, monkeypatch, capsys) -> None:
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    monkeypatch.setattr(sys, "stdin", _Terminal())
    main = __import__(f"untell.scripts.{module}", fromlist=["main"]).main

    code = main(["--json"])
    out = capsys.readouterr().out

    assert code == 2, f"{module} returned {code}, expected 2"
    try:
        payload = json.loads(out)
    except json.JSONDecodeError as exc:
        pytest.fail(f"{module} --json emitted non-JSON on the no-input path: {out[:200]!r} ({exc})")
    assert "error" in payload, f"{module}: {payload!r}"
    assert "no input" in payload["error"], f"{module}: {payload['error']!r}"


def test_a_bad_detector_thresholds_value_answers_json() -> None:
    code, out, _err = _run(
        "run", "--json", "--detector-thresholds", "not-json", "some text here"
    )
    assert code == 2
    payload = json.loads(out)
    assert "detector-thresholds" in payload["error"]


def test_the_same_error_is_plain_text_without_the_flag() -> None:
    """Guards the fix. Emitting JSON unconditionally would be the other way to break the
    contract — a human running the command without `--json` should read a sentence."""
    code, out, err = _run("run", "--detector-thresholds", "not-json", "some text here")
    assert code == 2
    combined = out + err
    assert "detector-thresholds" in combined
    assert not combined.strip().startswith("{"), f"plain mode emitted JSON: {combined[:120]!r}"


@pytest.mark.parametrize("module", _JSON_COMMANDS)
def test_json_mode_still_works_on_the_success_path(module: str) -> None:
    """Guards the guard. A command that answered `{"error": ...}` to everything would satisfy the
    cases above while being useless."""
    args = ["--json", "Moreover, the framework leverages robust methodologies to deliver outcomes."]
    if module in ("run", "sentences"):
        args = ["--tier", "lite", *args]
    if module == "run":
        args = ["--max-iters", "1", "--best-of", "1", "--rewriter", "surgical", *args]

    code, out, err = _run(module, *args)
    assert code == 0, f"{module} exited {code}: {(out + err)[-250:]}"
    payload = json.loads(out)
    assert "error" not in payload, f"{module} reported an error on valid input: {payload!r}"
