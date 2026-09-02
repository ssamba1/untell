"""Eviction is a no-op at or below the soft cap.

api_server.py:428: `if len(_rate_buckets) <= _RATE_BUCKET_SOFT_CAP: return` —
exactly at the cap (4096 buckets), the stale-bucket eviction does NOT run: a
bucket at the cap boundary is preserved. The mutation <= -> < runs eviction at
exactly 4096, dropping every stale bucket (here, all of them). Pinned at the
module-global level.
"""

import pytest

# `import fastapi` at module scope made this file a COLLECTION ERROR on the lite
# install, which ships zero ML — ten files did, so `pytest -q` was never green on
# the path CONTRIBUTING calls zero-dependency. A skip is the honest outcome: the
# test is not applicable, not broken. Install with `pip install 'untell[server]'`
# to run it.
pytest.importorskip("fastapi")
import untell.api_server as api_server


def test_eviction_noop_at_exact_cap():
    buckets = {f"k{i}": (100.0, 1) for i in range(4095)}
    buckets["stale_key"] = (100.0, 1)  # exactly _RATE_BUCKET_SOFT_CAP = 4096
    assert len(buckets) == api_server._RATE_BUCKET_SOFT_CAP
    api_server._rate_buckets = buckets
    try:
        api_server._evict_stale_buckets(now=200.0)
        assert "stale_key" in api_server._rate_buckets, "stale bucket at exact cap must survive"
        assert len(api_server._rate_buckets) == 4096
    finally:
        api_server._rate_buckets = {}
