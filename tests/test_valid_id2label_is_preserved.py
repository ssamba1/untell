"""A valid id2label config is preserved, not rewritten.

mage.py:64: `i2l = raw.get("id2label") or {}` — a config whose id2label is a
valid str->str map must be loaded as-is. The mutation or -> and makes the
expression `raw.get("id2label") and {}` which is ALWAYS {} when id2label is
present, so the validity check fails and the loader rewrites the model's real
label scheme to the MAGE convention ("AI" -> "machine"), clobbering a shipped
config. Pinned via the full load path with mocked snapshot/transformers.
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


def test_valid_id2label_is_preserved():
    d = tempfile.mkdtemp()
    cfg = os.path.join(d, "config.json")
    with open(cfg, "w", encoding="utf-8") as f:
        json.dump({"id2label": {"0": "AI", "1": "human"}, "num_labels": 2}, f)

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
    assert raw["id2label"] == {"0": "AI", "1": "human"}, raw["id2label"]
