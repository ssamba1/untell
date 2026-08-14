"""The CLI's own boundary check is pinned: similarity EXACTLY at the bar must pass.

quality.py:263 `passes()` is killed by test_similarity_exactly_at_bar_passes.py,
but the CLI at quality.py:302 computes `sim >= bar` INLINE — it does not call
`passes()`. The old survivors-table note claimed the same test killed both via
"shared logic"; that was wrong, and a mutation run proved it (302 survived with
the passes()-killing test in the set). This test pins the CLI copy directly:
same exact-bar pair (1 shared of 4 unique = Dice 0.5 = TOKEN_BAR), through
`quality_main`, asserting the JSON "passes" field flips.
"""
import json

import untell.scripts.quality as quality
from untell.scripts.quality import main as quality_main


def test_cli_passes_exactly_at_bar(monkeypatch, capsys):
    monkeypatch.setattr(quality, "_model", None)  # force the token-overlap path
    rc = quality_main(["cat dog", "cat tree"])
    assert rc == 0
    parsed = json.loads(capsys.readouterr().out)
    # 1 shared of 4 unique = Dice 0.5 = TOKEN_BAR exactly; must be True, not rejected.
    assert parsed["similarity"] == 0.5
    assert parsed["bar"] == quality.TOKEN_BAR
    assert parsed["passes"] is True


def test_cli_rejects_below_bar(monkeypatch, capsys):
    monkeypatch.setattr(quality, "_model", None)
    rc = quality_main(["cat dog", "tree bush"])  # 0 shared tokens
    assert rc == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["passes"] is False
