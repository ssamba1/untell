"""`UNTELL_PORT=abc` crashed the server before argparse could do anything.

The default was `int(os.environ.get("UNTELL_PORT", "8000"))`, evaluated while BUILDING the parser.
A bad value therefore raised while constructing the arguments, so nothing worked — including the
`--help` that would have shown the `--port` flag overriding it:

    $ UNTELL_PORT=abc untell-server --help
    ValueError: invalid literal for int() with base 10: 'abc'

A raw traceback for a mistyped environment variable, and no route to the answer. `--port` on the
command line has always been fine; argparse validates its own `type=int`.

The RANGE is checked too. 0 and 70000 parse as integers and fail later inside uvicorn, where the
message is about sockets rather than about the variable the user set.

    UNTELL_PORT=abc     error: UNTELL_PORT must be a whole number, got 'abc'.       exit 2
    UNTELL_PORT=0       error: UNTELL_PORT must be between 1 and 65535, got 0.      exit 2
    UNTELL_PORT=70000   error: UNTELL_PORT must be between 1 and 65535, got 70000.  exit 2
    UNTELL_PORT=8123    (starts normally)                                           exit 0
    UNTELL_PORT unset   (starts normally on 8000)                                   exit 0

One correction on the way: the first version raised `SystemExit("error: ...")`, which prints the
message and exits **1** — measured. 1 is the code this repo reserves for "ran, and the verdict was
no"; a configuration problem is 2. Printed to stderr and `SystemExit(2)` explicitly.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

_ROOT = Path(__file__).resolve().parents[1]

# `--help` makes the process exit before uvicorn binds anything, so these never open a socket.
_PROBE = (
    "import sys; sys.argv=['untell-server','--help']\n"
    "import untell.api_server as m\n"
    "m.main()\n"
)


def _run_with_port(value: str | None) -> tuple[int, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.pop("UNTELL_PORT", None)
    if value is not None:
        env["UNTELL_PORT"] = value
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True, text=True, env=env, cwd=str(_ROOT), timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


@pytest.mark.parametrize("value", ["abc", "8000.5", "", " "])
def test_a_non_numeric_port_is_reported(value: str) -> None:
    code, output = _run_with_port(value)
    if value.strip() == "":
        # Empty means "not set" — falling back to the default is right, not an error.
        assert code == 0, f"an empty UNTELL_PORT should fall back to the default: {output[-200:]}"
        return
    assert "Traceback" not in output, f"UNTELL_PORT={value!r} still crashes:\n{output[-400:]}"
    assert code == 2, f"UNTELL_PORT={value!r} exited {code}, expected 2"
    assert "UNTELL_PORT" in output and "whole number" in output


@pytest.mark.parametrize("value", ["0", "-1", "70000", "99999"])
def test_an_out_of_range_port_is_reported(value: str) -> None:
    """These parse as integers and would otherwise fail inside uvicorn, where the message is about
    sockets rather than about the variable the user set."""
    code, output = _run_with_port(value)
    assert "Traceback" not in output, output[-400:]
    assert code == 2, f"UNTELL_PORT={value} exited {code}, expected 2"
    assert "between 1 and 65535" in output


@pytest.mark.parametrize("value", ["8123", "1", "65535", None])
def test_a_valid_port_still_starts(value: str | None) -> None:
    """Guards every case above. A guard that rejected everything would satisfy them all."""
    code, output = _run_with_port(value)
    assert code == 0, f"UNTELL_PORT={value!r} was rejected: {output[-300:]}"
    assert "usage: untell-server" in output


def test_the_help_text_still_names_the_override() -> None:
    """The reason the crash mattered: `--help` was the route to the fix and it was unreachable."""
    code, output = _run_with_port("abc")
    assert code == 2
    # The failure message itself has to carry the route, since --help cannot run.
    assert "--port" in output, f"no override mentioned: {output[-200:]!r}"
