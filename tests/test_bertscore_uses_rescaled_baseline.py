"""BERTScore is constructed with rescale_with_baseline=True.

quality.py:78: `BERTScorer(lang="en", rescale_with_baseline=True)` — rescaling
maps raw F1 onto a calibrated [0,1] scale where 0.88 is the faithful-paraphrase
bar (raw F1 would sit ~0.93+ and need a different bar, per the comment). The
mutation True -> False silently switches the scorer to its raw scale. Pinned by
capturing the constructor kwargs via monkeypatched bert_score.BERTScorer.
"""
import bert_score

import untell.scripts.quality as quality


def test_bertscore_constructed_with_rescale(monkeypatch):
    captured = {}

    class _Fake:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(bert_score, "BERTScorer", _Fake)
    old = quality._bs_model
    quality._bs_model = quality._UNSET
    try:
        quality._bs_scorer()
    finally:
        quality._bs_model = old
    assert captured.get("rescale_with_baseline") is True, captured
