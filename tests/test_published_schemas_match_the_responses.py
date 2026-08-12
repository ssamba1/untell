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
from fastapi.testclient import TestClient

from untell import api_server
from untell.api_server import app

client = TestClient(app)

TEXT = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "Furthermore, it significantly improves overall efficiency across the evaluated corpus."
)

# (schema constant, method, path, request body)
CASES = [
    ("_SCORE_RESPONSES", "post", "/score", {"text": TEXT, "tier": "lite"}),
    ("_TELLS_RESPONSES", "post", "/tells", {"text": TEXT}),
    ("_TELLS_RESPONSES", "post", "/tells", {"text": TEXT, "include_matches": True}),
    ("_SENTENCES_RESPONSES", "post", "/sentences", {"text": TEXT, "tier": "lite"}),
    ("_VERIFY_RESPONSES", "post", "/verify", {"text": TEXT, "tier": "lite"}),
    ("_HEALTH_RESPONSES", "get", "/health", None),
]


def _schema(name: str) -> dict:
    responses = getattr(api_server, name)
    return responses[200]["content"]["application/json"]["schema"]


def _call(method: str, path: str, body: dict | None):
    response = client.get(path) if method == "get" else client.post(path, json=body)
    assert response.status_code == 200, f"{path}: {response.status_code} {response.text[:200]}"
    return response.json()


@pytest.mark.parametrize(
    ("name", "method", "path", "body"),
    CASES,
    ids=[f"{c[2]}{'+matches' if (c[3] or {}).get('include_matches') else ''}" for c in CASES],
)
def test_every_returned_key_is_declared(name, method, path, body):
    """The defect: `matches` was returned and undeclared."""
    declared = set(_schema(name).get("properties", {}))
    returned = set(_call(method, path, body))
    assert not (returned - declared), (
        f"{path} returns keys the schema does not declare: {sorted(returned - declared)}"
    )


@pytest.mark.parametrize(
    ("name", "method", "path", "body"),
    CASES,
    ids=[f"{c[2]}{'+matches' if (c[3] or {}).get('include_matches') else ''}" for c in CASES],
)
def test_every_required_key_is_returned(name, method, path, body):
    """The other direction: a schema may not promise a key the endpoint omits."""
    required = set(_schema(name).get("required", []))
    returned = set(_call(method, path, body))
    assert not (required - returned), (
        f"{path} omits keys its schema marks required: {sorted(required - returned)}"
    )


def test_a_conditional_key_is_declared_but_not_required():
    """`matches` appears only with include_matches=true, so requiring it would be a false promise."""
    schema = _schema("_TELLS_RESPONSES")
    assert "matches" in schema["properties"]
    assert "matches" not in schema.get("required", [])
    assert "matches" not in _call("post", "/tells", {"text": TEXT})
    assert "matches" in _call("post", "/tells", {"text": TEXT, "include_matches": True})
