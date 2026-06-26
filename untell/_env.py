"""Best-effort ``.env`` loader.

Lets API keys live in a gitignored ``.env`` file instead of the shell. Uses ``python-dotenv`` when
installed; otherwise a tiny zero-dependency parser handles ``KEY=VALUE`` lines. Real environment
variables always win (we never override an already-set var), so this is safe to call at CLI startup.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_env(path: str | None = None) -> bool:
    """Load ``.env`` (cwd by default) into ``os.environ`` without overriding existing vars.

    Returns True if a file/loader ran, False otherwise.
    """
    try:
        from dotenv import load_dotenv  # python-dotenv, if installed

        # utf-8-sig so a BOM-prefixed .env (common from Windows editors) doesn't corrupt the first key.
        return bool(load_dotenv(path, override=False, encoding="utf-8-sig"))
    except Exception:
        pass

    p = Path(path) if path else Path.cwd() / ".env"
    if not p.is_file():
        return False
    try:
        for raw in p.read_text(encoding="utf-8-sig").splitlines():  # utf-8-sig strips a leading BOM
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key.startswith("export "):  # tolerate `export KEY=VALUE` shell syntax
                key = key[len("export "):].strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:  # real env wins
                os.environ[key] = val
    except Exception:
        return False
    return True
