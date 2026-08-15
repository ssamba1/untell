"""The cosine-vs-fallback condition is not inverted (regression for fleet abb5688).

abb5688 flipped `if cos is not None:` to `if cos is None:` — the model-present
path returned token_overlap (silently degrading the semantic gate to the lite
metric) and the model-absent path crashed `max(0.0, min(1.0, None))`. This pins
both sides: a present model must yield the clamped cosine, an absent one must
yield the token-overlap fallback without raising.
"""
from unittest.mock import patch

import untell.scripts.quality as quality


def test_present_model_uses_cosine_not_token_overlap():
    with patch.object(quality, "_cosine_similarity", return_value=0.5949):
        # A cosine is available: similarity must be the clamped cosine, NOT the
        # token-overlap fallback (which the inversion returned).
        assert quality.similarity("feline rested rug", "cat lounged mat") == 0.5949


def test_absent_model_returns_token_overlap_without_crashing():
    with patch.object(quality, "_cosine_similarity", return_value=None):
        # No model: fall back to token overlap; must not raise on None.
        from untell.scripts.quality import token_overlap

        with patch.object(quality, "token_overlap", return_value=0.5) as mock_to:
            assert quality.similarity("cat dog", "cat tree") == 0.5
            mock_to.assert_called_once()
