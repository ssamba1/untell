"""A knob on the library and nowhere else answers differently depending on how you called it.

`seed` was added to `untell_text` so a run stops depending on what the process rewrote before it.
This repo has the matching defect on record three times over: `best_of` moved to 3 on the CLI
while MCP and REST stayed on 1, `polish` was exposed over HTTP and not over MCP, and `confirm` and
`detector_thresholds` were CLI flags the REST surface modelled nowhere — so sending them was a
silent no-op. Each time, the same request answered differently by protocol.

The result also reports the seed it used. Without that, a caller holding an output cannot ask for
that output again: the derived value is a blake2b digest of the input, not something anyone can
work out, so `--seed` would be a knob you can set and never read back.
"""
from __future__ import annotations

import inspect

import pytest

from untell.scripts.run import build_parser, untell_text

AI = (
    "Moreover, the framework leverages robust methodologies to deliver outcomes at scale. "
    "It significantly improves overall efficiency across the evaluated corpus."
)


@pytest.fixture(autouse=True)
def _stdlib(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


def _run(**kw):
    return untell_text(AI, tier="lite", threshold=0.30, max_iters=1, rewriter="composite", **kw)


def test_the_result_reports_the_stream_that_produced_it():
    result = _run()
    assert isinstance(result.get("seed"), int), "the result does not say which stream it used"


def test_the_reported_seed_replays_the_run():
    """The property that makes reporting it worth anything."""
    first = _run()
    replay = _run(seed=first["seed"])
    assert replay["final"] == first["final"]
    assert replay["post"]["max"] == first["post"]["max"]


def test_an_explicit_seed_is_reported_back_unchanged():
    assert _run(seed=7)["seed"] == 7


def test_the_cli_exposes_it():
    flags = {a.option_strings[0] for a in build_parser()._actions if a.option_strings}
    assert "--seed" in flags, "the library takes a seed and the CLI cannot pass one"


def test_the_mcp_tool_exposes_it():
    from untell import mcp_server

    source = inspect.getsource(mcp_server)
    assert "seed: int | None = None" in source, "MCP humanize has no seed parameter"
    assert "seed=seed," in source, "MCP accepts a seed and does not pass it to the loop"


def test_the_rest_request_model_exposes_it():
    rest = pytest.importorskip("untell.api_server", reason="needs the [server] extra")

    fields = getattr(rest.HumanizeRequest, "model_fields", None)
    assert fields is not None, "pydantic model shape changed; update this test rather than drop it"
    assert "seed" in fields, "the REST /humanize body cannot carry a seed"

    source = inspect.getsource(rest)
    assert "seed=body.seed," in source, "the REST surface accepts a seed and drops it"
