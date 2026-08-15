"""The stdlib mode is uninformative for ranking (0.493 AUROC), not trusted.

sentences.py:93: `if modes.get("perplexity_burstiness") != "stdlib": return
False` — only non-stdlib modes are treated as informative; the stdlib path
falls through to the detector check, which declares the stdlib-only lite tier
uninformative (measured per-sentence AUROC 0.493, 91/100 sentences exactly
0.250). The mutation != -> == makes the stdlib mode short-circuit to
"informative", treating a near-constant ranking as trustworthy.
"""
from unittest.mock import patch

from untell.scripts.sentences import _targeting_is_uninformative

_PB_ONLY = [type("D", (), {"name": "perplexity_burstiness"})()]


def test_stdlib_mode_is_uninformative():
    with patch("untell.detectors.base.load_detectors", return_value=_PB_ONLY):
        assert _targeting_is_uninformative(
            "lite", {"perplexity_burstiness": "stdlib"}
        ) is True
