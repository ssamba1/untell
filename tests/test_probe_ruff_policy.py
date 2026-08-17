"""The .claude/probes/ ruff exemption policy is complete and drift-proof.

Probe scripts are exempted from ruff by EXPLICIT policy, not by accident:
[tool.ruff.lint.per-file-ignores] in pyproject.toml ignores all rules for
".claude/probes/*.py" (rationale: .claude/probes/RUFF-POLICY.md). These tests
assert the policy lists every exempted file, so a probe dropped outside the
pattern — or a pattern that stops matching anything — fails the build.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PROBES_DIR = REPO_ROOT / ".claude" / "probes"
PYPROJECT = REPO_ROOT / "pyproject.toml"
POLICY_DOC = PROBES_DIR / "RUFF-POLICY.md"
EXEMPTION_PATTERN = ".claude/probes/*.py"

try:  # Python >= 3.11
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - 3.9/3.10 CI path
    tomllib = None

_STANZA_RE = re.compile(
    r"\[tool\.ruff\.lint\.per-file-ignores\](?P<body>.*?)(?=\n\[|\Z)", re.DOTALL
)
_PATTERN_RE = re.compile(r'"([^"]+)"\s*=\s*\[([^\]]*)\]')


def _per_file_ignores() -> dict[str, list[str]]:
    """The per-file-ignores table from pyproject.toml.

    tomllib on 3.11+; a small regex parse of the single stanza we control on
    3.9/3.10 (tomllib does not exist there and tomli is not a declared dep).
    """
    if tomllib is not None:
        with PYPROJECT.open("rb") as fh:
            data = tomllib.load(fh)
        return dict(data["tool"]["ruff"]["lint"]["per-file-ignores"])
    text = PYPROJECT.read_text(encoding="utf-8")  # pragma: no cover
    m = _STANZA_RE.search(text)  # pragma: no cover
    assert m, "per-file-ignores stanza missing from pyproject.toml"  # pragma: no cover
    return {  # pragma: no cover
        pat: [r.strip() for r in rules.split(",") if r.strip()]
        for pat, rules in _PATTERN_RE.findall(m.group("body"))
    }


def _expand(pattern: str) -> set[Path]:
    """Files matched by a per-file-ignore pattern, relative to the repo root.

    ruff matches patterns against paths relative to the project root with glob
    semantics; Path.glob on the same pattern is the closest stdlib equivalent.
    """
    return set(REPO_ROOT.glob(pattern))


def test_policy_doc_exists_and_names_the_exemption() -> None:
    assert POLICY_DOC.is_file(), "missing .claude/probes/RUFF-POLICY.md (the documented policy)"
    text = POLICY_DOC.read_text(encoding="utf-8")
    assert EXEMPTION_PATTERN in text, "policy doc must name the exemption pattern"
    assert "per-file-ignores" in text, "policy doc must reference the ruff mechanism"


def test_every_probe_file_is_covered_by_the_exemption_policy() -> None:
    ignores = _per_file_ignores()
    patterns = list(ignores)
    assert patterns, "no [tool.ruff.lint.per-file-ignores] policy in pyproject.toml"

    covered: set[Path] = set()
    for pat in patterns:
        covered |= _expand(pat)

    # The policy must list every exempted file: any probe *.py outside the patterns
    # is unexempted debt that would silently fail `ruff check .`.
    probe_files = set(PROBES_DIR.glob("*.py"))
    missing = sorted(probe_files - covered)
    assert not missing, (
        f"{len(missing)} probe file(s) are NOT covered by the ruff exemption policy: "
        + ", ".join(str(p.relative_to(REPO_ROOT)) for p in missing[:10])
        + (f" (+{len(missing) - 10} more)" if len(missing) > 10 else "")
    )

    # And no pattern may be dead: a listed pattern that matches nothing is drift.
    for pat in patterns:
        assert _expand(pat), f"per-file-ignore pattern {pat!r} matches no files (policy drift)"


def test_ruff_check_passes_on_the_whole_tree_including_probes() -> None:
    """End-to-end: with the exemption policy in place, `ruff check .` exits 0.

    This is the exact command CI's ruff job runs. It fails if a probe file escaped
    the policy (not matched by any pattern) or new lint errors appeared in shipped
    code — the two ways this issue's debt can come back.

    ruff is a dev-extra dependency, so it is always present in CI (lite/full jobs
    install ``[dev]``; the dedicated ruff job installs it directly); on a machine
    that lacks it the check is skipped at runtime rather than marked (the repo's
    convention for environmental prerequisites — see ``pytest.importorskip`` in
    tests/test_server_soak.py).
    """
    ruff = shutil.which("ruff")
    if ruff is None:
        pytest.skip("ruff not installed (dev extra); the CI ruff job runs this check")
    proc = subprocess.run(
        [ruff, "check", "."],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"`ruff check .` failed (exit {proc.returncode}):\n"
        f"{proc.stdout[-3000:]}\n{proc.stderr[-1000:]}"
    )
