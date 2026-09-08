"""The human index resolves from the label_1 fallback.

mage.py:121: `if "human" in str(v).lower() or str(v).lower() in
("label_1", "real")` — a model whose human label is exported as "label_1"
must resolve via the fallback. The mutation or -> and makes the condition
unsatisfiable ("label_1" can't contain "human"), so the detector returns None
— no score at all — instead of 1-P(human). Prior 'needs live model.config'
note wrong; the seam is a stub model.
"""

import pytest

# Without this the module raised ImportError at COLLECTION, which aborts the whole run
# (`Interrupted: N errors during collection`) rather than skipping one file. That is why
# the lite CI job reported "7 skipped, 127 deselected, 6 errors" and ran no tests at all.
pytest.importorskip("torch")

from unittest.mock import patch  # noqa: E402

import torch  # noqa: E402

import untell.detectors.mage as mage  # noqa: E402


class _Cfg:
    id2label = {"0": "spam", "1": "label_1"}


class _Model:
    config = _Cfg()

    def __call__(self, **kw):
        class Out:
            logits = torch.tensor([[-2.0, 2.0]])

        return Out()


class _Tok:
    def __call__(self, text, **kw):
        return {}


def test_human_index_resolves_from_label_1():
    d = mage.MageDetector()
    with patch.object(d, "_load", return_value=(_Tok(), _Model())):
        r = d.score("some text here")
    assert r is not None, "label_1 fallback must resolve a score"
    assert 0.0 < r < 1.0
