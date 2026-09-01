"""Every endpoint's advertised response schema must match what it actually returns.

A client generating types from the OpenAPI document sees exactly the fields listed there. `/humanize`
grew `seed`, `tells_before` and `tells_after` and its schema did not, so a generated client could
not see them at all — the same drift `docs/result-shapes.md` had in the same week, and for the same
reason: a surface that enumerates fields cannot be left to catch up on its own, because nothing
complains.

Swept all seven endpoints after fixing that one. MEASURED — the drift was confined to `/humanize`:

    endpoint     schema   returned   undocumented
    /score          13       11           0
    /tells          10        8           0
    /sentences       6        6           0
    /scrub           2        2           0
    /verify          7        6           0
    /ceiling        22       22           0
    /humanize       20       18           0   (after the fix; 3 before)

The gaps in the middle column are all CONDITIONAL fields — `detector_errors` when a detector
fails, `matches` when the caller asks for them, the three `*_warning` fields when their condition
holds. Those are exempt from the "must be returned" direction only: demanding them on every
response would assert that every run has something wrong with it.

Both directions are checked for every endpoint, so the next field added anywhere fails here rather
than reaching a client that cannot see it.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="needs the [server] extra")

from fastapi.testclient import TestClient  # noqa: E402

from untell.api_server import app  # noqa: E402

TEXT = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "Furthermore, it significantly improves overall efficiency across the evaluated corpus."
)

# Cheapest valid request per endpoint.
REQUESTS = {
    "/score": {"text": TEXT, "tier": "lite"},
    "/tells": {"text": TEXT},
    "/sentences": {"text": TEXT, "tier": "lite"},
    "/scrub": {"text": TEXT},
    "/verify": {"text": TEXT, "tier": "lite"},
    "/ceiling": {"tier": "lite", "n": 1, "max_iters": 1, "best_of": 1},
    "/humanize": {"text": TEXT, "tier": "lite", "max_iters": 1, "best_of": 1},
}

# Documented but present only when their condition holds.
#
# `unrankable` is the newest: /sentences sets it when its own per-sentence scores span less than
# 0.05, which happens when a detector is at its ceiling on every sentence. Like the rest, it is
# absent on ordinary input, so demanding it on every response would assert that every document has
# an unrankable ranking.
CONDITIONAL = {
    "warning", "voice_warning", "rewriter_warning", "error",
    "detector_errors", "failed_detectors", "matches", "suggestion",
    "out_of_range_detectors", "out_of_range_raw", "unrankable",
    # Returned by /sentences only when the request sets `evidence: true`. It is declared in the
    # schema on purpose — an undeclared field is the round-25 defect, where /score returned
    # `agreement` for several releases with nothing in the schema saying so, and a generated client
    # had no entry for the one field the tool exists to surface.
    "evidence_note",
}


@pytest.fixture(scope="module")
def client():
    # A module-scoped MonkeyPatch, undone in teardown — NOT os.environ.setdefault, which leaves the
    # variable set for the rest of the PROCESS. That leak made every later test in a combined run
    # score on the stdlib path: score_sentences began returning its targeting `warning` when run
    # together and not alone, and the failure surfaced three files away from its cause.
    patch = pytest.MonkeyPatch()
    patch.setenv("UNTELL_LITE_NO_TORCH", "1")
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        patch.undo()


@pytest.fixture(scope="module")
def spec(client) -> dict:
    return client.get("/openapi.json").json()


def _schema_properties(spec: dict, path: str) -> dict:
    node = spec["paths"].get(path, {}).get("post", {})
    content = node.get("responses", {}).get("200", {}).get("content", {}).get("application/json", {})
    schema = content.get("schema", {})
    if "$ref" in schema:
        schema = spec["components"]["schemas"][schema["$ref"].rsplit("/", 1)[-1]]
    return schema.get("properties", {})


def _response(client, path: str) -> dict:
    result = client.post(path, json=REQUESTS[path])
    assert result.status_code == 200, f"{path} -> {result.status_code}: {result.text[:200]}"
    return result.json()


def test_every_post_endpoint_is_covered(spec):
    """The guard. An endpoint added without an entry is one nobody checks the schema of."""
    posts = {
        path for path, node in spec["paths"].items()
        if "post" in node and not path.startswith(("/docs", "/openapi", "/redoc"))
    }
    assert not posts - set(REQUESTS), f"no request here for {sorted(posts - set(REQUESTS))}"


@pytest.mark.parametrize("path", sorted(REQUESTS))
def test_the_schema_enumerates_fields(spec, path: str):
    """Guards the guard: an empty schema passes both directions trivially."""
    assert len(_schema_properties(spec, path)) >= 2, path


@pytest.mark.parametrize("path", sorted(REQUESTS))
def test_every_promised_field_is_returned(client, spec, path: str):
    promised = set(_schema_properties(spec, path)) - CONDITIONAL
    missing = sorted(promised - set(_response(client, path)))
    assert not missing, f"{path} advertises fields it does not return: {missing}"


@pytest.mark.parametrize("path", sorted(REQUESTS))
def test_every_returned_field_is_in_the_schema(client, spec, path: str):
    """The direction that drifted. A generated client cannot use a field it was never told about."""
    undocumented = sorted(set(_response(client, path)) - set(_schema_properties(spec, path)))
    assert not undocumented, (
        f"{path} returns fields the schema does not list: {undocumented}. Add them to the "
        "endpoint's response schema rather than deleting this assertion."
    )


@pytest.mark.parametrize("field", ["seed", "tells_before", "tells_after"])
def test_the_recently_added_humanize_fields_are_advertised(spec, field: str):
    """Named individually because these are the three that were missing when this was written."""
    assert field in _schema_properties(spec, "/humanize")
