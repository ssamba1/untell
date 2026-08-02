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

⚠️ **Nothing currently consults this module.** It is imported by no CLI, no server and no library
path, and appears in no documentation — so writing an ``untell.yaml`` today changes nothing. The
loader itself works and is tested; what is missing is the wiring at each entry point. Said here
explicitly because a module that documents a lookup order it does not participate in reads exactly
like a feature, and the docstring above would otherwise be a promise the package does not keep.
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
    """Load config from the first source that yields anything: ``untell.yaml``, ``pyproject.toml``.

    Returns a flat dict of config keys. Callers merge these with CLI args and env vars.

    Falls through on an EMPTY result, not merely on a missing file. Returning as soon as
    ``untell.yaml`` exists meant that a repo with both files and no PyYAML installed silently got
    ``{}`` — ``_try_yaml`` returns ``{}`` when the import fails — and ``pyproject.toml`` was never
    consulted. The user sees their pyproject settings ignored because of an unrelated missing
    dependency.
    """
    cwd = Path.cwd()
    for path, reader in ((cwd / "untell.yaml", _try_yaml), (cwd / "pyproject.toml", _try_pyproject)):
        if path.is_file():
            data = reader(path)
            if data:
                return data
    return {}


def _coerce(value: str, default: Any) -> Any:
    """Convert an env-var string to the type of ``default``.

    Environment variables are always strings, config files are typed. Without this, the SAME key
    answers ``0.30`` (float) from a file and ``"0.30"`` (str) from the environment, so
    ``get("threshold", 0.30) < 0.5`` raises TypeError only when the env var happens to be set —
    the worst kind of conditional failure.
    """
    if isinstance(default, bool):
        return value.strip().lower() in ("1", "true", "yes", "on")
    for caster in ((int,) if isinstance(default, int) else (float,) if isinstance(default, float) else ()):
        try:
            return caster(value)
        except ValueError:
            return default
    return value


def get(key: str, default: Any = None) -> Any:
    """Lookup: env var (``UNTELL_<KEY>``) > config file > default.

    An env value is coerced to the type of ``default`` so a key's type does not depend on which
    source supplied it.
    """
    val = os.environ.get(f"UNTELL_{key.upper()}")
    if val is not None:
        return _coerce(val, default) if default is not None else val
    return load().get(key, default)
