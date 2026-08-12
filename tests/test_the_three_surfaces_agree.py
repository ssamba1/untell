"""The same request must get the same answer whichever surface it arrives on.

This repository has the scar four times over: `best_of` moved to 3 on the CLI while MCP and REST
stayed on 1, so identical requests got a measurably weaker result by protocol (0.601 -> 0.293 with
33% still flagged, against 0.601 -> 0.256 with 0%). `polish`, `confirm` and `detector_thresholds`
each had a version of the same drift, and `tier` on the MCP `score` tool ran a single heuristic
where REST ran the four-detector ensemble.

MEASURED knob by knob across library, CLI, MCP and REST:

  * results agree — the same text and explicit arguments give one number on all three
  * defaults agree on tier, threshold, max_iters, best_of, style, polish, seed
  * MCP was missing exactly two knobs REST models: `confirm` and `detector_thresholds`

The five knobs absent from BOTH remote surfaces (browser, progress, scrub, sim_bar,
veto_contradictions) are a deliberate line — they drive Playwright, write to stdout, or are
internals — so the gap really was those two, both of which change the verdict.
"""
from __future__ import annotations

import inspect
import sys
from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi", reason="needs the [server] extra")

TEXT = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "It significantly improves overall efficiency across the evaluated corpus."
)

# Absent from MCP and REST alike, on purpose.
LIBRARY_ONLY = {"browser", "progress", "scrub", "sim_bar", "veto_contradictions"}


@pytest.fixture(scope="module")
def mcp_tools() -> dict:
    captured: dict = {}

    class _FakeFastMCP:
        def __init__(self, *a, **k):
            pass

        def tool(self, *a, **k):
            def deco(fn):
                captured[fn.__name__] = fn
                return fn

            return deco

        def run(self, *a, **k):
            pass

    fastmcp = MagicMock()
    fastmcp.FastMCP = _FakeFastMCP
    server = MagicMock()
    server.fastmcp = fastmcp
    mcp = MagicMock()
    mcp.server = server

    saved = {n: sys.modules.get(n) for n in
             ("mcp", "mcp.server", "mcp.server.fastmcp", "untell.mcp_server")}
    for name, mod in (("mcp", mcp), ("mcp.server", server), ("mcp.server.fastmcp", fastmcp)):
        sys.modules[name] = mod
    sys.modules.pop("untell.mcp_server", None)
    try:
        import untell.mcp_server as mcp_server

        mcp_server._server()
        yield captured
    finally:
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod


def test_the_same_text_scores_the_same_on_every_surface(mcp_tools):
    from fastapi.testclient import TestClient

    from untell.api_server import app
    from untell.scripts.score import score_text

    library = score_text(TEXT, tier="lite", threshold=0.30)["max"]
    mcp = mcp_tools["score"](text=TEXT, tier="lite", threshold=0.30)["max"]
    rest = TestClient(app).post(
        "/score", json={"text": TEXT, "tier": "lite", "threshold": 0.30}
    ).json()["max"]

    assert library == mcp == rest, f"library={library} mcp={mcp} rest={rest}"


@pytest.mark.parametrize(
    "knob", ["tier", "threshold", "max_iters", "best_of", "style", "polish", "seed", "confirm"]
)
def test_the_default_is_the_same_on_every_surface(mcp_tools, knob: str):
    """Defaults are what a caller gets without knowing to ask, which is why drift here is silent."""
    from untell.api_server import HumanizeRequest
    from untell.scripts.run import build_parser, untell_text

    values = {}
    lib = inspect.signature(untell_text).parameters
    if knob in lib:
        values["library"] = lib[knob].default
    cli = {a.dest: a.default for a in build_parser()._actions}
    if knob in cli:
        values["cli"] = cli[knob]
    mcp = inspect.signature(mcp_tools["untell"]).parameters
    if knob in mcp:
        values["mcp"] = mcp[knob].default
    if knob in HumanizeRequest.model_fields:
        values["rest"] = HumanizeRequest.model_fields[knob].default

    assert len(values) >= 3, f"{knob} is not exposed widely enough to compare: {values}"
    assert len(set(map(repr, values.values()))) == 1, f"{knob} differs by surface: {values}"


def test_mcp_exposes_every_knob_rest_does(mcp_tools):
    """The two that were missing both change the verdict, which is why silence was the wrong answer."""
    from untell.api_server import HumanizeRequest

    mcp = set(inspect.signature(mcp_tools["untell"]).parameters) - {"text"}
    rest = set(HumanizeRequest.model_fields) - {"text"}

    assert not (rest - mcp), f"MCP cannot ask for {sorted(rest - mcp)}, which REST models"


def test_the_library_only_knobs_are_absent_from_both(mcp_tools):
    """The deliberate line, pinned — otherwise closing the gap above invites closing this one too."""
    from untell.api_server import HumanizeRequest

    mcp = set(inspect.signature(mcp_tools["untell"]).parameters)
    rest = set(HumanizeRequest.model_fields)
    for knob in LIBRARY_ONLY:
        assert knob not in mcp and knob not in rest, (
            f"{knob} is a library-only knob — it drives Playwright, writes to stdout, or is an "
            "internal. Exposing it remotely needs its own argument, not this file's."
        )


@pytest.mark.parametrize("confirm,ok", [(0, True), (1, True), (32, True), (-1, False), (99, False)])
def test_confirm_accepts_zero_and_rejects_out_of_range(mcp_tools, confirm: int, ok: bool):
    """Zero is a MEANING here, not an out-of-range count.

    The first version of this knob validated `confirm` as a "count" (1..100), so the DEFAULT was
    rejected and the flagship tool answered {"error": "confirm=0 is outside 1..100."} to every
    ordinary call. Found by testing the boundary rather than the middle.
    """
    result = mcp_tools["untell"](
        text=TEXT, tier="lite", max_iters=1, best_of=1, confirm=confirm
    )
    assert (not result.get("error")) is ok, result
