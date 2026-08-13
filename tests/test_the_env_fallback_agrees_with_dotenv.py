"""An unclosed quote in `.env` put the quote inside the API key.

`load_env` has two parsers: python-dotenv when installed, and a zero-dependency fallback otherwise.
Which one runs depends only on an optional dependency, so any disagreement means the same file
configures the program two different ways — `_parse_value`'s docstring says exactly that, and
records eight line shapes compared, of which one diverged and was fixed.

This is a ninth. MEASURED with python-dotenv absent, so the fallback runs:

    UNCLOSED="sk-broken   ->   os.environ["UNCLOSED"] == '"sk-broken'

The leading quote is kept and travels into the value. python-dotenv, given the same file, sets the
key not at all. `.env` is the documented place for UNTELL_API_KEY and the provider keys, so that
quote reaches an auth header and the remote end answers about credentials rather than about
quoting, with nothing naming the .env file as the cause.

The fallback now skips the key, matching python-dotenv on the outcome, and logs why — which
python-dotenv does not. A silently absent key is what sends someone hunting through a provider
dashboard instead of their own file.

NOTE ON HOW THIS WAS FOUND. The audit that reported it measured `_parse_value` directly and
claimed the environment variable was set. It is not, on a machine with python-dotenv installed —
the fallback never runs there. The end-to-end claim only holds on the base install, which is the
path that matters and had to be forced to see it.
"""

from __future__ import annotations

import builtins
import logging
import os
from pathlib import Path

import pytest

from untell._env import _parse_value, load_env


@pytest.fixture
def no_dotenv(monkeypatch):
    """Force the zero-dependency fallback, which is what a base install uses."""
    real_import = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name == "dotenv":
            raise ImportError("forced: the base install has no python-dotenv")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)


def _write(tmp_path: Path, body: str) -> Path:
    target = tmp_path / ".env"
    target.write_text(body, encoding="utf-8")
    return target


def test_an_unclosed_quote_is_not_stored(tmp_path, monkeypatch, no_dotenv, caplog) -> None:
    env_file = _write(tmp_path, 'UNCLOSED="sk-broken\nGOOD="sk-real"\n')
    monkeypatch.delenv("UNCLOSED", raising=False)
    monkeypatch.delenv("GOOD", raising=False)

    with caplog.at_level(logging.WARNING):
        assert load_env(str(env_file)) is True

    assert os.environ.get("UNCLOSED") is None, (
        f"the opening quote reached the value: {os.environ.get('UNCLOSED')!r}"
    )
    assert "never closed" in caplog.text, "the key was dropped with no explanation"
    assert "UNCLOSED" in caplog.text, "the warning does not name the key"


def test_the_rest_of_the_file_still_loads(tmp_path, monkeypatch, no_dotenv) -> None:
    """Guards the fix. One bad line must not abandon the file — the keys after it are the ones the
    user is most likely to need."""
    env_file = _write(tmp_path, 'UNCLOSED="sk-broken\nGOOD="sk-real"\nTRAIL=sk-plain\n')
    for key in ("UNCLOSED", "GOOD", "TRAIL"):
        monkeypatch.delenv(key, raising=False)

    load_env(str(env_file))
    assert os.environ.get("GOOD") == "sk-real"
    assert os.environ.get("TRAIL") == "sk-plain"


@pytest.mark.parametrize("body,key,expected", [
    ('K="quoted value"\n', "K", "quoted value"),
    ("K='single quoted'\n", "K", "single quoted"),
    ("K=bare\n", "K", "bare"),
    ("K=bare # trailing comment\n", "K", "bare"),
    ('K="keeps # inside quotes"\n', "K", "keeps # inside quotes"),
    ("export K=exported\n", "K", "exported"),
    ("K =  spaced  \n", "K", "spaced"),
])
def test_the_shapes_that_already_worked_still_work(
    body: str, key: str, expected: str, tmp_path, monkeypatch, no_dotenv
) -> None:
    """The eight-line comparison in `_parse_value`'s docstring is the contract; widening the return
    type must not disturb any of it."""
    env_file = _write(tmp_path, body)
    monkeypatch.delenv(key, raising=False)
    load_env(str(env_file))
    assert os.environ.get(key) == expected


def test_parse_value_reports_unparseable_rather_than_guessing() -> None:
    """The unit-level contract the loader depends on."""
    assert _parse_value('"unclosed') is None
    assert _parse_value("'unclosed") is None
    assert _parse_value('"closed"') == "closed"
    assert _parse_value("plain") == "plain"


def test_a_real_environment_variable_still_wins(tmp_path, monkeypatch, no_dotenv) -> None:
    """The module's stated guarantee, re-checked because the loop body changed."""
    env_file = _write(tmp_path, "K=from_file\n")
    monkeypatch.setenv("K", "from_shell")
    load_env(str(env_file))
    assert os.environ["K"] == "from_shell"
