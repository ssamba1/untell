"""A lone surrogate in the text must not crash the preserve lock / NER pass.

Fuzz-found: `preserve._spacy_entity_spans_impl` guards against a missing model, a broken
import, and >1MB text — but not against lone surrogates (U+D800..U+DFFF). spaCy's tokenizer
utf-8-encodes tokens to hash them, and a surrogate has no UTF-8 form, so `nlp(text)` raised
UnicodeEncodeError. It cannot arrive via UTF-8 stdin/files/argv (all validated elsewhere),
but it CAN arrive as a JSON-escaped `"\ud800"` in a REST body or from a library caller.
MEASURED on this slice: POST /humanize with one surrogate in the text -> HTTP 500
Internal Server Error (network-reachable crash); `untell-explain` on the same text -> exit 1
with a spacy traceback.

The fix replaces surrogates with U+FFFD before the NER pass: both are single characters, so
entity offsets stay valid against the ORIGINAL text, and locked spans are sliced from the
original — the caller's text is never altered, only what the model sees.
"""

from __future__ import annotations

import pytest

from untell.scripts import preserve
from untell.scripts.explain import explain_spans

SURROGATE_TEXT = "Furthermore, AI \ud800 transforms industries. See Smith (2020); it cost $500."


def test_spacy_entity_pass_survives_a_lone_surrogate():
    """The NER pass must not raise on a surrogate (with or without the model installed)."""
    spans = preserve._spacy_entity_spans(SURROGATE_TEXT)
    assert isinstance(spans, list)
    for start, end in spans:
        assert 0 <= start < end <= len(SURROGATE_TEXT)


def test_lock_survives_a_lone_surrogate_and_keeps_other_locks():
    """A number after the surrogate must still be locked, at the correct offsets."""
    masked, mapping = preserve.lock(SURROGATE_TEXT)
    assert "$500" in mapping.values()
    assert "Smith (2020)" in mapping.values()


def test_explain_survives_a_lone_surrogate():
    """untell-explain's engine must not raise on a surrogate either."""
    rows = explain_spans(SURROGATE_TEXT)
    spans = [r["span"] for r in rows]
    assert "$500" in spans


def test_the_original_text_is_not_altered():
    """The fix is internal to the NER pass: the caller's string stays byte-identical."""
    before = SURROGATE_TEXT
    preserve._spacy_entity_spans(before)
    assert before == SURROGATE_TEXT


def test_api_rejects_a_surrogate_body_with_422_not_500():
    """POST /humanize with a JSON-escaped lone surrogate must be a clean 422.

    Fuzz-found: pydantic correctly rejects the string (`string_unicode`), but the 422
    detail echoed the raw surrogate, which JSONResponse cannot utf-8-encode — the refusal
    itself 500'd. The detail must render, and name the field.
    """
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from untell.api_server import app

    client = TestClient(app, raise_server_exceptions=False)
    body = b'{"text": "Furthermore, AI \\ud800 transforms industries.", "tier": "lite", ' \
           b'"rewriter": "surgical", "max_iters": 1, "best_of": 1}'
    resp = client.post("/humanize", content=body, headers={"Content-Type": "application/json"})
    assert resp.status_code == 422, f"expected 422, got {resp.status_code}: {resp.text[:120]}"
    data = resp.json()  # the body must parse
    locs = [tuple(e.get("loc", ())) for e in data["detail"]]
    assert ("body", "text") in locs
