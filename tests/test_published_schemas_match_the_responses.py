"""A published schema is a promise a client codes against.

`/tells` returned a `matches` key that `_TELLS_RESPONSES` never declared, so a client generated
from the spec dropped the one field saying WHICH phrases were counted. The same omission had
already been found and fixed for `warning`, one field over — the schema even carries a comment
about it — which is why this is a test and not another one-off correction.

Checks the shape rather than a key list: every endpoint's real response must declare everything it
returns, and return everything it marks required.
"""

from __future__ import annotations

import pytest

# `import fastapi` at module scope made this file a COLLECTION ERROR on the lite
# install, which ships zero ML — ten files did, so `pytest -q` was never green on
# the path CONTRIBUTING calls zero-dependency. A skip is the honest outcome: the
# test is not applicable, not broken. Install with `pip install 'untell[server]'`
# to run it.
pytest.importorskip("fastapi")
