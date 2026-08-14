"""A similarity EXACTLY at the bar must pass.

quality.py:263: `similarity(a, b) >= bar`. The mutation >= -> > rejects a rewrite
whose similarity equals the bar exactly. The token-overlap path makes exact
equality reachable: 1 shared token of 4 unique gives Dice = 2*1/4 = 0.5, which
IS TOKEN_BAR (0.50). The prior 'measure-zero with floats' note was wrong — the
token path produces exact rationals.
"""
import untell.scripts.quality as quality


def test_similarity_exactly_at_bar_passes(monkeypatch):
    monkeypatch.setattr(quality, "_model", None)  # force the token-overlap path
    assert quality.recommended_bar() == quality.TOKEN_BAR
    assert quality.passes("cat dog", "cat tree") is True


def test_similarity_below_bar_fails(monkeypatch):
    monkeypatch.setattr(quality, "_model", None)
    # 0 shared tokens of 4 unique: Dice = 0 < 0.5
    assert quality.passes("cat dog", "tree bush") is False
