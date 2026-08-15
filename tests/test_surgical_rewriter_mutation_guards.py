"""Kill the surgical.py survivors found by .claude/mutate.py.

Each test calls the REAL SurgicalRewriter and either reads a real attribute or
spies on the real surgical_substitute call (delegating to the real function) —
nothing is reimplemented in the test.

Survivors killed here (module:line / mutation):
  surgical.py:46   deterministic = True -> False
  surgical.py:48   max_subs default 12 -> 13
  surgical.py:63   tier normalization `not in` -> `in` (composite label leak)
  surgical.py:96   prefer_tells=True -> False (tell-removal objective lost)
"""

from untell.rewriter import SurgicalRewriter


def test_surgical_declares_deterministic():
    """The loop collapses best_of and stops early on this flag — a False here
    costs N-1 wasted draws every round."""
    rw = SurgicalRewriter()
    assert rw.deterministic is True


def test_surgical_max_subs_default_is_twelve():
    """Default substitution budget is part of the constructor contract; the
    loop's per-iteration cap depends on it."""
    assert SurgicalRewriter().max_subs == 12


def test_surgical_normalizes_composite_tier_before_scoring(monkeypatch):
    """A browser-scorer composite label ('browser:zerogpt') is not directly
    scoreable and must be normalized to 'lite' before it reaches the real
    surgical_substitute. The spy records the kwargs and delegates, so the real
    substitution still runs on the real text."""
    import untell.attacks as attacks

    real = attacks.surgical_substitute
    seen = {}

    def spy(text, tier="lite", threshold=0.30, max_subs=8, prefer_tells=False):
        seen.update(tier=tier, threshold=threshold, max_subs=max_subs,
                    prefer_tells=prefer_tells)
        return real(text, tier=tier, threshold=threshold, max_subs=max_subs,
                    prefer_tells=prefer_tells)

    monkeypatch.setattr(attacks, "surgical_substitute", spy)

    rw = SurgicalRewriter()
    out = rw.rewrite(
        "Furthermore we utilize robust solutions.", {"tier": "browser:zerogpt"}
    )
    assert isinstance(out, str) and out.strip()
    assert seen["tier"] == "lite", f"composite tier leaked through: {seen['tier']!r}"


def test_surgical_asks_for_the_tell_removal_objective(monkeypatch):
    """The rewriter's contract is prefer_tells=True (rank by tell removal, not
    by deletion-importance). A False here silently switches ranking mode and
    the measured tell-removal gain (0.571 -> 0.233 vs 0.458) disappears."""
    import untell.attacks as attacks

    real = attacks.surgical_substitute
    seen = {}

    def spy(text, tier="lite", threshold=0.30, max_subs=8, prefer_tells=False):
        seen["prefer_tells"] = prefer_tells
        return real(text, tier=tier, threshold=threshold, max_subs=max_subs,
                    prefer_tells=prefer_tells)

    monkeypatch.setattr(attacks, "surgical_substitute", spy)

    rw = SurgicalRewriter()
    out = rw.rewrite(
        "Furthermore we utilize robust solutions.", {"tier": "lite"}
    )
    assert isinstance(out, str)
    assert seen["prefer_tells"] is True, "prefer_tells must be True"
