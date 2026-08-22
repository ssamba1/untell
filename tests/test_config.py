"""Config loader tests.

``untell/config.py`` is imported by no CLI, no server and no library path — writing an
``untell.yaml`` today changes nothing. That is recorded in the module docstring rather than fixed
here, but the loader's own behaviour is still worth pinning: it is shipped in the package, it is
importable, and its two defects below were the kind that only appear in one environment.
"""

from __future__ import annotations

import math
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


def test_an_unconvertible_env_value_is_reported_not_silently_dropped(monkeypatch, caplog):
    """Both file readers warn when a setting the user wrote is dropped. The environment did not.

    `UNTELL_MAX_ITERS=3.7` fell back to the default and said nothing, so a value the user could see
    in their own shell behaved exactly as if it had never been set.
    """
    import logging

    from untell import config

    monkeypatch.setenv("UNTELL_MAX_ITERS", "3.7")
    with caplog.at_level(logging.WARNING, logger="untell.config"):
        assert config.get("max_iters", 5) == 5
    assert "UNTELL_MAX_ITERS" in caplog.text
    assert "3.7" in caplog.text


def test_a_convertible_env_value_stays_quiet(monkeypatch, caplog):
    import logging

    from untell import config

    monkeypatch.setenv("UNTELL_MAX_ITERS", "7")
    with caplog.at_level(logging.WARNING, logger="untell.config"):
        assert config.get("max_iters", 5) == 7
    assert caplog.text == ""


class TestTheLoopCliActuallyReadsTheConfig:
    """This module documented a lookup order and participated in none of it.

    It was imported by no CLI, no server and no library path, so writing an untell.yaml changed
    nothing. `untell humanize` now takes its defaults from here.
    """

    def _parse(self, argv):
        from untell.scripts.run import build_parser

        return build_parser().parse_args(argv)

    def test_shipped_defaults_when_nothing_is_configured(self, monkeypatch):
        for var in ("UNTELL_TIER", "UNTELL_THRESHOLD", "UNTELL_MAX_ITERS", "UNTELL_REWRITER",
                    "UNTELL_STYLE", "UNTELL_BEST_OF"):
            monkeypatch.delenv(var, raising=False)
        args = self._parse(["x"])
        assert (args.tier, args.rewriter, args.best_of, args.style) == ("full", "composite", 3, None)

    def test_env_moves_the_default(self, monkeypatch):
        monkeypatch.setenv("UNTELL_TIER", "lite")
        monkeypatch.setenv("UNTELL_BEST_OF", "5")
        args = self._parse(["x"])
        assert args.tier == "lite"
        assert args.best_of == 5

    def test_a_command_line_flag_still_wins(self, monkeypatch):
        monkeypatch.setenv("UNTELL_TIER", "lite")
        assert self._parse(["x", "--tier", "heavy"]).tier == "heavy"

    def test_a_configured_value_outside_the_choices_is_refused(self, monkeypatch, capsys):
        """`choices=` validates what the user TYPES, never the `default=`.

        Without this check a `tier: fulll` would sail past argparse and surface much later as an
        empty detector list — a config typo turning into a mystery at scoring time.
        """
        monkeypatch.setenv("UNTELL_TIER", "fulll")
        args = self._parse(["x"])
        assert args.tier == "full"
        assert "fulll" in capsys.readouterr().err

    def test_a_broken_config_does_not_stop_the_cli(self, monkeypatch):
        from untell import config

        def boom(*a, **k):
            raise RuntimeError("config on fire")

        monkeypatch.setattr(config, "get", boom)
        assert self._parse(["x"]).tier == "full"


# --- an env var must not change a key's TYPE ----------------------------------------------------
# `_coerce`'s docstring states the hazard: the same key answering 0.30 (float) from a file and
# "0.30" (str) from the environment makes `get("threshold") < 0.5` raise TypeError only when the
# env var happens to be set. The coercion that prevents it was gated on the caller passing a
# default, so the promise held for `get(key, default)` and not for `get(key)`.


def test_an_env_var_takes_its_type_from_the_config_file(tmp_path, monkeypatch):
    """The path the docstring promised and the code did not cover."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "untell.yaml").write_text("threshold: 0.11\nbest_of: 7\n", encoding="utf-8")
    from untell import config

    monkeypatch.setenv("UNTELL_THRESHOLD", "0.99")
    monkeypatch.setenv("UNTELL_BEST_OF", "3")
    assert config.get("threshold") == pytest.approx(0.99)
    assert isinstance(config.get("threshold"), float), "env value came back as a string"
    assert config.get("best_of") == 3
    assert isinstance(config.get("best_of"), int)


def test_a_key_with_no_type_anywhere_stays_a_string(tmp_path, monkeypatch):
    """The documented limit, pinned so it is a decision rather than a surprise. With neither a
    default nor a file value there is nothing to infer a type from, and guessing would make
    UNTELL_X=1 an int while UNTELL_X=1.0 is a float."""
    monkeypatch.chdir(tmp_path)
    from untell import config

    monkeypatch.setenv("UNTELL_TOTALLYUNKNOWN", "1.5")
    assert config.get("totallyunknown") == "1.5"


def test_a_passed_default_still_wins_the_type(tmp_path, monkeypatch):
    """Guards the guard: the original behaviour must be untouched."""
    monkeypatch.chdir(tmp_path)
    from untell import config

    monkeypatch.setenv("UNTELL_THRESHOLD", "0.42")
    assert config.get("threshold", 0.30) == pytest.approx(0.42)
    assert isinstance(config.get("threshold", 0.30), float)


# --- non-finite float env vars must not silently corrupt the config ---------------------------
# `float("nan")` and `float("inf")` succeed in Python without raising ValueError, so the
# ValueError branch in `_coerce` never fired for them.
#
#   UNTELL_THRESHOLD=nan  -> _coerce returned nan  -> score >= nan is always False -> nothing flags
#   UNTELL_THRESHOLD=inf  -> _coerce returned inf  -> threshold unreachable       -> nothing flags
#   UNTELL_THRESHOLD=1e999 -> float("1e999") == inf (CPython overflow)            -> same as inf
#
# All three are as harmful as a non-parseable value ("abc" -> default + warning), but were
# silently passed through. Now they also warn and fall back to the default, matching the
# documented contract: "A value that will not convert falls back to the default AND SAYS SO."


@pytest.mark.parametrize("bad_value", ["nan", "inf", "-inf", "1e999"])
def test_non_finite_float_env_var_falls_back_to_default(monkeypatch, caplog, bad_value):
    """A non-finite string that float() accepts must not silently bypass the default."""
    import logging

    from untell import config

    monkeypatch.setenv("UNTELL_THRESHOLD", bad_value)
    with caplog.at_level(logging.WARNING, logger="untell.config"):
        result = config.get("threshold", 0.30)

    assert math.isfinite(result), (
        f"UNTELL_THRESHOLD={bad_value!r} produced a non-finite threshold {result!r}; "
        "detection would be silently disabled"
    )
    assert result == pytest.approx(0.30), f"expected fallback to default 0.30, got {result!r}"
    assert caplog.text, f"UNTELL_THRESHOLD={bad_value!r} was silently accepted — no warning logged"


def test_finite_float_env_var_is_still_accepted(monkeypatch, caplog):
    """The fix must not break ordinary float values."""
    import logging

    from untell import config

    monkeypatch.setenv("UNTELL_THRESHOLD", "0.55")
    with caplog.at_level(logging.WARNING, logger="untell.config"):
        result = config.get("threshold", 0.30)
    assert result == pytest.approx(0.55)
    assert caplog.text == "", "a valid float should produce no warning"
