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


def test_healthcheck_probes_the_unauthenticated_health_endpoint() -> None:
    """The image must health-check `/health` — the one endpoint auth and rate limiting exempt.

    A probe hitting a protected endpoint would 401 (and 429 at high frequency) itself into a
    restart loop the moment UNTELL_API_KEY is set at runtime; /health is the cheap exemption.
    urllib is stdlib: `curl` is not in python:3.11-slim and the image installs only
    ca-certificates.
    """
    m = re.search(r"HEALTHCHECK\s+.*?CMD\s+(.*)$", _DOCKERFILE, re.M)
    assert m, "no HEALTHCHECK instruction in the Dockerfile"
    cmd = m.group(1).rstrip()
    assert "127.0.0.1:8000/health" in cmd, f"HEALTHCHECK does not probe /health: {cmd!r}"
    assert "timeout=3" in cmd, f"HEALTHCHECK lacks a timeout: {cmd!r}"


# --- .dockerignore must not strip the wheel's inputs -------------------------
# The builder stage is `COPY . .` then `python -m build`, so the build context IS the sdist
# input. It shipped ignoring `eval/`, `training/` and every `*.md`; the first made the build
# fail outright (`error: package directory 'eval' does not exist`) and the second silently
# produced a wheel with no SKILL.md, no references/, and an empty long description — the
# package data this repo's docs promise. Both verified by building from a context filtered
# exactly as the old ignore list filtered. Docker .dockerignore semantics: patterns apply in
# order, a later `!` pattern re-includes what an earlier one excluded.

_DOCKERIGNORE = pathlib.Path(".dockerignore").read_text(encoding="utf-8")


def _ignored_by_dockerignore(relpath: str) -> bool:
    import fnmatch

    ignored = False
    for raw in _DOCKERIGNORE.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negate = line.startswith("!")
        pat = line[1:].strip() if negate else line
        if fnmatch.fnmatch(relpath, pat) or fnmatch.fnmatch(relpath, pat.rstrip("/") + "/*"):
            ignored = not negate
    return ignored


def test_dockerignore_keeps_every_declared_package() -> None:
    """pyproject's package list must survive into the build context."""
    import re

    text = pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
    block = text[text.index("[tool.setuptools]") :]
    packages = re.findall(r'^\s*"([^"]+)"\s*,?$', block, re.M)
    assert len(packages) >= 6, packages
    for pkg in packages:
        assert not _ignored_by_dockerignore(pkg + "/__init__.py"), (
            f"package {pkg} is excluded from the docker build context; "
            f"`python -m build` inside the image cannot succeed"
        )


def test_dockerignore_keeps_readme_and_package_data() -> None:
    """The wheel must ship README (long description), SKILL.md and references/."""
    assert not _ignored_by_dockerignore("README.md"), (
        "README.md is pyproject's `readme`; dropping it empties the wheel's long description"
    )
    for rel in ("untell/SKILL.md", "untell/references/ai-tells.md", "untell/references/thresholds.md"):
        assert not _ignored_by_dockerignore(rel), (
            f"{rel} is package data; dropping it breaks what the docs promise in the wheel"
        )


def test_dockerignore_still_trims_the_context() -> None:
    """The ignore list is there to keep the context small — it must still exclude the fat."""
    for rel in ("docs/api-server.md", "tests/test_score.py", ".github/workflows/ci.yml"):
        assert _ignored_by_dockerignore(rel), f"{rel} should be trimmed from the docker context"
