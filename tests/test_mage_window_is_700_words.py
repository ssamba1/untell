"""The MAGE window is 700 words — a 701-word piece never exists.

mage.py:129: `p = windowed_max(text, lambda w: float(_probs(w)[ai_idx]), 700)` —
the windowing constant. The mutation 700 -> 701 changes the piece boundaries
of a 1401-word text: under 700 the pieces are 700/700/1, under 701 they are
701/700. A stub model that scores ONLY a 701-word piece therefore reads 0.0025
(no such piece exists) under the original and 0.998 under the mutant. Pinned
via the score() seam with a size-sensitive stub model.
"""

import pytest

# `import torch` at module scope made this file a COLLECTION ERROR on the lite
# install, which ships zero ML — ten files did, so `pytest -q` was never green on
# the path CONTRIBUTING calls zero-dependency. A skip is the honest outcome: the
# test is not applicable, not broken. Install with `pip install 'untell[heavy]'`
# to run it.
pytest.importorskip("torch")
from unittest.mock import patch

import torch

import untell.detectors.mage as mage

TEXT = " ".join(["word"] * 1401)


class _Cfg:
    id2label = {"0": "machine", "1": "human"}


class _Model:
    config = _Cfg()

    def __call__(self, **kw):
        n = kw.get("_n", 0)
        logit = 3.0 if n == 701 else -3.0

        class Out:
            logits = torch.tensor([[logit, -logit]])

        return Out()


class _Tok:
    def __call__(self, text, **kw):
        return {"_n": len(text.split())}


def test_window_is_700_words():
    d = mage.MageDetector()
    with patch.object(d, "_load", return_value=(_Tok(), _Model())):
        r = d.score(TEXT)
    assert r is not None
    assert r < 0.01, f"a 701-word piece must not exist under a 700-word window, got {r!r}"
