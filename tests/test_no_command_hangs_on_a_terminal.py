"""Six commands hung when run with no argument at an interactive terminal.

`sys.stdin.read()` on a TTY blocks until the user sends EOF, and none of these commands prints a
prompt first. So `untell tells` typed with no argument produced no output, no error and no cursor
movement — it looked hung, when the answer wanted was the usage line. Every one of them documents
stdin as an input source in its own `--help`, so the user has no way to tell "waiting for you" from
"crashed".

FOUND by reading: `scrub.py` guards with `if not sys.stdin.isatty()` and nothing else did.
CONFIRMED by modelling a terminal — isatty() True, read() raising instead of blocking, so a call is
visible rather than fatal:

    run score tells verify sentences preserve   -> blocked in read()
    scrub                                       -> returned 2

A pipe cannot show this. `sleep 6 | untell tells` times out on all seven, because a pipe with no
data is exactly what the guard is meant to READ. Only isatty separates them, so only isatty can
test them.

All seven now return 2 — nothing ran, which is a configuration problem rather than a verdict about
any text, matching the exit-code convention the rest of these commands use.
"""

from __future__ import annotations

import io
import sys

import pytest

COMMANDS = ["run", "score", "tells", "verify", "sentences", "preserve", "scrub"]

PIPED = "Moreover, the framework leverages robust methodologies to deliver outcomes today."


class _Terminal(io.TextIOBase):
    """A stdin that says it is a terminal and refuses to block."""

    def isatty(self) -> bool:
        return True

    def read(self, *args, **kwargs):
        raise AssertionError(
            "read() called on a terminal: this blocks until the user sends EOF, with no prompt"
        )


class _Pipe(io.StringIO):
    def isatty(self) -> bool:
        return False


def _main_of(name: str):
    return __import__(f"untell.scripts.{name}", fromlist=["main"]).main


@pytest.mark.parametrize("name", COMMANDS)
def test_no_argument_at_a_terminal_returns_instead_of_blocking(name: str, monkeypatch) -> None:
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    monkeypatch.setattr(sys, "stdin", _Terminal())
    assert _main_of(name)([]) == 2


@pytest.mark.parametrize("name", COMMANDS)
def test_piped_input_is_still_read(name: str, monkeypatch, capsys) -> None:
    """Guards the guard. A command that stopped reading stdin altogether would pass the test above
    while breaking `cat doc.txt | untell tells`, which its own --help advertises."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    monkeypatch.setattr(sys, "stdin", _Pipe(PIPED))
    argv = ["--tier", "lite"] if name in ("run", "score", "verify", "sentences") else []
    if name == "run":
        argv += ["--max-iters", "1", "--rewriter", "surgical", "--best-of", "1"]

    rc = _main_of(name)(argv)
    assert rc != 2, f"{name} rejected piped input: {capsys.readouterr().out[:200]}"


def test_a_replaced_stream_without_isatty_is_treated_as_piped() -> None:
    """The helper must not turn a captured stream into a terminal. Test harnesses and some
    embedding contexts replace stdin with an object lacking `isatty`, and treating that as
    interactive would make every command in them return 2 with nothing read."""
    from untell.scripts.io_utils import read_stdin_or_none

    class Bare:
        def read(self, *args, **kwargs):
            return "piped text"

    real = sys.stdin
    sys.stdin = Bare()  # type: ignore[assignment]
    try:
        assert read_stdin_or_none() == "piped text"
    finally:
        sys.stdin = real
