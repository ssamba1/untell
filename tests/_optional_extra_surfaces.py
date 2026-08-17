"""Surface runner for the issue-#36 optional-extra guard matrix.

Spawned as a subprocess by ``test_optional_extra_matrix.py`` so each optional
dependency's surface is exercised with that dependency genuinely absent from
``sys.path`` (a meta_path finder that raises ``ModuleNotFoundError``), rather
than relying on what happens to be installed on the runner — the same trick
used to prove a package's absence without uninstalling it.

Why meta_path and not ``sys.modules[dep] = None``: several guards check
availability with ``importlib.util.find_spec`` / ``importlib.import_module``,
which do *not* consult ``sys.modules``. Stubbing ``None`` in ``sys.modules``
therefore leaves those guards believing the dep is present and lets the real
import leak through. A finder on ``sys.meta_path`` is consulted by both the
statement ``import x`` and by ``find_spec``, so it blocks every path a guard
could take.

Usage (from the test)::

    python _optional_extra_surfaces.py <BLOCKED_DEP> <SURFACE>

Writes the surface's own output to stdout and exits with the surface's exit
code. It deliberately never swallows an exception, so a genuine traceback
survives to stderr and the "no traceback" assertion can catch it.
"""

from __future__ import annotations

import importlib.abc
import os
import sys
import tempfile
from pathlib import Path

# Make `untell` importable from any cwd / CI checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_TINY_TEXT = "This is a plain sentence about nothing at all."


class _MissingDepFinder(importlib.abc.MetaPathFinder):
    """Raise ``ModuleNotFoundError`` for one module (and its submodules)."""

    def __init__(self, blocked: str) -> None:
        self._blocked = blocked

    def find_spec(self, fullname, path=None, target=None):
        if fullname == self._blocked or fullname.startswith(self._blocked + "."):
            raise ModuleNotFoundError(f"No module named '{self._blocked}'", name=self._blocked)
        return None


def _install_blocker(blocked: str) -> None:
    sys.meta_path.insert(0, _MissingDepFinder(blocked))


def _peft_cli() -> int:
    """`untell-humanize --rewriter local <text>` with peft absent → clean exit 2."""
    os.environ["UNTELL_POLICY_DIR"] = tempfile.mkdtemp(prefix="optdep_policy_")
    from untell.scripts.run import main

    return main(["--rewriter", "local", _TINY_TEXT])


def _peft_unavailable_reason() -> int:
    """The library guard: unavailable_reason() names the missing package + extra."""
    from untell.rewriter.local_policy import LocalPolicyRewriter

    rw = LocalPolicyRewriter(adapter_dir=tempfile.mkdtemp(prefix="optdep_policy_"))
    reason = rw.unavailable_reason()
    print("unavailable_reason:", reason)
    print("available:", rw.available())
    return 0


def _sacremoses_mtpivot() -> int:
    """mt_pivot (Marian round-trip MT): availability and a rewrite must not crash."""
    from untell.rewriter.mt_pivot import MTPivotRewriter

    rw = MTPivotRewriter()
    print("available:", rw.available())
    return 0


def _nltk_synonyms() -> int:
    """word_importance.synonyms falls back to the built-in map when nltk is absent."""
    from untell.attacks.word_importance import synonyms

    print("synonyms:", synonyms("commence"))
    return 0


def _torch_score() -> int:
    """score_text(tier='full') with torch absent reports an honest lite fallback."""
    from untell.scripts.score import score_text

    res = score_text(_TINY_TEXT, tier="full")
    print("reported_tier:", res.get("tier"))
    return 0


def _spacy_roles() -> int:
    """roles: predicate-argument veto degrades to unavailable/'unknown' — never a crash."""
    from untell.scripts.roles import available, role_swap

    print("roles.available:", available())
    print("role_swap:", role_swap("The cat chased the dog", "The dog chased the cat"))
    return 0


def _fastapi_check() -> int:
    """`untell check`: reports the REST server's missing extra cleanly."""
    from untell.scripts.cli import main

    return main(["--check"])


def _fastapi_server_cli() -> int:
    """`untell-server` (console shim): with FastAPI absent it exits 2 with a clean message."""
    from untell.api_server_cli import main

    return main([])


_SURFACES = {
    "peft_cli": _peft_cli,
    "peft_unavailable_reason": _peft_unavailable_reason,
    "sacremoses_mtpivot": _sacremoses_mtpivot,
    "nltk_synonyms": _nltk_synonyms,
    "torch_score": _torch_score,
    "spacy_roles": _spacy_roles,
    "fastapi_check": _fastapi_check,
    "fastapi_server_cli": _fastapi_server_cli,
}


def main() -> int:
    blocked, surface = sys.argv[1], sys.argv[2]
    _install_blocker(blocked)
    runner = _SURFACES[surface]
    return runner()


if __name__ == "__main__":
    sys.exit(main())
