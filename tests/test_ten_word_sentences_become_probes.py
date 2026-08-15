"""Ten-word sentences qualify as sentence probes.

eval/detector_audit.py:398: `out += [s for s in split_sentences(para) if
len(s.split()) >= 10]` — a sentence of EXACTLY 10 words is long enough to be a
probe. The mutation >= -> > excludes it, so a probe set built from ten-word
sentences collapses to zero and the audit falls back to the 6 packaged
sentence probes, losing the measured signal the --pairs mode exists to add.
Pinned via the audit_detector spy (same pattern as the existing suite test).
"""
from unittest.mock import patch

import eval.detector_audit as audit

PARA = ". ".join(["one two three four five six seven eight nine ten"] * 10)


def test_ten_word_sentences_become_probes(monkeypatch):
    seen = []
    original = audit.audit_detector

    def spy(name, det, probes):
        if probes is not None:
            seen.append((len(probes[0]), len(probes[1])))
        return {"name": name, "ok": True, "verdict": "OK"}

    audit.audit_detector = spy
    try:
        with patch("eval.datasets.load_pairs", return_value=[(PARA, PARA)]):
            audit.audit_all(pairs=1)
    finally:
        audit.audit_detector = original

    sentence_passes = [n for n in seen if n[0] > 6]
    assert sentence_passes, f"expected a sentence pass with derived probes, saw {seen}"
    assert sentence_passes[0] == (10, 10), sentence_passes
