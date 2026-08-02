""".env loader tests."""

from __future__ import annotations

import os
import sys

import pytest

from untell._env import load_env


def test_load_env_sets_vars_and_respects_existing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        'FOO_KEY=from_file\nBAR_KEY="quoted val"\n# a comment\n\nEXISTING=should_not_win\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("EXISTING", "real")
    monkeypatch.delenv("FOO_KEY", raising=False)
    monkeypatch.delenv("BAR_KEY", raising=False)

    assert load_env(str(env)) is True
    assert os.environ["FOO_KEY"] == "from_file"
    assert os.environ["BAR_KEY"] == "quoted val"  # surrounding quotes stripped
    assert os.environ["EXISTING"] == "real"  # a real env var always wins


def test_load_env_missing_file_is_noop(tmp_path):
    assert load_env(str(tmp_path / "does-not-exist.env")) is False


def test_load_env_handles_bom_and_export(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    # BOM-prefixed (common from Windows editors) + a shell-style `export ` prefix on the first key.
    env.write_bytes("﻿export BOM_KEY=hi\nNORMAL_KEY=ok\n".encode())
    monkeypatch.delenv("BOM_KEY", raising=False)
    monkeypatch.delenv("NORMAL_KEY", raising=False)

    assert load_env(str(env)) is True
    assert os.environ["BOM_KEY"] == "hi"  # BOM stripped + `export ` tolerated
    assert os.environ["NORMAL_KEY"] == "ok"


# Every caller in the tree (api_server, verify, score, ceiling, prove, distill, dpo_humanizer)
# calls ``load_env()`` with no argument, but until now every test passed an explicit path — so the
# bare call was untested and, with python-dotenv installed, loaded nothing at all. Both branches
# get pinned: bare ``load_dotenv()`` resolves relative to the *calling file*, not the cwd.
@pytest.mark.parametrize("with_dotenv", [True, False], ids=["python-dotenv", "stdlib-fallback"])
def test_load_env_bare_call_reads_the_cwd(tmp_path, monkeypatch, with_dotenv):
    if not with_dotenv:
        monkeypatch.setitem(sys.modules, "dotenv", None)  # force the zero-dependency parser
    (tmp_path / ".env").write_text("CWD_PROBE_KEY=from_cwd\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CWD_PROBE_KEY", raising=False)

    assert load_env() is True
    assert os.environ["CWD_PROBE_KEY"] == "from_cwd"


def test_load_env_bare_call_with_no_env_file_is_noop(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_env() is False
