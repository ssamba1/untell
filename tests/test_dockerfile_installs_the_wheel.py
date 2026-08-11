"""The Dockerfile's install line has to survive shell globbing.

It shipped as:

    RUN pip install --no-cache-dir /tmp/untell-*.whl[server] && rm /tmp/untell-*.whl

`[server]` is a glob CHARACTER CLASS to the shell, not pip's extras syntax. The word only expands
if some file matches `untell-*.whl` followed by one of s/e/r/v — and no wheel is, because a wheel
filename ends at `.whl`. So the pattern never matches, POSIX shells pass the literal string
through, and pip fails:

    ERROR: untell-*.whl is not a valid wheel filename.

Verified by running that exact argument through pip. No CI job builds this image, which is why it
was never caught — so this file is the check that the shipped recipe is at least shaped correctly.
Building the image in CI would be better and is a separate piece of work.
"""

from __future__ import annotations

import pathlib
import re

_DOCKERFILE = pathlib.Path("Dockerfile").read_text(encoding="utf-8")


def test_extras_are_never_appended_to_an_unexpanded_glob() -> None:
    """`*.whl[extras]` in one word is the bug. The glob must be expanded first."""
    # Instruction lines only. The comment above the fix quotes the broken form deliberately, and
    # a check that cannot tell an example from an instruction would forbid documenting the bug.
    offenders = [
        ln.strip()
        for ln in _DOCKERFILE.splitlines()
        if not ln.lstrip().startswith("#") and re.search(r"\*[^\s]*\.whl\[", ln)
    ]
    assert not offenders, (
        f"a shell glob with extras appended never expands: {offenders}"
    )


def test_the_wheel_is_installed_with_the_server_extra() -> None:
    """The image serves the REST API, so the extra is the point of the line."""
    assert "[server]" in _DOCKERFILE, "the server extra is no longer installed"


def test_the_install_uses_an_expanded_path() -> None:
    """Whatever form it takes, the path pip receives must be a real filename."""
    assert re.search(r'\$\(ls /tmp/untell-\*\.whl\)|WHEEL=', _DOCKERFILE), (
        "the wheel path is no longer expanded before use"
    )


def test_the_temporary_wheel_is_cleaned_up() -> None:
    assert "rm /tmp/untell-*.whl" in _DOCKERFILE
