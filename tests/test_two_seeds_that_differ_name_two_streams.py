"""`--seed -1` and `--seed 1` were the same stream.

A seed names a random stream, and the only reason to expose one is that different seeds give
different draws. The help text goes further and recommends it for comparing two settings on ONE
stream, "the honest way to ask whether a flag changed anything, since two runs that differ only by
chance look exactly like a flag that works."

CPython's `random.seed()` takes the ABSOLUTE value of an int argument, so -n and n are one seed.
MEASURED through `untell_text` on the lite path, seven seeds, same text:

    seed    sha256(final)[:10]   post
    -1      a128226bed           0.0731
     1      a128226bed           0.0731     <- identical to -1
     0      cbe4bcf80a           0.1000
     2      9a1f64af02           0.0583
     7      7df6932d6a           0.1762
     12345  424beb3191           0.2350

Six distinct outputs from seven seeds. The pair that collided is exactly the pair someone would
reach for to check that the flag does anything at all, and the collision reads as "seeding is not
working" or, worse, as "the setting I changed made no difference".

All three surfaces took a bare int. The CLI bounds it through the shared `_ranged` helper, REST
through a `_Seed` annotated type, MCP through `_bad_args` — and `untell_text` refuses it directly,
since it is the public entry point all three go through and a silently aliased seed is worse than
a rejected one. The upper bound is the range of the text-derived default (blake2b, 8 bytes), so a
caller can still name any stream the tool would pick on its own.
"""

from __future__ import annotations

import os
import random
import subprocess
import sys

import pytest

TEXT = "Moreover, the framework leverages robust methodologies to deliver outcomes at scale."


def test_the_mechanism_negative_seeds_alias_to_their_absolute_value():
    """The premise, asserted against the interpreter rather than assumed. If a future Python
    stopped folding the sign, the bound below would be merely conservative instead of necessary,
    and this test is what would say so."""
    random.seed(1)
    positive = [random.random() for _ in range(3)]
    random.seed(-1)
    negative = [random.random() for _ in range(3)]
    assert positive == negative, (
        "random.seed() no longer folds the sign — the aliasing this bound exists for is gone"
    )


class TestTheLibraryRefusesIt:
    def test_a_negative_seed_raises(self):
        from untell.scripts.run import untell_text

        with pytest.raises(ValueError, match="0 or greater"):
            untell_text(TEXT, tier="lite", max_iters=1, seed=-1)

    def test_zero_and_none_are_both_accepted(self):
        """0 is a legitimate seed and None means "derive it from the text" — the default. A bound
        that refused either would be its own bug."""
        from untell.scripts.run import untell_text

        assert untell_text(TEXT, tier="lite", max_iters=1, seed=0)["final"]
        assert untell_text(TEXT, tier="lite", max_iters=1, seed=None)["final"]


class TestTheCliRefusesIt:
    @staticmethod
    def _run(args: list[str]) -> subprocess.CompletedProcess:
        env = dict(os.environ, UNTELL_LITE_NO_TORCH="1", PYTHONIOENCODING="utf-8")
        return subprocess.run(
            [sys.executable, "-m", "untell.scripts.run", TEXT, "--tier", "lite",
             "--max-iters", "1", *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env, input="",
        )

    @pytest.mark.parametrize("value", ["-1", "-12345"])
    def test_a_negative_seed_exits_two(self, value: str):
        result = self._run(["--seed", value])
        assert result.returncode == 2, (
            f"--seed {value} was accepted; it is the same stream as {value.lstrip('-')}. "
            f"stdout: {result.stdout[:200]}"
        )

    def test_zero_is_still_accepted(self):
        assert self._run(["--seed", "0"]).returncode == 0


class TestTheOtherSurfacesRefuseIt:
    def test_the_rest_model_bounds_the_field(self):
        """Declared as an annotated type next to its siblings, so `run._bounds` reads the CLI's
        bound off the API rather than falling back to a literal pair."""
        pytest.importorskip("fastapi")
        from untell import api_server

        low = high = None
        for constraint in api_server._Seed.__metadata__[0].metadata:
            low = getattr(constraint, "ge", low)
            high = getattr(constraint, "le", high)
        assert low == 0 and high == 2**64 - 1

    def test_the_cli_bound_is_the_api_bound(self):
        """The indirection is real: `_SEED` must refuse what `_Seed` refuses, not a private copy."""
        pytest.importorskip("fastapi")
        import argparse

        from untell.scripts.run import _SEED

        with pytest.raises(argparse.ArgumentTypeError):
            _SEED("-1")
        assert _SEED("0") == 0
        assert _SEED(str(2**64 - 1)) == 2**64 - 1

    def test_mcp_names_the_reason_rather_than_the_range(self):
        """An MCP client reads the dict, so the message has to explain why a negative seed is not
        simply an unusual one."""
        from untell.mcp_server import _bad_args

        assert _bad_args(seed=(None, "seed")) is None
        assert _bad_args(seed=(0, "seed")) is None
        assert _bad_args(seed=(12345, "seed")) is None
        bad = _bad_args(seed=(-1, "seed"))
        assert bad is not None and "absolute value" in bad["error"]


def test_distinct_seeds_still_give_distinct_runs(stdlib_lite):
    """The property the bound protects. Without it the flag would be pointless; with it every
    accepted value has to still mean something.

    `stdlib_lite` pins UNTELL_LITE_NO_TORCH=1 (issue #18): on the torch/gpt2 path this text
    scores 0.214 < the 0.30 default threshold, so the loop answers `stopped: passed,
    iterations: 0` at every seed and all three runs return the input — the test then fails
    for the wrong reason. The distinct-stream property is about the RNG, not about the
    scoring path, so it must not depend on what the ambient environment set.
    """
    from untell.scripts.run import untell_text

    text = (
        "Moreover, it is important to note that the comprehensive framework leverages robust "
        "methodologies. Furthermore, this solution delivers value at scale, unlocking potential "
        "across the organization."
    )
    finals = {untell_text(text, tier="lite", max_iters=2, seed=s)["final"] for s in (0, 2, 7)}
    assert len(finals) > 1, "three seeds produced one output — the seed reaches nothing"
