"""The REST API's reported version must match the package version.

api_server.py carried a hand-written APP_VERSION = "0.2.0" that drifted a minor
release behind the package (0.3.0 in pyproject.toml and untell/__init__.py),
while test_every_declared_version_agrees covered four declarations but not the
API's. This pins the API surface directly.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_api_version_matches_package_version():
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    expected = re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)

    api = (REPO / "untell" / "api_server.py").read_text(encoding="utf-8")
    declared = re.search(r'APP_VERSION = "([^"]+)"', api).group(1)

    assert declared == expected, (
        f"untell/api_server.py APP_VERSION is {declared!r} but the package version is "
        f"{expected!r}"
    )


def test_api_uses_its_declared_version():
    """The FastAPI app and the /info-style version field both use APP_VERSION."""
    import untell.api_server as api

    assert api.app.version == api.APP_VERSION
