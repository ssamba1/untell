"""A config file that exists and is not applied has to say so.

`_try_yaml` already did: PyYAML missing logs a warning naming the file and what to do instead,
with a comment explaining why silence would be wrong — "the settings exist and are not being
applied". `_try_pyproject` was in the identical situation and returned `{}` without a word.

That matters on the versions this package declares. `tomllib` arrived in Python 3.11;
`requires-python` is `>=3.9` and the classifiers list 3.9 and 3.10, `tomli` is not a dependency,
and the README documents `[tool.untell]` as a supported config source with no version caveat. So on
two of the four supported Pythons a user's settings were dropped in silence.

`tomli` is deliberately NOT added: the base install is zero-dependency by design, which is a
stronger constraint than this feature. Telling the user is the part that was missing.
"""

from __future__ import annotations

import builtins
import logging
import pathlib

import pytest

import untell.config as C


@pytest.fixture
def pyproject(tmp_path: pathlib.Path) -> pathlib.Path:
    p = tmp_path / "pyproject.toml"
    p.write_text('[tool.untell]\ntier = "lite"\n', encoding="utf-8")
    return p


@pytest.fixture
def no_toml_parser(monkeypatch: pytest.MonkeyPatch):
    """Simulate Python 3.9/3.10 with no `tomli` installed."""
    real = builtins.__import__

    def fake(name, *a, **k):
        if name in ("tomllib", "tomli"):
            raise ImportError(f"no module named {name}")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)


def test_pyproject_settings_are_read_when_a_parser_exists(pyproject: pathlib.Path) -> None:
    assert C._try_pyproject(pyproject) == {"tier": "lite"}


def test_ignoring_pyproject_is_not_silent(pyproject, no_toml_parser, caplog) -> None:
    with caplog.at_level(logging.WARNING):
        assert C._try_pyproject(pyproject) == {}
    assert caplog.records, "the file was ignored with no warning"
    msg = caplog.records[0].getMessage()
    assert "tomllib" in msg and "NOT applied" in msg
    assert str(pyproject) in msg, "the warning must name the file it ignored"


def test_the_warning_offers_a_way_forward(pyproject, no_toml_parser, caplog) -> None:
    """Naming the problem without a remedy just relocates the confusion."""
    with caplog.at_level(logging.WARNING):
        C._try_pyproject(pyproject)
    msg = caplog.records[0].getMessage()
    assert "tomli" in msg
    assert "untell.yaml" in msg or "UNTELL_" in msg


def test_the_yaml_branch_still_warns_too() -> None:
    """The behaviour this was matched to. If it goes, the pair is inconsistent again."""
    import inspect

    src = inspect.getsource(C._try_yaml)
    assert "logger.warning" in src


def test_base_install_stays_zero_dependency() -> None:
    """The reason `tomli` was not simply added. If that changes, revisit this whole trade."""
    import tomllib as _t

    data = _t.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["dependencies"] == [], (
        "base dependencies are no longer empty — if that is deliberate, `tomli; "
        'python_version < "3.11"` would make [tool.untell] work everywhere it is documented'
    )
