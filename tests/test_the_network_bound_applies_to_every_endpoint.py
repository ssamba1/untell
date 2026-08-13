"""The 50k bound is a network-edge guard, and every endpoint must carry it.

`preserve.lock()` is what justified the bound — 45ms per KB, so a megabyte occupies a worker for
~45 seconds. But the bound is applied to `/tells` and `/scrub` too, which never lock, and that
looked like inheritance rather than a decision. MEASURED, wall-clock per call against input size:

       input     tells    scrub      lock    score
       50 KB    0.413s   0.084s    2.017s   2.132s
      100 KB    1.019s   0.095s    2.854s   1.387s
      200 KB    2.137s   0.193s    5.483s   1.484s

`lock` dominates, and on its own cost `/tells` could carry a far larger bound. It should not: the
work is LINEAR, so a 10 MB body is ~100 seconds of regex on a worker regardless of how cheap the
per-KB figure looks. A bound that some endpoints skip is a bound an attacker picks.

The CLI is deliberately different. It is not a network surface, takes any length, and reports what
it truncated. The asymmetry is the point — one of the two has an untrusted caller.

This pins the property that is easy to lose: a new endpoint added without `_TEXT`, or a model whose
field is retyped, silently drops the guard for that route only.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from untell.scripts.score import MAX_INPUT_CHARS  # noqa: E402

OVERSIZED = "Moreover, the framework leverages robust methods. " * 1200  # ~60k chars
WITHIN = "Moreover, the framework leverages robust methods. " * 20


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    monkeypatch.delenv("UNTELL_API_KEY", raising=False)
    from untell.api_server import app

    with TestClient(app) as c:
        yield c


def _text_endpoints() -> list[tuple[str, int | None]]:
    """(path, declared maxLength) for every POST body carrying `text`.

    Read from the PUBLISHED OpenAPI schema rather than by walking `app.routes`. The first version
    introspected `route.body_field.type_.model_fields`, which is empty on this FastAPI/pydantic
    version — it found zero endpoints, and the parametrized cases below would have run zero times
    and passed. Only the scan-guard caught it. The schema is also the better source on its merits:
    it is what a generated client sees, so a bound missing there is missing for every consumer.
    """
    from untell.api_server import app

    spec = app.openapi()
    out: list[tuple[str, int | None]] = []
    for path, operations in spec["paths"].items():
        body = (operations.get("post") or {}).get("requestBody")
        if not body:
            continue
        ref = body["content"]["application/json"]["schema"].get("$ref", "")
        model = spec["components"]["schemas"].get(ref.rsplit("/", 1)[-1], {})
        properties = model.get("properties", {})
        if "text" in properties:
            out.append((path, properties["text"].get("maxLength")))
    return sorted(out)


def _paths() -> list[str]:
    return [path for path, _limit in _text_endpoints()]


def test_the_scan_finds_the_endpoints() -> None:
    """Guards every case below. An empty list would make the parametrize vacuous."""
    found = _paths()
    assert len(found) >= 5, f"only found {found}"
    for expected in ("/score", "/humanize", "/tells", "/scrub", "/sentences"):
        assert expected in found, f"{expected} not discovered by the schema scan"


def test_the_fixture_is_actually_oversized() -> None:
    assert len(OVERSIZED) > MAX_INPUT_CHARS
    assert len(WITHIN) < MAX_INPUT_CHARS


@pytest.mark.parametrize("path", _paths())
def test_every_text_endpoint_rejects_oversized_input(path: str, client) -> None:
    response = client.post(path, json={"text": OVERSIZED})
    assert response.status_code == 422, (
        f"{path} accepted a {len(OVERSIZED)}-character body (HTTP {response.status_code}); the "
        f"network bound is missing on this route"
    )


@pytest.mark.parametrize("path", _paths())
def test_the_rejection_names_the_field_and_the_limit(path: str, client) -> None:
    """A 422 a caller cannot act on is barely better than a hang. The demo page renders
    `detail[0].msg` verbatim, so this is the sentence a user reads."""
    detail = client.post(path, json={"text": OVERSIZED}).json().get("detail")
    assert isinstance(detail, list) and detail, f"{path}: no detail to render"
    assert "text" in str(detail[0].get("loc")), f"{path}: error does not name the field"
    assert str(MAX_INPUT_CHARS) in str(detail[0].get("msg")), (
        f"{path}: error does not name the limit: {detail[0].get('msg')!r}"
    )


@pytest.mark.parametrize("path,limit", _text_endpoints())
def test_the_published_schema_declares_the_bound(path: str, limit: int | None) -> None:
    """The contract, not just the behaviour. A client generated from this spec should refuse
    oversized input before spending a round trip on it."""
    assert limit == MAX_INPUT_CHARS, (
        f"{path} declares maxLength={limit!r} in the OpenAPI schema, expected {MAX_INPUT_CHARS}"
    )


def test_input_within_the_bound_is_not_rejected(client) -> None:
    """Guards the guard. A route that rejected everything would pass every case above."""
    response = client.post("/tells", json={"text": WITHIN})
    assert response.status_code == 200, response.text[:200]
