"""Which rewriters run without an API key — one definition, two servers.

This frozenset decides what an unauthenticated caller may ask for, and it was **written out twice**
— once in `api_server.py`, once in `mcp_server.py`. They agreed when this module was created, and
nothing made them. A rewriter added to one surface and forgotten on the other is not a crash: it is
one server accepting a name the other rejects with a 422, which is the quiet kind of drift the
demo-UI tests in `tests/test_docs_claims.py` were already written to catch on the HTML side.

It lives in its own module rather than beside either server because a set of strings should be
readable without installing a web framework. `import untell.api_server` needs FastAPI, so a test
checking nothing more than "does the demo offer a free rewriter" was a **collection error** on the
zero-dependency install that CONTRIBUTING advertises.
"""

from __future__ import annotations

FREE_REWRITERS = frozenset({
    "surgical",
    "structural",
    "composite",
    "targeted",
    "neural",
    "ensemble",
    "max",
    "t5_paraphrase",
    "mt_pivot",
})
