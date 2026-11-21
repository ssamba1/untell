"""The audit commands over REST and MCP, and the refusals that keep those surfaces safe."""

from __future__ import annotations

import pytest

from untell.evidence.service import RefusedSpec, brief_payload, safe_scorer, stability_payload

TEXT = ('We met on a Tuesday. She said "it\'s fine" -- and it was... mostly. '
        "The second paragraph is here so that the layout edits have something to do.")


@pytest.mark.parametrize("spec", ["cmd:rm -rf /", "manual:/etc/passwd"])
def test_network_surfaces_refuse_command_and_file_specs(spec):
    with pytest.raises(RefusedSpec):
        safe_scorer(spec, None, None, allow_commercial=True)


def test_commercial_needs_operator_opt_in():
    with pytest.raises(RefusedSpec, match="credit"):
        safe_scorer("gptzero", None, None, allow_commercial=False)


def test_inline_scores_drive_a_full_brief():
    scores = {"base": 91, "N1": 0.12, "N3": 0.88, "N4": 0.9, "N5": 0.2}
    b = brief_payload(TEXT, scores=scores, name="turnitin", documents=8)
    null = b["stability"]["summary"]["null"]
    assert b["stability"]["base"]["flagged"] is True
    assert null["flips"] == 2
    assert b["detector"]["name"] == "turnitin" and b["published_rates"]
    assert TEXT not in str(b)


def test_inline_scores_reject_nonsense():
    with pytest.raises(RefusedSpec):
        stability_payload(TEXT, scores={"base": 250})


def test_rest_endpoints():
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from untell.api_server import app

    c = TestClient(app)
    r = c.post("/variants", json={"text": TEXT})
    assert r.status_code == 200 and r.json()["variants"]
    r = c.post("/stability", json={"text": TEXT, "detector": "cmd:id"})
    assert r.status_code == 400 and "CLI-only" in r.json()["error"]
    r = c.post("/brief", json={"text": TEXT, "scores": {"base": 0.9, "N1": 0.1}, "name": "gptzero"})
    assert r.status_code == 200 and r.json()["kind"] == "untell.evidence_brief"
    r = c.post("/stability", json={"text": TEXT, "detector": "local:lite"})
    assert r.status_code == 200 and "finding" in r.json()["summary"]


def test_mcp_tools_registered():
    pytest.importorskip("mcp.server.fastmcp")
    from untell.mcp_server import _TOOL_NAMES
    assert {"variants", "stability", "brief", "flagmath"} <= set(_TOOL_NAMES)
