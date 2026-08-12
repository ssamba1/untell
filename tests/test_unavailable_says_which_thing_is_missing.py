"""An error has to name the thing to DO, not just report that something is wrong.

Two surfaces failed that bar in the same way — reporting a symptom shared by several causes.

`untell_text(rewriter="anthropic")` with the SDK installed and the key unset answered "rewriter
'anthropic' is not available — check the name". The name was correct; the key was missing. A typo
and an unset environment variable produced identical advice, and one of them told the user to fix
something that was not broken.

`untell-server` is a console script pointing at `main` in `untell.api_server`, so the module
imports before `main` can print anything. On a base install that surfaced as a bare
`ModuleNotFoundError: No module named 'fastapi'` with a traceback, naming neither the extra nor
the fact that everything else works without it.

The bar comes from this repo: `io_utils` says "reading it needs python-docx: pip install
'untell[docs]'" — the package AND the extra.
"""

from __future__ import annotations

import builtins
import sys

import pytest

from untell.scripts.run import _HOSTED_REQUIREMENTS, _unavailable_reason


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch: pytest.MonkeyPatch):
    for env_var, _module, _extra in _HOSTED_REQUIREMENTS.values():
        monkeypatch.delenv(env_var, raising=False)


@pytest.mark.parametrize("name", sorted(_HOSTED_REQUIREMENTS))
def test_a_missing_key_is_not_reported_as_a_bad_name(name: str):
    reason = _unavailable_reason(name)
    env_var = _HOSTED_REQUIREMENTS[name][0]
    assert env_var in reason, reason
    assert "check the name" not in reason, "the name is correct; only the key is missing"


@pytest.mark.parametrize("name", sorted(_HOSTED_REQUIREMENTS))
def test_it_names_the_extra_not_just_the_package(name: str):
    _env_var, module, extra = _HOSTED_REQUIREMENTS[name]
    reason = _unavailable_reason(name)
    assert module in reason and extra in reason, reason


def test_a_key_that_is_set_changes_the_advice(monkeypatch: pytest.MonkeyPatch):
    """Set the key and the message must stop telling the user to set it."""
    env_var, module, _extra = _HOSTED_REQUIREMENTS["anthropic"]
    monkeypatch.setenv(env_var, "sk-test")
    reason = _unavailable_reason("anthropic")
    assert f"{env_var} is not set" not in reason, reason
    assert module in reason, "with the key set, the SDK is the remaining thing to install"


def test_an_unknown_name_still_says_check_the_name():
    """Guards the guard: the specific advice must not swallow the generic case."""
    reason = _unavailable_reason("no_such_backend")
    assert "check the name" in reason
    assert "API_KEY" not in reason, "there is no key to suggest for a name that does not exist"


def test_the_server_import_names_its_extra(monkeypatch: pytest.MonkeyPatch):
    """A base install must be told which extra supplies FastAPI, and that nothing else needs it."""
    real_import = builtins.__import__

    def without_fastapi(name, *args, **kwargs):
        if name == "fastapi" or name.startswith("fastapi."):
            raise ModuleNotFoundError(f"No module named '{name}'")
        return real_import(name, *args, **kwargs)

    for module in [m for m in list(sys.modules) if m.startswith(("untell.api_server", "fastapi"))]:
        monkeypatch.delitem(sys.modules, module, raising=False)
    monkeypatch.setattr(builtins, "__import__", without_fastapi)

    with pytest.raises(ImportError) as caught:
        import untell.api_server  # noqa: F401

    message = str(caught.value)
    assert "untell[server]" in message, message
    assert "CLI" in message, "say that the rest of the tool works without it"


def test_the_server_import_error_is_not_a_systemexit(monkeypatch: pytest.MonkeyPatch):
    """A library caller importing this module gets the exception their `try` expects — a
    `SystemExit` would take their process down instead."""
    real_import = builtins.__import__

    def without_fastapi(name, *args, **kwargs):
        if name == "fastapi" or name.startswith("fastapi."):
            raise ModuleNotFoundError(f"No module named '{name}'")
        return real_import(name, *args, **kwargs)

    for module in [m for m in list(sys.modules) if m.startswith(("untell.api_server", "fastapi"))]:
        monkeypatch.delitem(sys.modules, module, raising=False)
    monkeypatch.setattr(builtins, "__import__", without_fastapi)

    try:
        import untell.api_server  # noqa: F401
    except ImportError:
        pass
    except SystemExit:  # pragma: no cover - the regression this pins
        pytest.fail("importing the module must not raise SystemExit")
