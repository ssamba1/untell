"""Best-effort ``.env`` loader.

Lets API keys live in a gitignored ``.env`` file instead of the shell. Uses ``python-dotenv`` when
installed; otherwise a tiny zero-dependency parser handles ``KEY=VALUE`` lines. Real environment
variables always win (we never override an already-set var), so this is safe to call at CLI startup.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


_COMMENT = re.compile(r"\s+#.*$")


def _parse_value(raw: str) -> str:
    """Parse the right-hand side of a ``KEY=VALUE`` line the way python-dotenv does.

    Which parser runs depends only on whether an optional dependency is installed, so any
    disagreement means the same .env file configures the program two different ways. MEASURED
    across eight representative lines, exactly one diverged: an inline comment on an unquoted
    value.

        SOME_API_KEY=abc123 # the prod key
          python-dotenv -> "abc123"
          this fallback -> "abc123 # the prod key"

    A key with trailing junk fails auth at the remote end, and nothing in that error names the
    .env file as the cause. A quoted value keeps its ``#`` — inside quotes it is data, not a
    comment — which is why the comment strip has to happen before unquoting, not after.
    """
    val = raw.strip()
    if val and val[0] in "\"'":
        # Close on the MATCHING quote, not on the end of the line: `KEY="abc" # note` is a quoted
        # value with a comment after it, and anchoring to the last character left the quotes in.
        end = val.find(val[0], 1)
        if end != -1:
            return val[1:end]
    return _COMMENT.sub("", val).strip()


def load_env(path: str | None = None) -> bool:
    """Load ``.env`` (cwd by default) into ``os.environ`` without overriding existing vars.

    Returns True if a file was found and parsed, False otherwise.
    """
    # Resolve the path here rather than letting python-dotenv do it. Bare ``load_dotenv()``
    # searches *upward from the calling file*, which is this module inside the installed package —
    # so with python-dotenv present it walks site-packages' parents and never sees the caller's
    # cwd, silently ignoring the .env the docs tell users to create. Without python-dotenv the
    # fallback below reads cwd correctly, so the optional dependency was what broke it.
    p = Path(path) if path else Path.cwd() / ".env"
    if not p.is_file():
        return False

    try:
        from dotenv import load_dotenv  # python-dotenv, if installed

        # utf-8-sig so a BOM-prefixed .env (common from Windows editors) doesn't corrupt the first key.
        load_dotenv(str(p), override=False, encoding="utf-8-sig")
        return True
    except Exception:
        pass

    try:
        for raw in p.read_text(encoding="utf-8-sig").splitlines():  # utf-8-sig strips a leading BOM
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key.startswith("export "):  # tolerate `export KEY=VALUE` shell syntax
                key = key[len("export "):].strip()
            val = _parse_value(val)
            if key and key not in os.environ:  # real env wins
                os.environ[key] = val
    except Exception:
        return False
    return True
