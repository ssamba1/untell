"""Edge branches of the config loader and the language router.

The yaml-missing path can only be reached when PyYAML is absent, so it is driven with the
import faked away; the language router's name-lookup fallback is driven with a character
that has no Unicode name at all (a lone surrogate).
"""

from __future__ import annotations

import sys

from untell.config import _try_yaml
from untell.languages import dominant_script


def test_try_yaml_without_pyyaml_warns_and_returns_empty(tmp_path, monkeypatch, caplog):
    """`untell.yaml` must be ignored WITH a warning, not silently dropped, when PyYAML is
    missing — the settings exist and are not being applied."""
    import logging

    cfg = tmp_path / "untell.yaml"
    cfg.write_text("threshold: 0.5\n", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "yaml", None)  # `import yaml` -> ImportError

    with caplog.at_level(logging.WARNING, logger="untell.config"):
        assert _try_yaml(cfg) == {}
    assert any("PyYAML" in r.message for r in caplog.records), (
        "the absence of PyYAML must be named in the warning"
    )


def test_a_character_with_no_unicode_name_is_skipped_not_fatal():
    """U+17000 (a Tangut ideograph) is alpha but has no entry in Python's Unicode name
    database, so `unicodedata.name` raises ValueError and the router must skip it rather
    than crash — with nothing else in the text it falls back to the Latin default."""
    assert dominant_script("\U00017000") == "Latin"


def test_named_scripts_still_win_over_the_fallback():
    # Sanity anchor: the fallback only applies when nothing else matched.
    assert dominant_script("привет") != "Latin"
