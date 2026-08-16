"""Tests for the MCP server — verifies tool registration, not network/MCP protocol.
Mocks the mcp package entirely before importing so we don't need it installed."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


def test_server_tools_registered():
    """The _server() function registers tools without error and returns a FastMCP instance."""
    mock_fastmcp_instance = MagicMock()
    mock_fastmcp_cls = MagicMock(return_value=mock_fastmcp_instance)
    fake_fastmcp_module = MagicMock(FastMCP=mock_fastmcp_cls)
    fake_fastmcp_module.__name__ = "mcp.server.fastmcp"

    fake_mcp_server = MagicMock()
    fake_mcp_server.fastmcp = fake_fastmcp_module

    fake_mcp = MagicMock()
    fake_mcp.server = fake_mcp_server

    patches = {
        "mcp": fake_mcp,
        "mcp.server": fake_mcp_server,
        "mcp.server.fastmcp": fake_fastmcp_module,
    }
    saved_modules = {"untell.mcp_server": sys.modules.get("untell.mcp_server")}

    with patch.dict(sys.modules, patches, clear=False):
        if "untell.mcp_server" in sys.modules:
            del sys.modules["untell.mcp_server"]

        import untell.mcp_server as mcp_mod

        result = mcp_mod._server()
        mock_fastmcp_cls.assert_called_once_with("untell")
        assert len(mock_fastmcp_instance.tool.call_args_list) >= 5, (
            f"Expected at least 5 tools registered, got {len(mock_fastmcp_instance.tool.call_args_list)}"
        )
        assert result is mock_fastmcp_instance

        # The re-import above replaced the module in sys.modules AND on the `untell` package
        # attribute; patch.dict only restores the mcp.* keys it patched, so the two end up
        # pointing at DIFFERENT copies — a stale-copy desync that surfaced as an identity
        # failure in a later test. Restore the original module so the registry is coherent.
        if "untell.mcp_server" in saved_modules:
            sys.modules["untell.mcp_server"] = saved_modules["untell.mcp_server"]
            import untell as _untell_pkg

            _untell_pkg.mcp_server = saved_modules["untell.mcp_server"]


def test_mcp_advertises_every_style_the_cli_accepts():
    """The MCP tool docstring is what a client reads to learn valid `style` values.

    It was hand-copied and had drifted to 6 of the 14 styles, so eight were invisible to every
    MCP caller. It is now generated from the same table `--style` uses.

    Registration order matters: `server.tool()` snapshots __doc__ as the advertised description,
    so patching the list in after an inline decorator had no effect on what a client sees.
    """
    import asyncio

    pytest.importorskip("mcp")
    from untell.mcp_server import _server
    from untell.rewriter.prompts import STYLE_NAMES

    tools = asyncio.run(_server().list_tools())
    described = next(t for t in tools if t.name == "untell").description or ""
    missing = [s for s in STYLE_NAMES if s not in described]
    assert not missing, f"MCP does not advertise these styles: {missing}"


def test_cli_style_choices_come_from_the_same_table():
    from untell.rewriter.prompts import STYLE_NAMES
    from untell.scripts.run import main as run_main

    with pytest.raises(SystemExit):
        run_main(["--style", "definitely-not-a-style", "text"])
    assert len(STYLE_NAMES) == 14


def _mcp_tools():
    """Register the MCP tools against a fake FastMCP and return them by name.

    The existing tests assert that >=5 tools register and that the style list matches the CLI, but
    never CALL one — a tool could raise on every invocation and the suite would stay green. This
    captures the actual callables so their behaviour can be asserted.
    """
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


class TestMcpToolsActuallyRun:
    TEXT = (
        "Furthermore, organizations leverage these robust technologies to optimize operational "
        "efficiency. Moreover, the impact continues to expand across various sectors."
    )

    @pytest.mark.parametrize("name", ["score", "sentences", "tells", "scrub"])
    def test_simple_tools_return_dicts(self, name):
        fn = _mcp_tools()[name]
        kwargs = {"text": self.TEXT}
        if name in ("score", "sentences"):
            kwargs["tier"] = "lite"
        result = fn(**kwargs)
        assert isinstance(result, dict) and result

    def test_untell_works_with_default_arguments(self):
        """MEASURED before the fix: calling this with defaults returned
        {"error": "no rewriter configured"} on any install without an API key.

        The default was `rewriter="auto"`, which is not in _FREE_REWRITERS, so it fell through
        unresolved and auto-select declined to pick a backend — even though `composite` is free and
        always available. The identical CLI invocation worked, because the CLI defaults to
        composite. The flagship MCP tool failed out of the box.
        """
        result = _mcp_tools()["untell"](text=self.TEXT, tier="lite", max_iters=1)
        assert "error" not in result, result["error"]
        assert result["final"]

    @pytest.mark.parametrize("style", ["bogus", "Casual", "CASUAL", "casual "])
    def test_an_unknown_style_is_refused_not_silently_dropped(self, style):
        """An unrecognised name is looked up in STYLES, missed, and skipped — so a caller asked
        for a voice and got a rewrite with no style applied and nothing saying so. The CLI rejects
        the same input at parse time and POST /humanize now returns 422."""
        result = _mcp_tools()["untell"](text=self.TEXT, tier="lite", max_iters=1, style=style)
        assert "error" in result, result
        assert "unknown style" in result["error"]

    def test_the_error_lists_the_styles_the_tool_advertises(self):
        from untell.rewriter.prompts import STYLE_NAMES

        err = _mcp_tools()["untell"](text=self.TEXT, tier="lite", max_iters=1, style="nope")["error"]
        for name in STYLE_NAMES:
            assert name in err, name

    def test_a_real_style_still_runs(self):
        result = _mcp_tools()["untell"](text=self.TEXT, tier="lite", max_iters=1, style="casual")
        assert "error" not in result, result.get("error")
        assert result["final"]

    def test_unknown_rewriter_names_the_rewriter(self):
        """A typo used to fall through to auto-selection, running a DIFFERENT technique and
        reporting the result as the requested one."""
        result = _mcp_tools()["untell"](text=self.TEXT, tier="lite", rewriter="does_not_exist")
        assert "does_not_exist" in result.get("error", "")

    def test_an_unknown_rewriter_is_a_clean_refusal_not_a_success_with_original_text(self):
        """MEASURED (this slice, real engine): untell(rewriter='does_not_exist') returned
        {"error": ..., "final": <the UNCHANGED input>, "seed": ...} — a successful-looking
        result whose `final` is exactly the text the caller asked to be rewritten.

        `untell_text` refuses the name (nothing is rewritten; run.py returns
        {"error": ..., "final": text} immediately), but the tool passed that dict through
        untouched, so a client that reads `final` — the key this tool's own docstring
        advertises as "the humanized text" — saw the original passed back as if the loop had
        run. The CLI refuses the same name at parse time and REST answers 422; on MCP there
        is no status code, so the refusal must be the pure error dict every other guard on
        this surface returns (tier, style, ceiling-rewriter). An unchanged original must
        never be able to pass for a rewrite.
        """
        result = _mcp_tools()["untell"](
            text=self.TEXT, tier="lite", max_iters=1, rewriter="does_not_exist"
        )
        assert "error" in result and "does_not_exist" in result["error"]
        assert "final" not in result, "a refusal must not present the unchanged text as `final`"
        assert "seed" not in result


def test_best_of_default_matches_the_cli_on_every_surface():
    """best-of-1 was identified as a root cause of understated evasion and the CLI moved to 3.
    MCP and the REST API were left on 1, so every non-CLI caller got the weak path.

    MEASURED over 6 real HC3 paragraphs: best_of=1 -> 33% still flagged, best_of=3 -> 0%.

    The ceiling surfaces are deliberately excluded — eval/ceiling.py's CLI also defaults to 1,
    because measuring the single-draw baseline is the point of that tool.
    """
    import inspect

    from untell.api_server import HumanizeRequest
    from untell.scripts.run import main as run_main  # noqa: F401

    mcp_untell = _mcp_tools()["untell"]
    assert inspect.signature(mcp_untell).parameters["best_of"].default == 3
    assert HumanizeRequest.model_fields["best_of"].default == 3


def test_rewriter_default_is_the_free_path_on_every_surface():
    """"auto" declines to pick a backend without an API key, so it cannot be the default on a
    tool that advertises a zero-dependency free path."""
    import inspect

    from untell.api_server import HumanizeRequest

    assert inspect.signature(_mcp_tools()["untell"]).parameters["rewriter"].default == "composite"
    assert HumanizeRequest.model_fields["rewriter"].default == "composite"


def test_untell_tool_exposes_polish():
    """The REST API's /humanize exposes `polish`; the MCP tool always called untell_text with the
    default False, so the same loop reached through MCP produced a strictly weaker result than
    through HTTP, with nothing to indicate a knob was missing."""
    import inspect

    import untell.mcp_server as mcp

    src = inspect.getsource(mcp)
    assert "polish: bool = False" in src
    assert "polish=polish" in src, "declared but not forwarded to untell_text"


class TestMcpRejectsOutOfRangeArguments:
    """The third surface. The CLI rejects these at parse time and REST answers 422.

    `tier="fulll"` matches no tier, falls back to the lite heuristic, and answers with a
    lite-shaped result and no sign the requested tier was never honoured. `threshold=50` produces
    a verdict in which nothing can ever be flagged, because detector scores live in [0, 1].

    Tested against `_bad_args` directly: it lives at module level precisely so these do not skip
    on a machine without the optional `mcp` package, which is most of them.
    """

    def test_unknown_tier_is_named(self):
        from untell.mcp_server import _bad_args

        out = _bad_args(tier=("fulll", "tier"))
        assert "unknown tier" in out["error"]
        assert "lite, full, heavy, commercial" in out["error"]

    def test_threshold_above_one_is_refused(self):
        from untell.mcp_server import _bad_args

        assert "outside [0, 1]" in _bad_args(threshold=(50, "probability"))["error"]
        assert "outside [0, 1]" in _bad_args(margin=(-0.1, "probability"))["error"]

    def test_counts_are_bounded(self):
        from untell.mcp_server import _bad_args

        assert "outside 1..100" in _bad_args(max_iters=(0, "count"))["error"]
        assert "outside 1..100" in _bad_args(best_of=(10 ** 6, "count"))["error"]

    def test_valid_arguments_pass_through(self):
        from untell.mcp_server import _bad_args

        assert _bad_args(
            tier=("lite", "tier"), threshold=(0.3, "probability"), best_of=(3, "count")
        ) is None

    def test_the_tools_actually_call_it(self):
        """A validator nothing invokes is decoration."""
        pytest.importorskip("mcp")
        from untell.mcp_server import _server

        tools = {t.name: t.fn for t in _server()._tool_manager.list_tools()}
        text = "Furthermore, the system leverages robust methodologies to optimize outcomes."
        assert "unknown tier" in tools["score"](text, tier="fulll").get("error", "")
        assert "outside 1..100" in tools["untell"](text, tier="lite", max_iters=0).get("error", "")

    def test_non_numeric_garbage_is_refused_not_a_traceback(self):
        """The conversions inside _bad_args used to raise ValueError on garbage (MEASURED before:
        _bad_args(threshold=("abc", "probability")) raised instead of refusing). An MCP client
        can send ANYTHING, and a traceback is what this validator exists to prevent."""
        from untell.mcp_server import _bad_args

        for name, kind in (("threshold", "probability"), ("margin", "probability"),
                           ("max_iters", "count"), ("best_of", "count"),
                           ("confirm", "count_or_zero"), ("top", "top"), ("seed", "seed")):
            err = _bad_args(**{name: ("abc", kind)})
            assert err and "is not a number" in err["error"], (name, err)


class TestVerifyCommercialValidatesArguments:
    """The one tool `_bad_args` was written for and never wired into.

    MEASURED before the guard: threshold=50 returned passes_all=True (a warning string was the
    only signal that nothing could ever fail) and tier='bogus' ran the lite tier and said so only
    inside a warning. REST /verify rejects both with 422; the CLI rejects the tier at parse time.
    A verification tool must not answer PASS to an impossible threshold.
    """

    def test_an_unknown_tier_is_refused(self):
        fn = _mcp_tools()["verify_commercial"]
        err = fn(text="This is a test sentence.", tier="bogus").get("error", "")
        assert "unknown tier" in err and "bogus" in err

    def test_a_threshold_above_one_is_refused(self):
        fn = _mcp_tools()["verify_commercial"]
        err = fn(text="This is a test sentence.", threshold=50).get("error", "")
        assert "outside [0, 1]" in err

    def test_a_negative_threshold_is_refused(self):
        fn = _mcp_tools()["verify_commercial"]
        err = fn(text="This is a test sentence.", threshold=-0.5).get("error", "")
        assert "outside [0, 1]" in err

    def test_a_non_numeric_threshold_is_refused(self):
        fn = _mcp_tools()["verify_commercial"]
        err = fn(text="This is a test sentence.", threshold="abc").get("error", "")
        assert "is not a number" in err

    @pytest.mark.parametrize("tier", ["", "commercial"])
    def test_the_api_only_tiers_still_run(self, tier):
        """'' and 'commercial' mean commercial-only (local ensemble skipped) on every surface;
        the guard must not refuse the documented vocabulary."""
        fn = _mcp_tools()["verify_commercial"]
        result = fn(text="This is a test sentence.", tier=tier)
        assert "error" not in result, result
        assert result["n_configured"] == 0  # no commercial keys configured in CI

    def test_the_valid_default_still_runs(self):
        fn = _mcp_tools()["verify_commercial"]
        result = fn(text="This is a test sentence.", tier="lite")
        assert "error" not in result, result
        assert "passes_all" in result


def test_advertised_tool_names_match_what_the_server_registers():
    """`--help` and `--list-tools` print a literal list, because they must work on an install
    without the optional `mcp` package. A literal drifts; this is what stops it.

    Registration is not uniform — most tools use the `@server.tool()` decorator but `untell` is
    registered manually afterwards, because the decorator snapshots `__doc__` at registration time
    and the style list is patched in after definition. So the check has to ask the built server,
    not the source.
    """
    mcp = pytest.importorskip("mcp")  # noqa: F841
    import asyncio

    from untell.mcp_server import _TOOL_NAMES, _server

    registered = {t.name for t in asyncio.run(_server().list_tools())}
    assert registered == set(_TOOL_NAMES), (
        f"registered but not advertised: {sorted(registered - set(_TOOL_NAMES))}; "
        f"advertised but not registered: {sorted(set(_TOOL_NAMES) - registered)}"
    )


def test_help_does_not_start_the_server():
    """`untell-mcp --help` used to print nothing and exit 0, having briefly started a JSON-RPC
    server that blocked on stdin. Silence is indistinguishable from a broken install."""
    from untell.mcp_server import build_parser

    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["--help"])
    assert exc.value.code == 0


def test_list_tools_flag_exits_without_starting_the_server(capsys):
    from untell.mcp_server import _TOOL_NAMES, main

    assert main(["--list-tools"]) == 0
    printed = capsys.readouterr().out.split()
    assert printed == list(_TOOL_NAMES)


def test_pyproject_entry_point_wires_this_module_and_its_tool_list():
    """The console-script wiring is part of the tool-name registry: if `untell-mcp` were
    repointed at another module, `--list-tools` would still print a literal list and nothing
    would notice the server no longer runs the tools the README advertises. Pin the
    pyproject [project.scripts] mapping to this module's `main`, and `main`'s literal list
    to what the server registers (the existing registration test pins the latter)."""
    import importlib
    from pathlib import Path

    import tomllib

    mcp_module = importlib.import_module("untell.mcp_server")

    pyproject = tomllib.loads(
        (Path(mcp_module.__file__).resolve().parents[1] / "pyproject.toml").read_text("utf-8")
    )
    scripts = pyproject["project"]["scripts"]
    assert scripts["untell-mcp"] == "untell.mcp_server:main", scripts
    module_name, _, attr = scripts["untell-mcp"].partition(":")
    # Both sides go through importlib so they read the same sys.modules entry — a bare
    # `import untell.mcp_server as mcp` here bound the parent-package attribute instead,
    # which test_server_tools_registered leaves pointing at a stale re-imported copy.
    assert importlib.import_module(module_name) is mcp_module
    assert getattr(mcp_module, attr)(["--list-tools"]) == 0


def test_an_unknown_flag_is_rejected_rather_than_ignored():
    """The bug underneath the missing --help: argv was never parsed, so any flag at all fell
    through to starting a server."""
    from untell.mcp_server import build_parser

    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["--not-a-real-flag"])
    assert exc.value.code != 0
