"""Embeddings are normalized before the cosine is computed.

quality.py:162: `model.encode([a, b], normalize_embeddings=True)` — the cosine
is computed on unit vectors. The mutation True -> False leaves vectors raw:
for [1,1] vs [1,0] the normalized cosine is 0.707 but the raw dot is 1.0. The
0.76 gate bar lives on the raw-cosine scale, so the flag is part of the
measurement contract. Pinned with a fake model so no HF download is needed.
"""
from unittest.mock import patch

import numpy as np

from untell.scripts.quality import _cosine_similarity


class _FakeModel:
    def encode(self, texts, normalize_embeddings=True):
        if normalize_embeddings:
            a, b = np.array([1.0, 1.0]), np.array([1.0, 0.0])
            return np.stack(
                [a / np.linalg.norm(a), b / np.linalg.norm(b)]
            )
        return np.array([[1.0, 1.0], [1.0, 0.0]])


def test_cosine_uses_normalized_embeddings():
    with patch("untell.scripts.quality._st_model", return_value=_FakeModel()):
        cos = _cosine_similarity("a", "b")
    assert cos == 0.7071067811865475, f"expected normalized cosine, got {cos!r}"
