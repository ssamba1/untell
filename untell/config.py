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

**Wired into ``untell humanize`` only** (``untell/scripts/run.py``, ``_config_defaults``): tier,
threshold, max_iters, rewriter, style, best_of. Those keys are read here, validated against the
same choice lists argparse enforces, and used as the parser's defaults, so a command-line flag
still wins over a config file.

Everything else in the example above — ``api_key``, ``api_host``, ``api_port`` — is still read by
nobody. The REST and MCP surfaces have their own defaults and do NOT consult this module, so a
``tier:`` set here changes the CLI and not those. Said explicitly because a module that documents
a lookup order it only partly participates in reads exactly like a finished feature.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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
    except Exception as exc:
        # A file the user WROTE and got wrong is not the same as no file. Swallowing this returned
        # {}, every default applied, and nothing said the config had been dropped — so a typo in
        # `threshold` looked exactly like never having set it. Say so and keep going: a broken
        # config should not stop the tool, but it must not be invisible either.
        logger.warning(
            "ignoring %s: it exists but could not be parsed (%s: %s). Its [tool.untell] settings "
            "are NOT applied and defaults are in use.", path, type(exc).__name__, exc,
        )
        return {}


def _try_yaml(path: Path) -> dict[str, Any]:
    """Read ``untell.yaml`` (requires PyYAML; degrades gracefully)."""
    try:
        import yaml
    except ImportError:
        # Not a user error, but still a silently ignored file: the settings exist and are not being
        # applied. `load()` already falls through to pyproject.toml on an empty result, so this is
        # informational rather than a warning about correctness.
        logger.warning(
            "ignoring %s: PyYAML is not installed, so its settings are NOT applied "
            "(pip install pyyaml, or move them to pyproject.toml under [tool.untell]).", path,
        )
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        logger.warning(
            "ignoring %s: it exists but could not be parsed (%s: %s). Its settings are NOT applied "
            "and defaults are in use.", path, type(exc).__name__, exc,
        )
        return {}
    if data is not None and not isinstance(data, dict):
        # A YAML file that parses to a list or a bare scalar is not a config mapping. Returning {}
        # for it was as silent as a parse failure.
        logger.warning(
            "ignoring %s: expected a mapping of settings, got %s. Its contents are NOT applied.",
            path, type(data).__name__,
        )
        return {}
    return dict(data) if isinstance(data, dict) else {}


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


def _coerce(value: str, default: Any, key: str = "") -> Any:
    """Convert an env-var string to the type of ``default``.

    Environment variables are always strings, config files are typed. Without this, the SAME key
    answers ``0.30`` (float) from a file and ``"0.30"`` (str) from the environment, so
    ``get("threshold", 0.30) < 0.5`` raises TypeError only when the env var happens to be set —
    the worst kind of conditional failure.

    A value that will not convert falls back to the default AND SAYS SO. Both file readers above
    already warn when a setting the user wrote is being dropped; the environment was the one path
    that did it silently, so ``UNTELL_MAX_ITERS=3.7`` looked exactly like never setting it at all —
    and looked it while the user was staring at the variable in their shell.
    """
    if isinstance(default, bool):
        return value.strip().lower() in ("1", "true", "yes", "on")
    for caster in ((int,) if isinstance(default, int) else (float,) if isinstance(default, float) else ()):
        try:
            return caster(value)
        except ValueError:
            logger.warning(
                "ignoring UNTELL_%s=%r: expected %s, using the default %r instead.",
                (key or "?").upper(), value, caster.__name__, default,
            )
            return default
    return value


def get(key: str, default: Any = None) -> Any:
    """Lookup: env var (``UNTELL_<KEY>``) > config file > default.

    An env value is coerced to the type of ``default`` so a key's type does not depend on which
    source supplied it.
    """
    val = os.environ.get(f"UNTELL_{key.upper()}")
    if val is not None:
        return _coerce(val, default, key) if default is not None else val
    return load().get(key, default)
