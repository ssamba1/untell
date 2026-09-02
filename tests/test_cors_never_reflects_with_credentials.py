"""A wildcard origin must never be paired with credentials.

`allow_origins=["*"]` with `allow_credentials=True` is the combination the CORS spec forbids, and
Starlette implements the forbidden case by REFLECTING the request's Origin header rather than
sending `*` — because `*` is invalid alongside credentials. Reflection means any page the user is
visiting can call this server cross-origin with credentials attached and read the response.

This server ships an `UNTELL_API_KEY` auth path and runs on localhost by default, so that is a
browser tab away from someone else's text.
"""

from __future__ import annotations

import pytest

# `import fastapi` at module scope made this file a COLLECTION ERROR on the lite
# install, which ships zero ML — ten files did, so `pytest -q` was never green on
# the path CONTRIBUTING calls zero-dependency. A skip is the honest outcome: the
# test is not applicable, not broken. Install with `pip install 'untell[server]'`
# to run it.
pytest.importorskip("fastapi")
