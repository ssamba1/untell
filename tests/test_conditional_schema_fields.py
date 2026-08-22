"""Conditional response fields that existed in responses but not in the OpenAPI schema.

Three defects found by driving paths the standard CALLS table never exercises:

1. ``out_of_range_detectors`` / ``out_of_range_raw`` — score.py emits them when a detector
   returns a value outside [0, 1]. They were in CONDITIONAL (the known-missing list) but
   completely absent from ``_SCORE_RESPONSES``. A client generated from the spec had no entry
   for them, so a response carrying them looked like a contract violation.

2. ``suggestion`` — run.py emits it when the loop exhausts max_iters at the full tier with a
   rule-based rewriter. Same omission from ``_HUMANIZE_RESPONSES``.

3. MCP ``untell`` tool: ``detector_thresholds`` values are not range-checked. A value above 1
   can never be reached by a detector score (scores are probabilities in [0, 1]), so
   ``detector_thresholds={"hc3_roberta": 50}`` silently defeats the per-detector gate —
   exactly the same defect as ``threshold=50``, which ``_bad_args`` already refuses.

MEASURED (failing test, then fix): all three drove the paths, found the gaps,
and the schema / guard additions made them pass.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("fastapi", reason="needs the [server] extra")

from fastapi.testclient import TestClient  # noqa: E402

from untell.api_server import app  # noqa: E402

TEXT = (
    "Moreover, the framework leverages a robust approach to delivery at scale. "
    "Furthermore, it is important to note that this underscores the pivotal integration."
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _schema_props(path: str, method: str = "post") -> dict:
    return (
        app.openapi()["paths"][path][method]["responses"]["200"]["content"][
            "application/json"
        ]["schema"].get("properties", {})
    )


# ---------------------------------------------------------------------------
# Defect 1: out_of_range_detectors / out_of_range_raw missing from /score schema
# ---------------------------------------------------------------------------


def _score_resp_with_out_of_range():
    """Make /score return a response that includes out_of_range_* by injecting
    a mocked score_text result."""
    with patch("untell.api_server.score_text") as mock_score:
        mock_score.return_value = {
            "tier": "lite",
            "tier_requested": "lite",
            "detectors": {"perplexity_burstiness": 1.0},
            "max": 1.0,
            "mean": 1.0,
            "ai_percent": 100.0,
            "threshold": 0.3,
            "verdict_threshold": 0.45,
            "flagged": True,
            "out_of_range_detectors": ["perplexity_burstiness"],
            "out_of_range_raw": {"perplexity_burstiness": 1.42},
        }
        return TestClient(app).post("/score", json={"text": TEXT, "tier": "lite"})


def test_score_passes_out_of_range_detectors_to_caller():
    """score.py emits the field; /score must not silently drop it."""
    body = _score_resp_with_out_of_range().json()
    assert "out_of_range_detectors" in body, (
        "score_text returned out_of_range_detectors but the /score response dropped it"
    )
    assert "out_of_range_raw" in body, (
        "score_text returned out_of_range_raw but the /score response dropped it"
    )


def test_out_of_range_detectors_field_is_in_the_score_schema():
    """`out_of_range_detectors` was in CONDITIONAL (the known-conditional list used by
    `test_no_documented_field_is_stale`) but not in the OpenAPI schema itself.

    A client generating types from /openapi.json never saw this field. Adding it to
    CONDITIONAL says "we know it can be absent on a normal call" — that is correct.
    But it must ALSO appear in the schema's properties, or a generated client has no
    entry for it at all and cannot act on the information.
    """
    props = _schema_props("/score")
    assert "out_of_range_detectors" in props, (
        "out_of_range_detectors is not declared in _SCORE_RESPONSES. "
        "It is in CONDITIONAL (which allows its absence) but omitted from properties "
        "entirely — a generated client cannot see it."
    )
    assert "out_of_range_raw" in props, (
        "out_of_range_raw is not declared in _SCORE_RESPONSES."
    )


def test_out_of_range_raw_has_numeric_values_in_the_schema():
    """The description must tell a caller the values are floats, not strings."""
    props = _schema_props("/score")
    if "out_of_range_raw" not in props:
        pytest.skip("field not in schema yet")
    raw_schema = props["out_of_range_raw"]
    # Either additionalProperties: number or items: number — the values are floats.
    assert raw_schema.get("type") == "object", raw_schema
    ap = raw_schema.get("additionalProperties", {})
    assert ap.get("type") == "number", f"out_of_range_raw values should be number, got {ap}"


# ---------------------------------------------------------------------------
# Defect 2: suggestion missing from /humanize schema
# ---------------------------------------------------------------------------


def _humanize_resp_with_suggestion():
    """Make /humanize return a response that includes `suggestion`."""
    with patch("untell.api_server.untell_text") as mock_untell:
        mock_untell.return_value = {
            "final": TEXT,
            "pre": {"max": 0.9, "detectors": {}, "tier": "full", "tier_requested": "full",
                    "mean": 0.9, "ai_percent": 90.0, "threshold": 0.3,
                    "verdict_threshold": 0.45, "flagged": True},
            "post": {"max": 0.85, "detectors": {}, "tier": "full", "tier_requested": "full",
                     "mean": 0.85, "ai_percent": 85.0, "threshold": 0.3,
                     "verdict_threshold": 0.45, "flagged": True,
                     "flagged_sentences": [], "style": None},
            "iterations": 5,
            "rewrites": 5,
            "adopted": 1,
            "changed": False,
            "similarity": 1.0,
            "sim_bar": 0.85,
            "quality_metric": "nli",
            "meaning_gate": "nli",
            "tier": "full",
            "flagged": True,
            "stopped": "max_iters",
            "rewriter": "surgical",
            "seed": 42,
            "tells_before": 3,
            "tells_after": 2,
            "suggestion": (
                "still flagged with rewriter='surgical'. Try --rewriter neural."
            ),
        }
        return TestClient(app).post(
            "/humanize",
            json={"text": TEXT, "tier": "lite", "max_iters": 1, "best_of": 1},
        )


def test_humanize_passes_suggestion_to_caller():
    """run.py emits `suggestion` when still flagged; /humanize must not drop it."""
    body = _humanize_resp_with_suggestion().json()
    assert "suggestion" in body, (
        "untell_text returned suggestion but the /humanize response dropped it"
    )


def test_suggestion_field_is_in_the_humanize_schema():
    """`suggestion` was in CONDITIONAL but absent from _HUMANIZE_RESPONSES.properties.

    Same shape as `out_of_range_*` on /score: CONDITIONAL says "may be absent on a
    normal call", which is correct (it only appears when still flagged). But the field
    must still appear in the schema so a generated client knows it exists.
    """
    props = _schema_props("/humanize")
    assert "suggestion" in props, (
        "suggestion is not declared in _HUMANIZE_RESPONSES. "
        "It is in CONDITIONAL but absent from the schema properties — "
        "run.py emits it when the loop exhausts max_iters still flagged."
    )


# ---------------------------------------------------------------------------
# Defect 3: MCP detector_thresholds values unvalidated
# ---------------------------------------------------------------------------


def _mcp_tools():
    """Register MCP tools using a minimal fake FastMCP and return them by name."""
    import sys
    import types

    recorded = {}

    class _FakeServer:
        def tool(self, *a, **k):
            def deco(fn):
                recorded[fn.__name__] = fn
                return fn
            return deco

    fake = types.ModuleType("mcp.server.fastmcp")
    fake.FastMCP = lambda name: _FakeServer()
    saved = {k: sys.modules.get(k) for k in ("mcp", "mcp.server", "mcp.server.fastmcp")}
    sys.modules["mcp"] = types.ModuleType("mcp")
    sys.modules["mcp.server"] = types.ModuleType("mcp.server")
    sys.modules["mcp.server.fastmcp"] = fake
    try:
        import untell.mcp_server as m
        m._server()
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return recorded


class TestMcpDetectorThresholdsValidation:
    """`detector_thresholds` values were never validated in the MCP `untell` tool.

    A value above 1 can never be reached by a detector score (all scores are
    probabilities in [0, 1]), so ``detector_thresholds={"hc3_roberta": 50}`` silently
    makes the hc3_roberta gate unreachable — the text would always pass for that detector,
    even at score=1.0. MEASURED: the same input reaches the loop, the per-detector check
    compares score (e.g. 0.99) against threshold (50), 0.99 < 50 → passes, no error.

    The global `threshold` parameter already refuses values above 1 via `_bad_args`
    ("outside [0, 1]"). Per-detector thresholds must be probabilities for the same reason.
    """

    def test_a_value_above_one_in_detector_thresholds_is_refused(self):
        fn = _mcp_tools()["untell"]
        result = fn(
            text=TEXT, tier="lite",
            detector_thresholds={"hc3_roberta": 50.0},
        )
        assert "error" in result, (
            "detector_thresholds={'hc3_roberta': 50.0} was accepted — "
            "a threshold above 1 can never be reached by a detector score"
        )
        assert "50" in result["error"] or "outside" in result["error"] or "probability" in result["error"], (
            f"error message doesn't mention the invalid value: {result['error']!r}"
        )

    def test_a_negative_value_in_detector_thresholds_is_refused(self):
        fn = _mcp_tools()["untell"]
        result = fn(
            text=TEXT, tier="lite",
            detector_thresholds={"perplexity_burstiness": -0.5},
        )
        assert "error" in result, "negative threshold should be refused"

    def test_a_non_numeric_value_in_detector_thresholds_is_refused(self):
        fn = _mcp_tools()["untell"]
        result = fn(
            text=TEXT, tier="lite",
            detector_thresholds={"hc3_roberta": "high"},
        )
        assert "error" in result, "a string value should be refused"

    def test_valid_detector_thresholds_pass_through(self):
        """The guard must not fire on valid inputs."""
        fn = _mcp_tools()["untell"]
        result = fn(
            text=TEXT, tier="lite", max_iters=1,
            detector_thresholds={"perplexity_burstiness": 0.5},
        )
        assert "error" not in result, (
            f"valid detector_thresholds raised an error: {result.get('error')}"
        )

    def test_none_detector_thresholds_passes_through(self):
        """None is the documented default — must not be treated as a validation error."""
        fn = _mcp_tools()["untell"]
        result = fn(text=TEXT, tier="lite", max_iters=1, detector_thresholds=None)
        assert "error" not in result, result.get("error")

    def test_empty_detector_thresholds_passes_through(self):
        """An empty dict is valid — no per-detector overrides applied."""
        fn = _mcp_tools()["untell"]
        result = fn(text=TEXT, tier="lite", max_iters=1, detector_thresholds={})
        assert "error" not in result, result.get("error")
