"""The voice tie-break costs no tells and up to 0.02 of detector score. Three surfaces said zero.

`voice_sample` picks, among best-of-N candidates, the one whose sentence length, rhythm and comma
rate sit closest to a sample of the caller's own writing. The CLI help, the MCP tool docstring and
the REST field comment all described it as a tie-break that "never costs evasion".

MEASURED with the same seed on both arms, so the only difference is the tie-break, over 12 HC3
texts:

    voice distance   4 closer, 0 farther, 8 unchanged
    detector max     3 worse: +0.0019, +0.0063, +0.0094

The direction is right and the feature works. The absolute claim is not: `near` holds every
candidate within `_TELLS_EPS` (0.02) of the best detector max, so voice can promote one that
scores slightly worse. That is the design — the band is defined as detector noise — but a caller
reading "never costs evasion" and then seeing their score rise has been told something untrue.

These tests pin the ORDER of the selection key, which is what bounds the cost, rather than
re-running a 12-text corpus measurement on every CI run.
"""
from __future__ import annotations

import inspect

from untell.scripts import run as run_module


def test_the_noise_band_is_what_bounds_the_cost():
    """If this grew, the wording fixed in this commit would understate the cost again."""
    assert run_module._TELLS_EPS == 0.02


def test_voice_is_ranked_after_tells_and_before_the_score_tiebreaks():
    """Order is the guarantee. Ahead of tells, voice could cost naturalness without limit."""
    source = inspect.getsource(run_module)
    # From the `min(` to the end of its key tuple. Splitting on the first ")" cuts inside
    # `_voice_key(v[0], voice_sample)` and silently drops the rest of the key — which is how the
    # first version of this test looked for `mean` in a slice that could not contain it.
    key = source.split("cand_best, cand_best_score, _ = min(", 1)[1][:400]

    tells_pos = key.index("v[2]")
    voice_pos = key.index("_voice_key")
    mean_pos = key.index('v[1].get("mean"')

    assert tells_pos < voice_pos < mean_pos, (
        "the selection key no longer runs tells -> voice -> score; voice ahead of tells would let "
        "a style match cost AI tells, which is the one thing it is documented never to do"
    )


def test_no_surface_still_claims_the_tiebreak_is_free():
    """The wording, on all three surfaces a caller can read it from."""
    from untell import api_server, mcp_server

    for module in (run_module, mcp_server, api_server):
        source = inspect.getsource(module)
        assert "never costs evasion" not in source, f"{module.__name__} still claims zero cost"
        assert "never cost evasion" not in source, f"{module.__name__} still claims zero cost"


def test_every_surface_names_the_band():
    """Replacing an absolute claim with a vague one would be no better."""
    from untell import api_server, mcp_server

    for module in (run_module, mcp_server, api_server):
        assert "0.02" in inspect.getsource(module), (
            f"{module.__name__} no longer tells the reader what the tie-break can cost"
        )


def test_no_sample_leaves_selection_untouched():
    """The claim that matters for everyone who never passes a sample."""
    assert run_module._voice_key("anything at all", None) == 0.0
    assert run_module._voice_key("anything at all", "") == 0.0
    assert run_module._voice_key("anything at all", "   ") == 0.0
