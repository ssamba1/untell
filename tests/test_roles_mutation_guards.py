"""Killing tests for the roles.py mutation survivors (2026-08-14 sweep).

  line 82/308  identity: is not -> is   `_load() is not None` in available().
  line 218     logic: or -> and         comparison-preposition guard.
  line 269     membership: not in -> in  conditional-antecedent POS guard.
  line 273     identity: is not -> is   consequent self-head loop guard.
  line 327     logic: or -> and         empty-analysis guard.

82/308 and 327 are killed here. 218/269/273 are spaCy-parse-shape mutations —
the exact dependency trees that would distinguish them are parser artifacts, and
the existing test file (which runs only when the model is installed) already
pins the real parse shapes; the mutations would require constructing token
graphs spaCy does not produce (a self-headed token at 273 is impossible).
"""

from __future__ import annotations

from untell.scripts import roles


def test_available_is_true_when_the_parser_loads() -> None:
    """Mutation `_load() is not None` -> `_load() is None` at the availability
    return. A loadable parser must report available; the mutation would invert
    it to False on every healthy install."""
    if roles._load() is None:
        import pytest

        pytest.skip("no parser installed - the loadable path is untestable here")
    assert roles.available() is True


def test_available_false_when_the_parser_is_missing(monkeypatch) -> None:
    """The same return, from the other side: no parser -> False. The mutation
    `is None` would report True here — a phantom guarantee."""
    monkeypatch.setattr(roles, "_load", lambda: None)
    assert roles.available() is False


def test_empty_analysis_is_not_a_veto(monkeypatch) -> None:
    """Mutation `if not ta or not tb` -> `if not ta and not tb`. When ONE side
    parses to an empty role set (no roles to compare), the pair must be skipped
    as not-a-swap (False) — not compared. The mutation would only skip when BOTH
    are empty, and a one-sided empty would fall through to the comparison logic
    and could report a swap where none is provable."""
    import untell.scripts.roles as r

    def fake_analyse(text: str):
        # first call (a) returns empty roles, second (b) returns a real triple
        if text == "a":
            return (), ()
        return (("verb", "give", ("subj",), ("obj",)),), ()

    monkeypatch.setattr(r, "_analyse", fake_analyse)
    assert r.role_swap("a", "b") is False
