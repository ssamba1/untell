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
import math
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
        # Same situation as PyYAML being absent in `_try_yaml`, and it deserves the same warning:
        # the settings exist in the file and are not being applied. That branch says so and this
        # one returned {} silently, so `[tool.untell]` was quietly ignored on Python 3.9 and 3.10
        # — both of which this package declares support for (`requires-python = ">=3.9"`, and the
        # classifiers list them) — while the README documents the file as a supported config source
        # with no version caveat.
        #
        # `tomli` is not added as a dependency because the base install is intentionally
        # zero-dependency, which is a stronger constraint than this feature. Telling the user is the
        # part that was missing.
        logger.warning(
            "ignoring [tool.untell] in %s: this Python has no `tomllib` (added in 3.11) and "
            "`tomli` is not installed, so those settings are NOT applied "
            "(pip install tomli, or use untell.yaml, or set the UNTELL_* environment variables).",
            path,
        )
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
            "are NOT applied.", path, type(exc).__name__, exc,
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
            "ignoring %s: it exists but could not be parsed (%s: %s). Its settings are NOT "
            "applied.", path, type(exc).__name__, exc,
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
    dropped: list[Path] = []
    for path, reader in ((cwd / "untell.yaml", _try_yaml), (cwd / "pyproject.toml", _try_pyproject)):
        if path.is_file():
            data = reader(path)
            if data:
                # Only `load` knows this, and it is the part that was wrong. The readers above each
                # said the dropped file's settings "are NOT applied and defaults are in use" — true
                # about the file, false about the outcome, because falling through means the NEXT
                # source applies, not the defaults. MEASURED with a broken untell.yaml beside a
                # pyproject.toml carrying `threshold = 0.91`: the warning said defaults were in use
                # and the effective threshold was 0.91, a cut at which almost nothing flags. A user
                # reading that believes their verdicts came from 0.30.
                if dropped:
                    logger.warning(
                        "settings came from %s. %s existed and supplied nothing, so it did not "
                        "override anything — the values in use are the ones below it in the chain, "
                        "not the defaults.",
                        path, ", ".join(str(p) for p in dropped),
                    )
                return data
            dropped.append(path)
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
            result = caster(value)
        except ValueError:
            logger.warning(
                "ignoring UNTELL_%s=%r: expected %s, using the default %r instead.",
                (key or "?").upper(), value, caster.__name__, default,
            )
            return default
        # `float("nan")` and `float("inf")` succeed — no ValueError — so the branch above
        # never fires for them. But a threshold of `nan` makes every comparison return False
        # (detection disabled) and `inf` makes the threshold unreachable (same effect). Both
        # are as harmful as a non-parseable value, and both must say so.
        # `float("1e309")` returns `inf` in CPython (overflow to infinity, not an exception),
        # so this also catches `UNTELL_THRESHOLD=1e999` and similar out-of-range exponents.
        if isinstance(result, float) and not math.isfinite(result):
            logger.warning(
                "ignoring UNTELL_%s=%r: expected a finite number, got %s, "
                "using the default %r instead.",
                (key or "?").upper(), value, result, default,
            )
            return default
        return result
    return value


def get(key: str, default: Any = None) -> Any:
    """Lookup: env var (``UNTELL_<KEY>``) > config file > default.

    An env value is coerced to the type of ``default`` so a key's type does not depend on which
    source supplied it.
    """
    val = os.environ.get(f"UNTELL_{key.upper()}")
    if val is not None:
        if default is not None:
            return _coerce(val, default, key)
        # No default to take a type from, so fall back to the type the CONFIG FILE uses for this
        # key. Without this the promise above holds only for callers who pass a default:
        # `get("threshold")` returned 0.11 (float) from untell.yaml and "0.99" (str) from the
        # environment — the same conditional TypeError the docstring on `_coerce` describes, in the
        # one path that was not covered.
        #
        # When neither a default nor a file value exists there is nothing to infer a type from, and
        # the raw string is returned. That is a real limit, not an oversight: guessing int-vs-float
        # from the text would make `UNTELL_THRESHOLD=1` an int and `=1.0` a float.
        typed = load().get(key)
        return _coerce(val, typed, key) if typed is not None else val
    return load().get(key, default)
