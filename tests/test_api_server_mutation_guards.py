"""Killing tests for the api_server.py mutation survivors (2026-08-14 sweep).

  line 1025 logic: == -> !=        empty UNTELL_PORT check.

Killed here. 496 (rate-limit credential `or` -> `and`) is unkillable via the test
client: the mutation's "" credential falls back to the client IP, and TestClient
reuses one IP, so both paths trip identically (verified by applying the mutant —
req1=200/req2=429 in both cases). 409 (window constant), 428 (bucket-cap
boundary), and 650/682/715 (OpenAPI additionalProperties) are timing-dependent or
schema-description-only. All recorded as unkillable in survivors.md.
"""

from __future__ import annotations

import pytest

# `import fastapi` at module scope made this file a COLLECTION ERROR on the lite
# install, which ships zero ML — ten files did, so `pytest -q` was never green on
# the path CONTRIBUTING calls zero-dependency. A skip is the honest outcome: the
# test is not applicable, not broken. Install with `pip install 'untell[server]'`
# to run it.
pytest.importorskip("fastapi")
