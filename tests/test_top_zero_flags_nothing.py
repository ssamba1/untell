"""top=0 must mean "flag nothing", not "raise".

sentences.py:209: `elif top < 0: raise ValueError` — only NEGATIVE top is a
refusal. The mutation < -> <= makes top=0 raise too, turning the documented
"flag nothing" count into an exception. top=0 is a legitimate request: the
CLI may pass 0 and the caller expects an empty flagged list.
"""
from untell.scripts.sentences import score_sentences


def test_top_zero_flags_nothing(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    r = score_sentences("One sentence here. Two sentences here.", tier="lite", top=0)
    assert r["flagged"] == []


def test_negative_top_raises(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    try:
        score_sentences("One sentence here. Two sentences here.", tier="lite", top=-1)
    except ValueError:
        pass
    else:
        raise AssertionError("negative top must raise ValueError")
