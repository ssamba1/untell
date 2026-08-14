"""similarity uses the embedding cosine when the backend returns a value.

quality.py:230: `if cos is not None: return clamp(cos)` — the embedding backend
is the meaning gate. The mutation is not -> is makes the check fire on None,
so a normal non-None cosine falls through to token_overlap: with the backend
pinned to a fixed 0.5 cosine, the original returns 0.5 (clamped) while the
mutant returns 0.0 (token overlap for 'cat' vs 'dog', no shared tokens). The
0.76 gate bar lives on the raw-cosine scale, so the backend swap is not
scale-invariant.
"""
from unittest.mock import patch

from untell.scripts.quality import similarity, token_overlap


def test_similarity_uses_cosine_when_backend_returns_value():
    with patch(
        "untell.scripts.quality._cosine_similarity", return_value=0.5
    ):
        assert similarity("cat", "dog") == 0.5


def test_token_overlap_is_below_pinned_cosine():
    # Control: with no backend override, token overlap alone scores 0.0.
    assert token_overlap("cat", "dog") == 0.0
