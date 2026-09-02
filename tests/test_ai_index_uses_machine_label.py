"""The AI index resolves from the machine label, not the human fallback.

mage.py:112: `if "machine" in str(v).lower() or str(v).lower() in
("label_0", "ai", "fake")` — the AI index is the label mentioning machine. The
mutation or -> and makes the condition impossible (a label can't both contain
"machine" AND equal "label_0"), so the search falls through to the human
fallback. For a 2-class model 1-P(human) == P(machine) hides it; a 3-class
model exposes the wrong index: P(machine)=0.0009 vs 1-P(human)=0.5002.
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


class _Cfg:
    id2label = {"0": "machine", "1": "human", "2": "neutral"}


class _Model:
    config = _Cfg()

    def __call__(self, **kw):
        class Out:
            logits = torch.tensor([[-5.0, 2.0, 2.0]])

        return Out()


class _Tok:
    def __call__(self, text, **kw):
        return {}


def test_ai_index_uses_machine_label():
    d = mage.MageDetector()
    with patch.object(d, "_load", return_value=(_Tok(), _Model())):
        r = d.score("some text here")
    assert r is not None
    assert r < 0.01, f"expected the machine probability, got {r!r}"
