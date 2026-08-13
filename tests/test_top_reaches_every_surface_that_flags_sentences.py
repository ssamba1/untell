"""`--top` decides which sentences come back flagged, and two of the four surfaces did not have it.

`score_sentences(text, tier, threshold, top)` is the whole of the sentences operation, and `top`
is the knob that says how many sentences to flag. The CLI exposed it. REST modelled `text`, `tier`
and `threshold` only; the MCP tool took the same three. So a client on either of those surfaces
always got the worst-third default and could not ask the question the CLI answers — the same
"answers differently by protocol" gap this repo already closed for `best_of`, `polish`, `confirm`
and `detector_thresholds`.

Bounded on the way in rather than forwarded raw, because a bare int made `order[:top]` a Python
negative slice: measured, `top=-1` flagged 2 of 3 sentences — more than `top=1` — and `top=-5`
flagged none, which reads as "nothing to rewrite". 0 is a meaning ("flag none"), so the low bound
is 0 on every surface.

Adding `_Top` to the API also retires a fallback: `run._bounds("_Top", ...)` had no annotated type
to read and fell back to a literal pair, which is the divergence the shared-bounds indirection
exists to prevent.
"""

from __future__ import annotations

import pytest

TEXT = (
    "Moreover, it is important to note that the system delivers value. "
    "The cat sat on the mat. "
    "Furthermore, this comprehensive solution leverages synergies to unlock potential."
)


class TestTheKnobExistsEverywhere:
    def test_the_library_takes_it(self):
        import inspect

        from untell.scripts.sentences import score_sentences

        assert "top" in inspect.signature(score_sentences).parameters

    def test_the_cli_takes_it(self):
        import inspect

        from untell.scripts import sentences

        assert "--top" in inspect.getsource(sentences.main)

    def test_the_rest_body_takes_it(self):
        pytest.importorskip("fastapi")
        from untell.api_server import SentencesRequest

        assert "top" in SentencesRequest.model_fields

    def test_the_mcp_tool_takes_it(self):
        import inspect

        import untell.mcp_server as mcp

        source = inspect.getsource(mcp._server)
        start = source.index("def sentences(")
        signature = source[start : source.index("-> dict", start)]
        assert "top" in signature, "the MCP sentences tool does not accept top"


class TestTheBoundTravelsWithIt:
    def test_the_rest_field_is_bounded_at_zero(self):
        pytest.importorskip("fastapi")
        from untell import api_server

        low = high = None
        for constraint in api_server._Top.__metadata__[0].metadata:
            low = getattr(constraint, "ge", low)
            high = getattr(constraint, "le", high)
        assert low == 0 and high == 10_000

    def test_the_cli_bound_now_reads_the_api_rather_than_a_fallback(self):
        """The literal pair passed to `_ranged` is a fallback for when the server extra is absent.
        With `_Top` declared, the real bound has to come from the API."""
        pytest.importorskip("fastapi")
        from untell.scripts.run import _bounds

        assert _bounds("_Top", (99, 99)) == (0, 10_000)

    def test_mcp_names_why_a_negative_value_is_not_fewer(self):
        from untell.mcp_server import _bad_args

        assert _bad_args(top=(None, "top")) is None
        assert _bad_args(top=(0, "top")) is None
        assert _bad_args(top=(3, "top")) is None
        bad = _bad_args(top=(-1, "top"))
        assert bad is not None and "slices from the end" in bad["error"]


class TestTheKnobActuallyChangesTheAnswer:
    """A parameter that is accepted and dropped is worse than one that is missing — it reads as
    honoured. Each surface is asked for a different count and has to return it."""

    def test_the_library_honours_it(self):
        from untell.scripts.sentences import score_sentences

        assert len(score_sentences(TEXT, tier="lite", top=0)["flagged"]) == 0
        assert len(score_sentences(TEXT, tier="lite", top=1)["flagged"]) <= 1

    def test_rest_forwards_it_rather_than_dropping_it(self):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient

        from untell.api_server import app

        with TestClient(app) as client:
            none_flagged = client.post("/sentences", json={"text": TEXT, "tier": "lite", "top": 0})
            assert none_flagged.status_code == 200, none_flagged.text
            assert none_flagged.json()["flagged"] == [], "top was accepted and then ignored"

            refused = client.post("/sentences", json={"text": TEXT, "tier": "lite", "top": -1})
            assert refused.status_code == 422, refused.text
