"""The same operation must mean the same thing on the CLI, the REST API and the MCP server.

This session found and fixed eight divergences one at a time — the humanize tier default (lite vs
full), the tier vocabulary (unvalidated on the network surfaces), the rewriter default ("auto",
which fails without an API key), best_of (1 vs 3), style (unvalidated, so a silent no-op), polish
(not forwarded by MCP), threshold (missing from the MCP score tool), and `confirm` /
`detector_thresholds` (dropped without a word by REST).

Every one of them was a case of the CLI being improved and the network surfaces being left behind,
and every one was found by accident. These tests compare the three surfaces mechanically so the
ninth is a test failure instead.

Parameters that are genuinely CLI-shaped — `--file`, `--json`, `--quiet`, `--max-rounds` (an alias)
— are excluded by name, because they describe how a terminal invocation is spelled rather than what
the operation does.
"""

from __future__ import annotations

import inspect
import sys
import types

import pytest

pytest.importorskip("fastapi")

import untell.api_server as api  # noqa: E402

# CLI-only spellings: input plumbing and output formatting, not parameters of the operation.
_CLI_ONLY = {"file", "json", "quiet", "max_rounds", "help", "text"}


def _mcp_tools() -> dict:
    """Register the MCP tools against a fake FastMCP and return the callables by name."""
    recorded: dict = {}

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


def _cli_defaults(build_parser) -> dict:
    return {
        a.dest: a.default
        for a in build_parser()._actions
        if a.dest not in _CLI_ONLY and not a.dest.startswith("no_")
    }


def _rest_defaults(model) -> dict:
    return {
        name: field.default
        for name, field in model.model_fields.items()
        if name not in _CLI_ONLY
    }


def _mcp_defaults(fn) -> dict:
    return {
        name: (p.default if p.default is not inspect.Parameter.empty else None)
        for name, p in inspect.signature(fn).parameters.items()
        if name not in _CLI_ONLY
    }


def _operations():
    from untell.scripts.run import build_parser as humanize_parser
    from untell.scripts.verify import build_parser as verify_parser

    tools = _mcp_tools()
    return [
        ("humanize", _cli_defaults(humanize_parser), _rest_defaults(api.HumanizeRequest),
         _mcp_defaults(tools["untell"])),
        ("verify", _cli_defaults(verify_parser), _rest_defaults(api.VerifyRequest),
         _mcp_defaults(tools["verify_commercial"])),
    ]


@pytest.mark.parametrize("operation", ["humanize", "verify"])
def test_shared_parameters_have_the_same_default_everywhere(operation):
    """A weaker default on one surface is a weaker product on that surface, silently.

    The loop OPTIMISES against the tier and the candidate count it is given, so tier=lite or
    best_of=1 does not merely change a number — it changes what "passed" means, and the caller has
    no way to see which one they got.
    """
    name, cli, rest, mcp = next(op for op in _operations() if op[0] == operation)
    mismatches = []
    for param in sorted(set(cli) | set(rest) | set(mcp)):
        present = {
            surface: values[param]
            for surface, values in (("cli", cli), ("rest", rest), ("mcp", mcp))
            if param in values
        }
        if len({repr(v) for v in present.values()}) > 1:
            mismatches.append((param, present))
    assert not mismatches, f"{name}: {mismatches}"


@pytest.mark.parametrize("operation", ["humanize", "verify"])
def test_no_surface_is_missing_a_parameter_another_one_has(operation):
    """A parameter one surface exposes and another does not is a capability gap, not a style
    choice — `confirm` and `detector_thresholds` were REST gaps that changed the verdict."""
    name, cli, rest, mcp = next(op for op in _operations() if op[0] == operation)
    everywhere = set(cli) & set(rest) & set(mcp)
    union = set(cli) | set(rest) | set(mcp)
    missing = {
        param: [s for s, v in (("cli", cli), ("rest", rest), ("mcp", mcp)) if param not in v]
        for param in union - everywhere
    }
    # `browser` needs playwright and `sim_bar`/`scrub` are advanced knobs the CLI spells with a
    # negative flag; anything else appearing here is a real gap.
    allowed = {"browser", "sim_bar", "scrub", "detector_thresholds", "confirm", "n", "include_matches"}
    unexpected = {k: v for k, v in missing.items() if k not in allowed}
    assert not unexpected, f"{name}: parameter present on some surfaces only: {unexpected}"


def test_the_tier_vocabulary_is_the_loaders_own():
    """Four places name the tiers: argparse choices, the REST Literal, the MCP docstring, and
    _TIER_RANK. The loader's table is the one that decides what actually runs."""
    from typing import get_args

    from untell.detectors.base import _TIER_RANK
    from untell.scripts.run import build_parser

    assert set(get_args(api._TIER)) == set(_TIER_RANK)
    tier_action = next(a for a in build_parser()._actions if a.dest == "tier")
    assert set(tier_action.choices) == set(_TIER_RANK)


def test_no_cli_accepts_a_narrower_tier_vocabulary_than_the_loader():
    """Every `--tier` in the tree restates the tier list, and a restated vocabulary drifts.

    Two had: `untell-humanness` and `eval/benchmark.py` omitted "commercial", so both exited 2 on a
    tier their own code passes straight to score_text and that every other CLI accepts.

    Scans the SOURCE rather than building each parser, because most of these still construct their
    parser inside main(). An earlier version of this test imported the modules and skipped whatever
    lacked a build_parser() — which skipped 7 of 11, including both files that had the defect. A
    test that skips the cases it was written for verifies nothing.

    `untell-verify` is allowed to be WIDER: it documents `--tier ''` for commercial-only.
    """
    import re
    from pathlib import Path

    from untell.detectors.base import _TIER_RANK

    root = Path(__file__).resolve().parents[1]
    # A literal `choices=[...]` list attached to a --tier argument, however the call is wrapped.
    pattern = re.compile(r'"--tier".{0,400}?choices=\[([^\]]*)\]', re.S)
    checked, narrow = 0, []
    for path in sorted(list(root.glob("untell/**/*.py")) + list(root.glob("eval/*.py"))
                       + list(root.glob("training/*.py"))):
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            checked += 1
            listed = set(re.findall(r'"([^"]*)"', match.group(1)))
            missing = set(_TIER_RANK) - listed
            if missing:
                narrow.append((path.relative_to(root).as_posix(), sorted(missing)))

    assert checked >= 8, f"only found {checked} --tier choices lists — the scan is wrong"
    assert not narrow, f"CLIs rejecting tiers the loader supports: {narrow}"


def test_the_style_vocabulary_is_the_prompt_tables_own():
    from untell.rewriter.prompts import STYLE_NAMES
    from untell.scripts.run import build_parser

    style_action = next(a for a in build_parser()._actions if a.dest == "style")
    assert list(style_action.choices) == STYLE_NAMES
    assert [member.value for member in api._Style] == STYLE_NAMES


def test_the_free_rewriter_list_is_the_same_on_both_network_surfaces():
    """A name free-listed on one surface and not the other resolves to a different backend."""
    import untell.mcp_server as mcp

    assert api._FREE_REWRITERS == mcp._FREE_REWRITERS


def test_the_free_rewriter_list_matches_the_cli_minus_its_two_special_names():
    """Three places enumerate the rewriters, and the relationship between them is exact.

    `untell humanize --rewriter` offers the free backends plus two names that are not free
    backends: "auto" (let get_rewriter choose, which may be a PAID hosted LLM) and "base" (the
    untrained local policy, a training/debug backend). _FREE_REWRITERS is exactly the rest, and
    that is what both network surfaces resolve against — so a backend added to the CLI and not to
    the frozenset would be rejected over HTTP while working on the command line.
    """
    from untell.scripts.run import build_parser

    action = next(a for a in build_parser()._actions if a.dest == "rewriter")
    cli = set(action.choices)
    assert {"auto", "base"} <= cli
    assert cli - {"auto", "base"} == set(api._FREE_REWRITERS)


def test_the_ceiling_cli_offers_the_same_backends():
    """eval/ceiling.py restates the list too; it omits only "base", which is not an evasion path."""
    from eval.ceiling import build_parser as ceiling_parser
    from eval.ceiling import main as ceiling_main  # noqa: F401

    action = next(a for a in ceiling_parser()._actions if a.dest == "rewriter")
    assert set(action.choices) - {"auto"} == set(api._FREE_REWRITERS)
