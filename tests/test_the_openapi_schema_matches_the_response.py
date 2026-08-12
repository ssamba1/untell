"""The advertised response schema must match what the endpoint actually returns.

`/humanize` publishes a response schema in the OpenAPI document, and a client generating types from
it gets exactly the fields listed there. The loop grew three fields — `seed`, `tells_before`,
`tells_after` — and the schema did not, so a generated client could not see them at all.

That is the same drift `docs/result-shapes.md` had in the same week, for the same reason: a
surface that enumerates fields cannot be left to catch up on its own, because nothing complains.
The prose reference had a test checking one direction; this one had no test at all.

Checked both ways here:

  * every field the schema promises is really returned — otherwise the document lies
  * every field returned is in the schema — otherwise callers cannot use it

Conditional fields are exempt from the first direction only. `warning`, `voice_warning` and
`rewriter_warning` appear when their condition holds, and demanding them on every response would
mean asserting that every run has something wrong with it.
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

# Present only when their condition holds.
CONDITIONAL = {"warning", "voice_warning", "rewriter_warning", "error", "detector_errors",
               "suggestion"}


@pytest.fixture(scope="module")
def client():
    import os

    os.environ.setdefault("UNTELL_LITE_NO_TORCH", "1")
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def humanize_schema(client) -> dict:
    spec = client.get("/openapi.json").json()
    responses = spec["paths"]["/humanize"]["post"]["responses"]
    ok = responses["200"]["content"]["application/json"]["schema"]
    if "$ref" in ok:
        name = ok["$ref"].rsplit("/", 1)[-1]
        ok = spec["components"]["schemas"][name]
    return ok.get("properties", {})


@pytest.fixture(scope="module")
def humanize_response(client) -> dict:
    response = client.post(
        "/humanize",
        json={"text": TEXT, "tier": "lite", "max_iters": 1, "best_of": 1},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_the_schema_has_properties(humanize_schema):
    """Guards the guard: an empty schema would make both directions pass trivially."""
    assert len(humanize_schema) >= 8, sorted(humanize_schema)


def test_every_promised_field_is_returned(humanize_schema, humanize_response):
    promised = set(humanize_schema) - CONDITIONAL
    missing = sorted(promised - set(humanize_response))
    assert not missing, f"the schema advertises fields /humanize does not return: {missing}"


def test_every_returned_field_is_in_the_schema(humanize_schema, humanize_response):
    """The direction that drifted. A generated client cannot use a field it was never told about."""
    undocumented = sorted(set(humanize_response) - set(humanize_schema))
    assert not undocumented, (
        f"/humanize returns fields the schema does not list: {undocumented}. Add them to "
        "_HUMANIZE_RESPONSES rather than deleting this assertion."
    )


@pytest.mark.parametrize("field", ["seed", "tells_before", "tells_after"])
def test_the_recently_added_fields_are_advertised(field: str, humanize_schema):
    """Named individually because these are the three that were missing when this was written."""
    assert field in humanize_schema, sorted(humanize_schema)
