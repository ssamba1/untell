"""A dropped config file does not mean defaults — it means the next file in the chain.

`load()` returns the first source that yields anything: `untell.yaml`, then `pyproject.toml`. Each
reader warned that a file it could not use had settings that "are NOT applied and defaults are in
use". The first half is true and the second is not, because falling through hands control to the
next source. MEASURED with a malformed untell.yaml beside a pyproject.toml carrying
`threshold = 0.91`:

    warning:  "...are NOT applied and defaults are in use."
    effective: {'threshold': 0.91}

0.91 is a cut at which almost nothing flags. A user reading that warning believes their clean
verdicts came from the 0.30 default; they came from a file they were told was not in play.

Only `load()` knows which source won, so that is where the correction lives.
"""

from __future__ import annotations

import logging
import pathlib

import pytest

from untell import config

BROKEN_YAML = "threshold: [this is: not: valid: yaml\n"
PYPROJECT = "[tool.untell]\nthreshold = 0.91\n"


@pytest.fixture
def in_tmp(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    if hasattr(config.load, "cache_clear"):
        config.load.cache_clear()
    yield tmp_path
    if hasattr(config.load, "cache_clear"):
        config.load.cache_clear()


def test_the_fallthrough_source_is_named(in_tmp, caplog: pytest.LogCaptureFixture) -> None:
    (in_tmp / "untell.yaml").write_text(BROKEN_YAML, encoding="utf-8")
    (in_tmp / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger=config.logger.name):
        loaded = config.load()

    assert loaded == {"threshold": 0.91}, "premise: the lower source must actually be in effect"
    assert "pyproject.toml" in caplog.text, "the file that won is the one a user needs named"
    assert "not the defaults" in caplog.text
    # The claim this replaced. Leaving it in would be worse than saying nothing, since it points
    # the reader at a number that is not the one deciding their verdicts.
    assert "defaults are in use" not in caplog.text


def test_a_single_healthy_source_says_nothing(in_tmp, caplog: pytest.LogCaptureFixture) -> None:
    """Guards the guard: pyproject.toml alone is the ordinary case and must stay quiet."""
    (in_tmp / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger=config.logger.name):
        assert config.load() == {"threshold": 0.91}
    assert "settings came from" not in caplog.text


def test_no_config_at_all_says_nothing(in_tmp, caplog: pytest.LogCaptureFixture) -> None:
    """The most common case of all. A warning here would fire for every user with no config."""
    with caplog.at_level(logging.WARNING, logger=config.logger.name):
        assert config.load() == {}
    assert caplog.text == ""


def test_a_pyproject_without_our_table_is_not_a_fallthrough(
    in_tmp, caplog: pytest.LogCaptureFixture
) -> None:
    """A pyproject.toml with no [tool.untell] yields {} and is the last source — nothing came after
    it, so there is no "the values in use are below it" to report. This is the common shape of a
    real repo and must not produce a warning."""
    (in_tmp / "pyproject.toml").write_text('[project]\nname = "something-else"\n', encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger=config.logger.name):
        assert config.load() == {}
    assert "settings came from" not in caplog.text


def test_the_broken_file_is_still_reported(in_tmp, caplog: pytest.LogCaptureFixture) -> None:
    """The reader's own warning has to survive the rewording — a user needs to know their YAML is
    malformed, separately from knowing what ran instead."""
    (in_tmp / "untell.yaml").write_text(BROKEN_YAML, encoding="utf-8")
    (in_tmp / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger=config.logger.name):
        config.load()
    assert "could not be parsed" in caplog.text
    assert "untell.yaml" in caplog.text
