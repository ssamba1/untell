"""A broken (empty) id2label config IS rewritten to the MAGE convention.

mage.py:65: `if not (i2l and all(isinstance(v, str) for v in i2l.values())):` —
an empty or non-str id2label must be replaced. The mutation and -> or makes
the expression `not (i2l or all(...))`: with i2l empty, `all(...)` over no
values is True, so the whole thing is False and the rewrite is SKIPPED — the
config stays broken and the model fails validation at construction. Pinned
via the full load path with mocked snapshot/transformers.
"""
import json
import os
import tempfile
from unittest.mock import patch

import untell.detectors.mage as mage


class _StubTok:
    @staticmethod
    def from_pretrained(local):
        return object()


class _StubModel:
    @staticmethod
    def from_pretrained(local):
        class M:
            def eval(self):
                return self

        return M()


def test_empty_id2label_is_rewritten():
    d = tempfile.mkdtemp()
    cfg = os.path.join(d, "config.json")
    with open(cfg, "w", encoding="utf-8") as f:
        json.dump({"num_labels": 2}, f)  # no id2label at all

    mage.MageDetector._model = None
    mage.MageDetector._tok = None
    try:
        with patch("huggingface_hub.snapshot_download", return_value=d), \
             patch("transformers.AutoTokenizer", _StubTok), \
             patch("transformers.AutoModelForSequenceClassification", _StubModel):
            mage.MageDetector()._load()
        raw = json.load(open(cfg, encoding="utf-8"))
    finally:
        mage.MageDetector._model = None
        mage.MageDetector._tok = None
    assert raw.get("id2label") == {"0": "machine", "1": "human"}, raw
    assert raw.get("num_labels") == 2
