"""Two `load_env` fallback behaviours the suite did not pin.

Found by mutation: `mutate.py untell/_env.py --max 15 --record` left two survivors.

1. Line 84  `or -> and`  — the line-skip guard. Mutated to `and`, the condition
   `not line and line.startswith("#") and "=" not in line` is almost never true, so
   comment lines fall through to the parser and become ENV VARS. The existing fixture
   in test_env.py contains `# a comment` but only asserts the positive keys, never that
   the comment stayed out of the environment. A comment becoming a key is exactly the
   silent-surprise class this module exists to prevent (`.env` is where API keys live).

2. Line 103 `False -> True` — the `except Exception` after the read/parse loop. Mutated
   to True, a file that cannot be decoded reports success, and the caller believes the
   `.env` was loaded. `read_text(encoding="utf-8-sig")` raises UnicodeDecodeError on
   non-UTF-8 bytes, so this is forceable without permission tricks.
"""

from __future__ import annotations

import builtins
import os

import pytest

from untell._env import load_env


@pytest.fixture
def no_dotenv(monkeypatch):
    """Force the zero-dependency fallback, which is what a base install uses."""
    real_import = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name == "dotenv":
            raise ImportError("forced: the base install has no python-dotenv")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)


def test_a_comment_line_does_not_become_an_environment_variable(tmp_path, monkeypatch, no_dotenv):
    """The fallback's skip guard must keep comments out of os.environ.

    Regression: `or -> and` in the guard let `# a comment` through to the parser, which
    stored it as the key `# a comment`. No existing test noticed because they only assert
    the keys that SHOULD be set, never the ones that must NOT be.
    """
    env = tmp_path / ".env"
    env.write_text("REAL_KEY=value\n# a comment\nANOTHER=yes\n", encoding="utf-8")
    monkeypatch.delenv("REAL_KEY", raising=False)
    monkeypatch.delenv("ANOTHER", raising=False)
    # The comment must not survive as a key under ANY name: not the full line, not a
    # trimmed form, not a partition fragment.
    monkeypatch.delenv("# a comment", raising=False)
    monkeypatch.delenv("a comment", raising=False)
    monkeypatch.delenv("#", raising=False)

    assert load_env(str(env)) is True
    assert os.environ["REAL_KEY"] == "value"
    assert os.environ["ANOTHER"] == "yes"
    for junk in ("# a comment", "a comment", "#"):
        assert junk not in os.environ, f"comment line leaked into os.environ as {junk!r}"


def test_an_undecodable_env_file_reports_failure(tmp_path, monkeypatch, no_dotenv):
    """A .env that cannot be decoded must return False, not pretend to succeed.

    Regression: `False -> True` in the read/parse `except` made a broken file report
    success, so the caller believed the environment was loaded when nothing was.
    """
    env = tmp_path / ".env"
    # 0xFF is not valid UTF-8, so read_text(encoding="utf-8-sig") raises.
    env.write_bytes(b"GOOD_KEY=value\n\xff\xfe\xfd broken\n")

    assert load_env(str(env)) is False
