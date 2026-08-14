"""Killing test: _env never overrides a real environment variable (line 100).

`if key and key not in os.environ` — the "real env wins" guard. Mutating
`and` to `or` makes the condition true even when the key IS in the
environment, so the .env value would overwrite the real one.

dotenv is disabled so the stdlib fallback loop (where line 100 lives) runs.
"""
import os
import sys

from untell._env import load_env


def test_real_env_wins_over_dotenv_file(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "dotenv", None)  # force stdlib fallback
    p = tmp_path / ".env"
    p.write_text("ALREADY_SET=from_file\n")
    monkeypatch.setenv("ALREADY_SET", "real_value")

    assert load_env(str(p)) is True
    assert os.environ["ALREADY_SET"] == "real_value", (
        ".env overrode a real environment variable"
    )


def test_dotenv_file_sets_a_missing_var(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "dotenv", None)
    p = tmp_path / ".env"
    p.write_text("FRESH_KEY=from_file\n")
    monkeypatch.delenv("FRESH_KEY", raising=False)

    assert load_env(str(p)) is True
    assert os.environ["FRESH_KEY"] == "from_file"
