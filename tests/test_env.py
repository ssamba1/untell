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


# Which parser runs depends only on whether an optional dependency is installed, so any
# disagreement means one .env file configures the program two different ways. The divergence that
# was there: an inline comment on an unquoted value.
#
#     SOME_API_KEY=abc123 # the prod key
#       python-dotenv -> "abc123"
#       the fallback  -> "abc123 # the prod key"
#
# A key carrying trailing junk fails auth at the remote end, and nothing in that error names the
# .env file. These are stated as expected values so they hold with or without python-dotenv, and
# the differential test below re-derives them from python-dotenv itself when it is installed.
_VALUE_CASES = [
    ("PLAIN=abc123", "abc123"),
    ("WITH_COMMENT=abc123 # the prod key", "abc123"),
    ('QUOTED="abc123"', "abc123"),
    ('QUOTED_WITH_HASH="abc # 123"', "abc # 123"),      # inside quotes a # is data
    ('QUOTED_THEN_COMMENT="abc123" # note', "abc123"),  # close on the MATCHING quote
    ("SINGLE='abc123'", "abc123"),
    ("SINGLE_WITH_HASH='abc # 123'", "abc # 123"),
    ("HASH_NO_SPACE=abc#123", "abc#123"),               # a comment needs leading whitespace
    ("URL=https://example.com/path#fragment", "https://example.com/path#fragment"),
    ("APOSTROPHE=it's fine", "it's fine"),
    ("EQUALS_IN_VALUE=a=b=c", "a=b=c"),
    ("TRAILING_SPACE=abc123   ", "abc123"),
    ("EMPTY=", ""),
]


@pytest.mark.parametrize(("line", "expected"), _VALUE_CASES, ids=[c[0].split("=")[0] for c in _VALUE_CASES])
def test_fallback_parser_values(tmp_path, monkeypatch, line, expected):
    monkeypatch.setitem(sys.modules, "dotenv", None)  # force the zero-dependency parser
    key = line.split("=", 1)[0]
    env = tmp_path / ".env"
    env.write_text(line + "\n", encoding="utf-8")
    monkeypatch.delenv(key, raising=False)

    assert load_env(str(env)) is True
    assert os.environ[key] == expected


def test_the_two_parsers_agree_on_every_case(tmp_path, monkeypatch):
    """Differential test: the optional dependency must not change what a .env file means."""
    pytest.importorskip("dotenv")
    source = "\n".join(line for line, _ in _VALUE_CASES) + "\n"
    keys = [line.split("=", 1)[0] for line, _ in _VALUE_CASES]

    def read(force_fallback: bool) -> dict[str, str | None]:
        env = tmp_path / (".env.fallback" if force_fallback else ".env.dotenv")
        env.write_text(source, encoding="utf-8")
        for k in keys:
            monkeypatch.delenv(k, raising=False)
        with monkeypatch.context() as m:
            if force_fallback:
                m.setitem(sys.modules, "dotenv", None)
            assert load_env(str(env)) is True
        return {k: os.environ.get(k) for k in keys}

    fallback = read(force_fallback=True)
    dotenv = read(force_fallback=False)
    assert fallback == dotenv
