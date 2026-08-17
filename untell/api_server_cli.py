"""Console-script entry for the REST server (``untell-server``).

``untell-server`` is a console script whose target, ``untell.api_server:main``,
lives in a module that imports FastAPI at module scope. On a base install (no
``[server]`` extra) that import fails *before* ``main`` can print anything, and
the console shim — ``from untell.api_server import main`` — leaks a full
traceback and exits 1 with no indication of which extra supplies the missing
package.

This thin wrapper sits in front of the module so the *console* surface fails
cleanly — a one-line message naming the extra and a documented exit code — while
library callers of ``untell.api_server`` still get the deliberate
``ImportError`` they ``try``/``except`` (the module's own guard keeps that
contract: an ``ImportError`` a caller can catch, never a ``SystemExit``).
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    """Run the REST server, or fail cleanly when FastAPI (``.[server]``) is absent."""
    try:
        from untell.api_server import main as _server_main
    except ImportError as exc:  # pragma: no cover - exercised on a base install
        msg = str(exc) or "the untell[server] extra is not installed"
        print(f"ERROR: {msg}", file=sys.stderr)
        return 2
    return int(_server_main(argv))


if __name__ == "__main__":  # pragma: no cover - console-script shims import main()
    sys.exit(main())
