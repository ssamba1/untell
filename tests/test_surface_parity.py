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

import argparse

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
    # `diff` is the CLI's presentation mode for the humanize report (unified before/after, or a
    # machine-readable untell-diff payload with --json) — the loop result dict is unchanged, so
    # there is nothing for the network surfaces to mirror, the same reasoning as `sim_bar`.
    # `timings` is the same category: a per-phase budget REPORT (issue #27), printed as a summary
    # line or — under --json — added to the result payload by `untell_text(timings=True)`. The
    # library knob exists for any programmatic caller; REST/MCP simply do not expose a toggle yet,
    # so their payloads stay byte-identical until someone asks for the report there.
    # `html` (issue #30) is the same category again: a presentation of the humanize result as a
    # self-contained HTML report, built on the diff payload — a CLI-only artifact that renders
    # the loop's existing result dict, changing nothing the network surfaces would mirror.
    # `manifest` (issue #31) is the same category once more: `--manifest PATH` writes a
    # reproducibility JSON *file* as a side effect of the run. It is output routing to a
    # filesystem the REST/MCP surfaces have no concept of, so there is nothing for them to
    # mirror — the loop result dict they return is unchanged.
    allowed = {"browser", "sim_bar", "scrub", "detector_thresholds", "confirm", "n",
               "include_matches", "diff", "timings", "html", "manifest"}
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


def test_the_free_rewriter_list_matches_the_cli_minus_its_three_special_names():
    """Three places enumerate the rewriters, and the relationship between them is exact.

    `untell humanize --rewriter` offers the free backends plus three names that are not free
    backends: "auto" (let get_rewriter choose, which may be a PAID hosted LLM), "base" (the
    untrained local policy, a training/debug backend) and "local" (the trained local policy,
    also a training/debug backend; added for issue #34 so a missing peft extra exits with a
    clean message instead of a traceback). _FREE_REWRITERS is exactly the rest, and
    that is what both network surfaces resolve against — so a backend added to the CLI and not to
    the frozenset would be rejected over HTTP while working on the command line.
    """
    from untell.scripts.run import build_parser

    action = next(a for a in build_parser()._actions if a.dest == "rewriter")
    cli = set(action.choices)
    assert {"auto", "base", "local"} <= cli
    assert cli - {"auto", "base", "local"} == set(api._FREE_REWRITERS)


def test_the_ceiling_cli_offers_the_same_backends():
    """eval/ceiling.py restates the list too; it omits only "base", which is not an evasion path."""
    from eval.ceiling import build_parser as ceiling_parser
    from eval.ceiling import main as ceiling_main  # noqa: F401

    action = next(a for a in ceiling_parser()._actions if a.dest == "rewriter")
    assert set(action.choices) - {"auto"} == set(api._FREE_REWRITERS)


class TestBestOfIsThreeOnEverySurfaceThatHumanizes:
    """best-of-1 was identified as a root cause of understated evasion and fixed three times.

    MEASURED over 6 real HC3 paragraphs:

        best_of=1   mean 0.601 -> 0.293, 33% still flagged
        best_of=3   mean 0.601 -> 0.256,  0% still flagged

    The CLI moved to 3 first. MCP and REST were found still on 1 and moved. The `untell_text`
    signature itself stayed on 1, so a direct library import — the fourth surface — kept getting the
    weak path with nothing to indicate a knob was missing. Same defect, one layer down each time,
    which is why this is a test rather than a comment.

    eval/ceiling.py is the deliberate exception and is asserted separately: measuring the
    single-draw baseline is its purpose, and it passes the value explicitly.
    """

    def test_the_library_default_is_three(self):
        import inspect

        from untell.scripts.run import untell_text

        assert inspect.signature(untell_text).parameters["best_of"].default == 3

    def test_the_cli_default_is_three(self):
        from untell.scripts.run import _CLI_DEFAULTS

        assert _CLI_DEFAULTS["best_of"] == 3

    def test_the_mcp_tool_default_is_three(self):
        """Via _mcp_tools(), not getattr on the module.

        The tools are registered through a @server.tool() decorator inside a factory, so they are
        not module attributes and a getattr lookup finds nothing. The first version of this test
        skipped on that — and a skipping parity test guards nothing while looking like coverage,
        which is the exact failure this file exists to catch.
        """
        import inspect

        tools = _mcp_tools()
        humanize = next(
            (fn for name, fn in tools.items()
             if "best_of" in inspect.signature(fn).parameters and "ceiling" not in name),
            None,
        )
        assert humanize is not None, f"no humanizing MCP tool takes best_of: {sorted(tools)}"
        assert inspect.signature(humanize).parameters["best_of"].default == 3

    def test_the_rest_humanize_default_is_three(self):
        pytest.importorskip("fastapi")
        import untell.api_server as api

        model = next(
            m
            for name, m in vars(api).items()
            if name.endswith("Request") and "best_of" in getattr(m, "model_fields", {})
            and "ceiling" not in name.lower()
        )
        assert model.model_fields["best_of"].default == 3

    def test_the_ceiling_surfaces_stay_at_one_on_purpose(self):
        """The exception must be explicit, or the parity check above would quietly force it to 3."""
        pytest.importorskip("fastapi")
        import untell.api_server as api

        ceiling = next(
            (m for name, m in vars(api).items()
             if name.endswith("Request") and "ceiling" in name.lower()),
            None,
        )
        if ceiling is None:
            pytest.skip("no ceiling request model")
        assert ceiling.model_fields["best_of"].default == 1


class TestTheSurfacesAgreeOnRANGES_NotJustDefaults:
    """The tests above compare defaults and vocabularies. They did not compare *ranges*, and that
    is the gap the CLI fell through.

    Measured before the fix — identical arguments, two answers:

        --threshold 50    CLI exit 0            REST 422   (scores are in [0,1]; nothing can flag)
        --threshold -1    CLI exit 0            REST 422   (everything flags, always)
        --best-of 0       CLI exit 0            REST 422
        --max-iters -5    CLI exit 0            REST 422   (no iterations; reports a pass)
        --best-of 10000   CLI ran until killed  REST 422   (genuinely generating candidates)

    The CLI now reads its bounds off the API's own annotated types rather than repeating them,
    so there is one definition to drift from. These tests check that the indirection actually
    holds — an import that silently falls back would restore the divergence invisibly.
    """

    @staticmethod
    def _api_bounds(name: str):
        """Read the bounds independently of `run._bounds`, so this checks the CLI against the API
        rather than against itself.

        Pydantic keeps `ge`/`le` inside `FieldInfo.metadata` as annotated_types constraint objects.
        Reaching for `FieldInfo.ge` raises AttributeError — which is the mistake the production
        helper originally made, and then swallowed into a fallback, so the sharing it advertised
        was doing nothing.
        """
        from untell import api_server

        low = high = None
        for constraint in getattr(api_server, name).__metadata__[0].metadata:
            if hasattr(constraint, "ge"):
                low = float(constraint.ge)
            if hasattr(constraint, "le"):
                high = float(constraint.le)
        assert low is not None and high is not None, f"{name} has no ge/le constraint"
        return low, high

    def test_the_cli_reads_its_bounds_from_the_api(self):
        from untell.scripts import run

        for cli_name, api_name, cast in (
            ("_PROBABILITY", "_Probability", float),
            ("_ITERS", "_Iters", int),
            ("_BEST_OF", "_BestOf", int),
        ):
            low, high = self._api_bounds(api_name)
            parse = getattr(run, cli_name)
            # An int-typed flag has to be handed an int spelling; "100.0" is rejected as
            # non-numeric by design, which is correct behaviour and not the bound under test.
            with pytest.raises(argparse.ArgumentTypeError):
                parse(str(cast(high + 1)))
            with pytest.raises(argparse.ArgumentTypeError):
                parse(str(cast(low - 1)))
            assert parse(str(cast(high))) == pytest.approx(high)
            assert parse(str(cast(low))) == pytest.approx(low)

    @pytest.mark.parametrize(
        "flag,value",
        [
            ("--threshold", "50"), ("--threshold", "-1"),
            ("--best-of", "0"), ("--best-of", "10000"),
            ("--max-iters", "-5"), ("--max-iters", "0"),
            ("--margin", "5"),
        ],
    )
    def test_the_cli_rejects_what_the_api_rejects(self, flag, value):
        from untell.scripts.run import build_parser

        with pytest.raises(SystemExit) as exc:
            build_parser().parse_args(["some text", flag, value])
        assert exc.value.code == 2, f"{flag} {value} was accepted"

    def test_an_error_message_names_the_flag_it_is_about(self):
        """`--margin 5` first reported "threshold must be between 0.0 and 1.0" because it reused
        the probability parser. A range message naming the wrong flag sends the reader to the
        wrong argument."""
        from untell.scripts.run import _MARGIN

        with pytest.raises(argparse.ArgumentTypeError, match="margin"):
            _MARGIN("5")

    def test_the_bounds_are_real_and_not_a_silent_fallback(self):
        """`_bounds` falls back to a literal pair when `api_server` cannot be imported, which is
        correct — the server extra is optional and the CLI must still run. But if that fallback
        fires on a machine that HAS the server installed, the two surfaces are silently
        independent again."""
        from untell.scripts.run import _bounds

        pytest.importorskip("fastapi")
        assert _bounds("_Probability", (99.0, 99.0)) == (0.0, 1.0)
        assert _bounds("_BestOf", (99.0, 99.0)) == (1.0, 32.0)


class TestConfigAndEnvGetTheSameRangeChecks:
    """A range guard on the command line only guards the command line.

    `add_argument(type=...)` runs on what the user TYPES. It never runs on a `default=`, and a
    config file or a `UNTELL_*` variable arrives as a default. So the bounds added for argparse did
    nothing for the other two input channels, and the same nonsense had two different answers:

        --threshold 50              rejected
        UNTELL_THRESHOLD=50         accepted
        untell.yaml  threshold: 50  accepted

    `_config_defaults` already validated categorical CHOICES for exactly this reason, with a
    docstring explaining it. Ranges were missed by the same argument.
    """

    OUT_OF_RANGE = [
        ("threshold", 50, 0.30),
        ("threshold", -1, 0.30),
        ("max_iters", -5, 5),
        ("max_iters", 0, 5),
        ("best_of", 0, 3),
        ("best_of", 99999, 3),
    ]

    @pytest.mark.parametrize("key,bad,shipped", OUT_OF_RANGE)
    def test_an_out_of_range_env_value_is_refused(self, key, bad, shipped, monkeypatch, capsys):
        from untell.scripts.run import _config_defaults

        monkeypatch.setenv(f"UNTELL_{key.upper()}", str(bad))
        resolved = _config_defaults()
        assert resolved[key] == shipped, f"{key}={bad} was accepted from the environment"
        assert key in capsys.readouterr().err, "the rejection was silent"

    @pytest.mark.parametrize("key,bad,shipped", OUT_OF_RANGE)
    def test_an_out_of_range_config_file_value_is_refused(
        self, key, bad, shipped, tmp_path, monkeypatch, capsys
    ):
        (tmp_path / "untell.yaml").write_text(f"{key}: {bad}\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv(f"UNTELL_{key.upper()}", raising=False)

        from untell import config
        from untell.scripts.run import _config_defaults

        if hasattr(config.load, "cache_clear"):
            config.load.cache_clear()
        resolved = _config_defaults()
        assert resolved[key] == shipped, f"{key}={bad} was accepted from untell.yaml"
        assert key in capsys.readouterr().err, "the rejection was silent"

    @pytest.mark.parametrize(
        "key,good", [("threshold", 0.55), ("max_iters", 9), ("best_of", 7)]
    )
    def test_an_in_range_value_still_gets_through(self, key, good, monkeypatch):
        """The guard must reject the impossible, not the merely unusual. A rule that dropped valid
        configuration would be a worse bug than the one it fixes, and silent besides."""
        from untell.scripts.run import _config_defaults

        monkeypatch.setenv(f"UNTELL_{key.upper()}", str(good))
        assert _config_defaults()[key] == pytest.approx(good)

    def test_the_ranges_come_from_the_same_place_as_the_cli_ones(self):
        """Two tables of bounds is how the CLI and the API drifted apart in the first place."""
        from untell.scripts.run import _BEST_OF, _CONFIG_RANGES, _ITERS, _PROBABILITY

        for key, parser in (
            ("threshold", _PROBABILITY), ("max_iters", _ITERS), ("best_of", _BEST_OF)
        ):
            low, high = _CONFIG_RANGES[key]
            cast = int if key != "threshold" else float
            with pytest.raises(argparse.ArgumentTypeError):
                parser(str(cast(high + 1)))
            assert parser(str(cast(high))) == pytest.approx(high)
