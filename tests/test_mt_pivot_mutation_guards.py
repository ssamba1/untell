"""Kill the mt_pivot.py survivors found by .claude/mutate.py.

The MT backend is stubbed exactly as tests/test_bugfixes.py already stubs it
(monkeypatched _bt.available / _bt.back_translate); the code under test — the
guard, the flag, and the sentinel bookkeeping in MTPivotRewriter — is real.

Survivors killed here (module:line / mutation):
  mt_pivot.py:54   deterministic = True -> False
  mt_pivot.py:64   `or` -> `and` in the empty/available guard
"""

from untell.rewriter.mt_pivot import MTPivotRewriter


def test_mt_pivot_declares_deterministic():
    """The loop collapses best_of on this flag. Beam search with num_beams=4 and
    no sampling makes identical input -> identical output, so the True is the
    honest declaration (and the loop depends on it)."""
    rw = MTPivotRewriter()
    assert rw.deterministic is True


def test_mt_pivot_does_not_call_backend_when_unavailable(monkeypatch):
    """The guard `not text.strip() or not self.available()` must short-circuit
    BEFORE any MT work. With `or` flipped to `and`, a non-empty text with an
    unavailable backend falls through into the translation path — the backend
    gets consulted (and the text goes through sentinel swap + back_translate)
    instead of being returned untouched."""
    rw = MTPivotRewriter()
    calls: list[str] = []

    monkeypatch.setattr(rw._bt, "available", lambda: False)
    monkeypatch.setattr(
        rw._bt,
        "back_translate",
        lambda text, pivots=("fr",): calls.append(text) or "TRANSLATED",
    )

    text = "AI changed ⟦HZ0000⟧ significantly."
    out = rw.rewrite(text, {})
    assert out == text  # unavailable backend -> safe no-op
    assert calls == []  # and the backend was never consulted
