"""Config loader tests.

``untell/config.py`` is imported by no CLI, no server and no library path — writing an
``untell.yaml`` today changes nothing. That is recorded in the module docstring rather than fixed
here, but the loader's own behaviour is still worth pinning: it is shipped in the package, it is
importable, and its two defects below were the kind that only appear in one environment.
"""

from __future__ import annotations

import os

import pytest

from untell import config


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("UNTELL_"):
            monkeypatch.delenv(key, raising=False)


COERCIONS = [
    ("threshold", "0.45", 0.30, 0.45),
    ("port", "9000", 8000, 9000),
    ("debug", "yes", False, True),
    ("debug", "0", True, False),
    ("tier", "full", "lite", "full"),
]


@pytest.mark.parametrize("key,env_value,default,expected", COERCIONS)
def test_env_value_takes_the_type_of_the_default(monkeypatch, key, env_value, default, expected):
    """Environment variables are strings; config files are typed. Without coercion the SAME key
    answers 0.30 (float) from a file and "0.30" (str) from the environment, so
    `get("threshold", 0.30) < 0.5` raises TypeError only when the env var happens to be set."""
    monkeypatch.setenv(f"UNTELL_{key.upper()}", env_value)
    got = config.get(key, default)
    assert got == expected and type(got) is type(expected), f"{got!r} ({type(got).__name__})"


def test_uncoercible_env_value_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("UNTELL_THRESHOLD", "not-a-number")
    assert config.get("threshold", 0.30) == 0.30


def test_env_without_a_default_stays_a_string(monkeypatch):
    monkeypatch.setenv("UNTELL_TIER", "full")
    assert config.get("tier") == "full"


def test_missing_key_returns_the_default(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert config.get("definitely-not-set", "fallback") == "fallback"


def test_pyproject_is_read_when_yaml_yields_nothing(monkeypatch, tmp_path):
    """`load()` returned as soon as untell.yaml EXISTED. `_try_yaml` returns {} when PyYAML is not
    installed, so a repo with both files and no PyYAML silently got {} and pyproject was never
    consulted — the user's settings ignored because of an unrelated missing dependency."""
    (tmp_path / "untell.yaml").write_text("tier: full\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.untell]\ntier = "heavy"\nrewriter = "composite"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "_try_yaml", lambda _p: {})  # simulate PyYAML absent
    assert config.load() == {"tier": "heavy", "rewriter": "composite"}


def test_yaml_wins_when_it_does_parse(monkeypatch, tmp_path):
    (tmp_path / "untell.yaml").write_text("tier: full\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[tool.untell]\ntier = "heavy"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "_try_yaml", lambda _p: {"tier": "full"})
    assert config.load()["tier"] == "full"


def test_no_config_files_is_an_empty_dict(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert config.load() == {}


def test_pyproject_without_a_tool_untell_table_is_empty(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "other"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert config.load() == {}


def test_malformed_pyproject_does_not_raise(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text("this is not [valid toml", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert config.load() == {}


class TestABrokenConfigFileIsNotSilent:
    """A file the user WROTE and got wrong is not the same as no file.

    Both readers swallowed every exception and returned {}, so a YAML typo or a broken TOML table
    meant the settings were dropped, every default applied, and nothing anywhere said so — a
    mistyped `threshold` looked exactly like never having set one. The tool should keep running on
    a broken config; it must not do so invisibly.
    """

    MALFORMED = [
        ("untell.yaml", "threshold: 0.2\n  tier: full\n   rewriter: [\n"),
        ("untell.yaml", 'threshold: "0.2\ntier: full\n'),
        ("pyproject.toml", '[tool.untell]\nthreshold = 0.2\ntier = "full\n'),
        ("pyproject.toml", "[tool.untell\nthreshold = 0.2\n"),
    ]

    @pytest.mark.parametrize(("filename", "body"), MALFORMED)
    def test_it_warns_and_names_the_file(self, monkeypatch, tmp_path, caplog, filename, body):
        (tmp_path / filename).write_text(body, encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        with caplog.at_level("WARNING", logger="untell.config"):
            assert config.load() == {}
        assert filename in caplog.text
        assert "NOT applied" in caplog.text

    @pytest.mark.parametrize(("filename", "body"), MALFORMED)
    def test_it_still_does_not_raise(self, monkeypatch, tmp_path, filename, body):
        (tmp_path / filename).write_text(body, encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        assert config.load() == {}

    def test_a_valid_file_warns_about_nothing(self, monkeypatch, tmp_path, caplog):
        (tmp_path / "pyproject.toml").write_text(
            '[tool.untell]\nthreshold = 0.2\n', encoding="utf-8"
        )
        monkeypatch.chdir(tmp_path)
        with caplog.at_level("WARNING", logger="untell.config"):
            assert config.load() == {"threshold": 0.2}
        assert not caplog.text

    def test_a_yaml_that_is_not_a_mapping_is_reported(self, monkeypatch, tmp_path, caplog):
        """A file parsing to a list is as silently ignored as one that fails to parse."""
        pytest.importorskip("yaml")
        (tmp_path / "untell.yaml").write_text("- threshold\n- tier\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        with caplog.at_level("WARNING", logger="untell.config"):
            assert config.load() == {}
        assert "expected a mapping" in caplog.text

    def test_an_absent_file_says_nothing(self, monkeypatch, tmp_path, caplog):
        monkeypatch.chdir(tmp_path)
        with caplog.at_level("WARNING", logger="untell.config"):
            assert config.load() == {}
        assert not caplog.text


def test_env_beats_the_config_file(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[tool.untell]\ntier = "heavy"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("UNTELL_TIER", "lite")
    assert config.get("tier", "full") == "lite"
