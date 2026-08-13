"""The MCP `ceiling` tool accepted a tier that does not exist and a threshold nothing can reach.

`_bad_args` exists in this module precisely for this, and its docstring names both cases and ends
"this was the third surface, still silent". `ceiling` was the fourth: it validated the rewriter name
and let the tier and the threshold through untouched. MEASURED before, one sample:

    tier="bogus"     result reports tier: "bogus", only perplexity_burstiness actually ran
    threshold=50.0   pre_flagged_rate 0.0, post_flagged_rate 0.0, and no warning

The second is the worse one on a MEASUREMENT tool. Detector scores are probabilities, so a
threshold above 1 can never be reached: nothing is ever flagged, and the answer reads as a perfect
result — 0% flagged before AND after — when nothing was measured at all. A caller quoting that
number is quoting an artefact of their own argument.

The first is the tier-reporting defect this repo has fixed on three other surfaces: the requested
tier is echoed back while a different one ran.
"""

from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("mcp")


def _call(name: str, **kwargs) -> dict:
    """Invoke a registered MCP tool the way a client does, and return its parsed payload."""
    import untell.mcp_server as mcp_server

    server = mcp_server._server()

    async def run():
        return await server.call_tool(name, kwargs)

    result = asyncio.run(run())
    blocks = result[0] if isinstance(result, tuple) else result
    for block in blocks:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"raw": text}
    return {}


@pytest.fixture(autouse=True)
def stdlib_lite(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


def test_an_unknown_tier_is_refused() -> None:
    payload = _call("ceiling", tier="bogus", n=1, max_iters=1)
    assert "error" in payload, payload
    assert "bogus" in payload["error"]
    assert "lite" in payload["error"], "the error should name the valid tiers"


def test_a_threshold_above_one_is_refused() -> None:
    """The dangerous one: it does not fail, it succeeds and reports 0% flagged."""
    payload = _call("ceiling", threshold=50.0, n=1, max_iters=1)
    assert "error" in payload, payload
    assert "outside [0, 1]" in payload["error"]


@pytest.mark.parametrize("override", [
    {"n": 0}, {"max_iters": 0}, {"best_of": 0}, {"n": 500},
], ids=lambda o: f"{next(iter(o))}={next(iter(o.values()))}")
def test_an_out_of_range_count_is_refused(override: dict) -> None:
    # Merged into the defaults rather than passed alongside them: `_call(..., n=1, **{"n": 0})`
    # is a duplicate keyword argument, which fails for a reason that has nothing to do with the
    # validation under test.
    kwargs = {"tier": "lite", "threshold": 0.30, "n": 1, "max_iters": 1}
    kwargs.update(override)
    payload = _call("ceiling", **kwargs)
    assert "error" in payload, f"{override} was accepted: {payload}"


def test_valid_arguments_still_run() -> None:
    """Guards every case above. A tool that refused everything would satisfy them all."""
    payload = _call("ceiling", tier="lite", threshold=0.30, n=1, max_iters=1)
    assert "error" not in payload, payload
    assert payload.get("n") == 1, payload


def test_the_tier_that_ran_is_the_one_reported() -> None:
    """The defect behind the unknown-tier case: an echoed request is not a measurement."""
    payload = _call("ceiling", tier="lite", threshold=0.30, n=1, max_iters=1)
    assert payload.get("tier", "lite") == "lite", payload
