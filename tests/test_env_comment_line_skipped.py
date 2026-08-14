"""Killing test: _env skips comment lines (line 84 or-chain).

A comment line like `# KEY = value` must be skipped. Mutating the or-chain
`not line or startswith("#") or "=" not in line` to `and` would parse the
comment as a real key (`# KEY`).

python-dotenv shadows the stdlib fallback loop when installed, so the dotenv
import is disabled (same pattern as test_env.py) to force the loop where the
mutation lives.
"""
import os
import sys

from untell._env import load_env


def test_comment_line_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "dotenv", None)  # force stdlib fallback
    p = tmp_path / ".env"
    p.write_text("# SECRET_KEY = supersecret\n")
    for k in list(os.environ):
        if "SECRET" in k:
            del os.environ[k]
    assert load_env(str(p)) is True
    # No key may be created from a comment — neither bare nor #-prefixed.
    assert not any("SECRET" in k for k in os.environ), (
        f"comment line leaked into env: {[k for k in os.environ if 'SECRET' in k]}"
    )


def test_blank_line_and_comment_line_together(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "dotenv", None)
    p = tmp_path / ".env"
    p.write_text("\n\n# only comments\n\n")
    assert load_env(str(p)) is True
