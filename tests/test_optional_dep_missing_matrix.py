"""Optional-dependency absence matrix (issue #36).

Every optional extra (peft, sacremoses, nltk, torch, spacy, fastapi) must fail
cleanly — a message or a documented no-op, never a traceback — when that
dependency is absent. This is the *class* of defect issue #36 tracks; the known
cases are peft (local-policy rewriter, partly fixed in wave-5 #34), sacremoses
(transitive, would surface only through a transformers load), nltk (WordNet in
word_importance), torch (every model-backed detector/rewriter), spacy (NER
locking + predicate-argument veto), and fastapi (the REST server).

The absence is simulated by a :class:`MetaPathFinder` installed ahead of ``sys``
that raises ``ModuleNotFoundError`` for the dep and its submodules — no real
uninstall, so a machine with the extras installed still exercises the exact
"dep absent" code path. Each surface runs in its own subprocess so the blocker
holds for the whole run and cannot leak into another case.

Acceptance (from the issue): every optional dep, run the surface with the dep
absent -> clean message + documented exit code, no traceback.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

# The blocker, run first inside every subprocess. It must be installed before
# any import of the dep. Raising ModuleNotFoundError (not ImportError) is what a
# genuinely missing package does, and several guards distinguish the two
# (api_server catches exactly ModuleNotFoundError on the named import).
_BLOCKER = """
import sys, importlib.abc
class _B(importlib.abc.MetaPathFinder):
    def __init__(self, mod): self.mod = mod
    def find_spec(self, name, path=None, target=None):
        if name == self.mod or name.startswith(self.mod + "."):
            raise ModuleNotFoundError("No module named %r" % name, name=name)
        return None
def _block(mod):
    sys.meta_path.insert(0, _B(mod))
"""

# Case 1 — peft: the local-policy rewriter must name peft + `.[train]`, return
# a reason, and raise a clean RuntimeError (never a ModuleNotFoundError five
# imports deep). Wave-5 #34 fixed this; it is pinned here so it stays fixed.
PEFT_SURFACE = """
from untell.rewriter.local_policy import LocalPolicyRewriter
import os, tempfile
# A dir that exists but no adapter inside: the dir check passes so the peft
# absence is what must be named.
os.environ["UNTELL_POLICY_DIR"] = tempfile.mkdtemp()
lp = LocalPolicyRewriter()
reason = lp.unavailable_reason()
print("REASON:", reason)
print("AVAIL:", lp.available())
try:
    lp._load()
    print("LOADED-UNEXPECTED")
except RuntimeError as e:
    print("RUNTIMEERROR:", e)
"""

# Case 2 — nltk: word_importance's WordNet probe must return a cached None and
# `synonyms()` must still return the built-in table for words it has, without
# raising.
NLTK_SURFACE = """
from untell.attacks.word_importance import _wordnet, synonyms
print("WORDNET:", _wordnet())
print("UTILIZE:", synonyms("utilize"))
print("IMPORTANT:", synonyms("important"))
"""

# Case 3 — torch: model-backed detectors report unavailable and rewriters are a
# documented no-op (return the input), never a traceback.
TORCH_SURFACE = """
from untell.rewriter.t5_paraphrase import T5ParaphraseRewriter
from untell.attacks.back_translation import BackTranslator
rw = T5ParaphraseRewriter()
print("T5_AVAIL:", rw.available())
print("T5_REWRITE:", rw.rewrite("This is a test sentence.", {}, 0.3))
bt = BackTranslator()
print("BT_AVAIL:", bt.available())
"""

# Case 4 — spacy: NER locking degrades to no entities and the predicate-argument
# veto degrades to "unknown" (None), each with a one-time warning; never a crash.
SPACY_SURFACE = """
from untell.scripts.preserve import lock
from untell.scripts import roles
import logging; logging.basicConfig(level=logging.WARNING)
out = lock("Apple hired John Smith in Paris.")
print("LOCK_TEXT:", out[0])
print("LOCK_SPANS:", out[1])
print("ROLES_AVAIL:", roles.parser_available())
print("ROLES_SWAP:", roles.role_swap("The cat chased the dog", "The dog chased the cat"))
"""

# Case 5 — fastapi: importing the REST server module raises a clean ImportError
# that names the extra, never a bare ModuleNotFoundError traceback.
FASTAPI_SURFACE = """
try:
    import untell.api_server as _m  # noqa: F401
    print("IMPORTED-UNEXPECTED")
except ImportError as e:
    print("IMPORTERROR:", e)
"""

# Case 6 — sacremoses: not imported anywhere in project code (verified by grep
# of the source tree); it is transitive through transformers tokenizers. The
# surface that *would* load it is a transformers-backed rewriter, which is
# already torch-gated (case 3). So the correct matrix entry for sacremoses is:
# absence is inert — the package imports and the CLI runs unchanged. This test
# blocks it and proves nothing observes it.
SACREMOSES_SURFACE = """
import untell
from untell.scripts.cli import _run_check
_rc = _run_check()
print("CHECK_RC:", _rc)
"""

# dep -> (surface source, env overrides)
CASES: dict[str, tuple[str, dict[str, str] | None]] = {
    "peft": (PEFT_SURFACE, {"UNTELL_LITE_NO_TORCH": "1"}),
    "nltk": (NLTK_SURFACE, {"UNTELL_LITE_NO_TORCH": "1"}),
    "torch": (TORCH_SURFACE, {"UNTELL_LITE_NO_TORCH": "1"}),
    "spacy": (SPACY_SURFACE, {"UNTELL_LITE_NO_TORCH": "1"}),
    "fastapi": (FASTAPI_SURFACE, None),
    "sacremoses": (SACREMOSES_SURFACE, None),
}


def _run_blocked(dep: str, surface: str, env_extra: dict[str, str] | None) -> tuple[int, str]:
    code = _BLOCKER + f"_block({dep!r})\n" + surface
    env = {**__import__("os").environ}
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, env=env, cwd=str(_ROOT), timeout=600,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output


@pytest.fixture(scope="module", params=sorted(CASES))
def blocked_result(request) -> tuple[str, int, str]:
    """Run one dep's surface once per module, cached, so the parametrised base
    contract and the dedicated per-dep assertions share a single subprocess
    instead of each spawning an expensive one (peft/sacremoses run heavy
    surfaces). Returns ``(dep, rc, output)``."""
    dep = request.param
    surface, env = CASES[dep]
    rc, output = _run_blocked(dep, surface, env)
    return dep, rc, output


# --- base contract: no traceback, exit 0 (clean refusal / no-op) ----------------
def test_optional_dep_absent_fails_cleanly_without_traceback(blocked_result) -> None:
    dep, rc, output = blocked_result
    assert "Traceback" not in output, f"{dep}: printed a traceback:\n{output[-500:]}"
    assert rc == 0, f"{dep}: exited {rc}, expected 0 (clean refusal / no-op):\n{output[-500:]}"


# --- per-dep documented outcomes --------------------------------------------------
def test_peft_absence_names_package_and_extra(blocked_result) -> None:
    dep, rc, output = blocked_result
    if dep != "peft":
        return
    assert "needs the 'peft' package" in output, output[-500:]
    assert "untell[train]" in output, output[-500:]
    assert "RUNTIMEERROR:" in output and "LOADED-UNEXPECTED" not in output, output[-500:]


def test_nltk_absence_is_a_cached_noop(blocked_result) -> None:
    dep, _rc, output = blocked_result
    if dep != "nltk":
        return
    assert "WORDNET: None" in output, output[-500:]
    assert "UTILIZE: ['use']" in output, output[-500:]


def test_torch_absence_is_a_documented_noop(blocked_result) -> None:
    dep, _rc, output = blocked_result
    if dep != "torch":
        return
    assert "T5_AVAIL: False" in output, output[-500:]
    assert "T5_REWRITE: This is a test sentence." in output, output[-500:]
    assert "BT_AVAIL: False" in output, output[-500:]


def test_spacy_absence_degrades_without_entities(blocked_result) -> None:
    dep, _rc, output = blocked_result
    if dep != "spacy":
        return
    # No entities locked (spacy absent means no NER), roles veto unavailable.
    assert "LOCK_SPANS: {}" in output, output[-500:]
    assert "ROLES_AVAIL: False" in output, output[-500:]
    assert "ROLES_SWAP: None" in output, output[-500:]


def test_fastapi_absence_raises_clean_import_error(blocked_result) -> None:
    dep, _rc, output = blocked_result
    if dep != "fastapi":
        return
    assert "IMPORTERROR:" in output, output[-500:]
    assert "untell[server]" in output, output[-500:]
    assert "IMPORTED-UNEXPECTED" not in output, output[-500:]


def test_sacremoses_absence_is_inert(blocked_result) -> None:
    """sacremoses has no direct import surface in project code; blocking it must
    leave the CLI (which would transitively touch it only via a transformers
    load) running unchanged."""
    dep, rc, output = blocked_result
    if dep != "sacremoses":
        return
    assert "CHECK_RC: 0" in output, output[-500:]
    assert rc == 0
