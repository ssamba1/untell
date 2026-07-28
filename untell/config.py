"""Config file loader — reads settings from ``untell.yaml`` or ``pyproject.toml [tool.untell]``.

Lookup order (first wins):
  1. CLI argument
  2. Environment variable (``UNTELL_*``)
  3. Config file (``untell.yaml`` in CWD, or ``pyproject.toml``)
  4. Default

Config file example (``untell.yaml``)::

    tier: full
    rewriter: composite
    style: academic
    threshold: 0.30
    api_key: sk-...           # same as UNTELL_API_KEY
    api_host: 0.0.0.0         # same as UNTELL_HOST
    api_port: 8000            # same as UNTELL_PORT

Or in ``pyproject.toml``::

    [tool.untell]
    tier = "full"
    rewriter = "composite"
    style = "academic"
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _try_pyproject(path: Path) -> dict[str, Any]:
    """Extract ``[tool.untell]`` from ``pyproject.toml``."""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # Python <3.11 fallback
        except ImportError:
            tomllib = None

    if tomllib is None:
        return {}

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return dict(data.get("tool", {}).get("untell", {}))
    except Exception:
        return {}


def _try_yaml(path: Path) -> dict[str, Any]:
    """Read ``untell.yaml`` (requires PyYAML; degrades gracefully)."""
    try:
        import yaml
    except ImportError:
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return dict(data) if isinstance(data, dict) else {}
    except Exception:
        return {}


def load() -> dict[str, Any]:
    """Load config from the first available source: ``untell.yaml`` or ``pyproject.toml``.

    Returns a flat dict of config keys. Callers merge these with CLI args and env vars.
    """
    cwd = Path.cwd()
    yaml_path = cwd / "untell.yaml"
    pyproject_path = cwd / "pyproject.toml"

    if yaml_path.is_file():
        return _try_yaml(yaml_path)
    if pyproject_path.is_file():
        return _try_pyproject(pyproject_path)
    return {}


def get(key: str, default: Any = None) -> Any:
    """Lookup: env var (``UNTELL_<KEY>``) > config file > default."""
    env_key = f"UNTELL_{key.upper()}"
    val = os.environ.get(env_key)
    if val is not None:
        return val
    cfg = load()
    return cfg.get(key, default)
