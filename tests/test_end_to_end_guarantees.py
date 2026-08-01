"""End-to-end guarantees — the two promises the product actually makes.

Everything else in the suite tests a component. These run the REAL loop (real preserve-lock, real
rewriters, real meaning gate) and assert the guarantees a user relies on:

1. Every locked fact survives byte-exact. Citations, numbers, percentages, URLs and quotes must come
   back identical or the tool has corrupted the user's document.
2. The output does not contradict the input.

Both were broken this session in ways no component test caught:
  - "42%" locked only its digits, so a rewrite could turn "⟦HZ0000⟧%" into "⟦HZ0000⟧ percent" and
    restore as "42 percent" with every integrity check reporting success.
  - "-15" locked as "15", dropping the sign.
  - The meaning gate passed "runs faster" -> "runs slower" at 0.974 similarity.

Detectors are stubbed so these stay fast and deterministic; the preserve-lock, rewriter and meaning
gate are all real, because those are what the guarantees depend on.
"""
from __future__ import annotations

import pytest

FACT_TEXTS = [
    (
        "Moreover, the study by Smith (2020) demonstrates that error rates fell 42% overall. "
        "Furthermore, the team utilized robust methodologies to obtain these results.",
        ["Smith (2020)", "42%"],
    ),
    (
        "It is important to note that revenue declined -15 points last quarter [12]. "
        "Additionally, the effect was significant at p<0.05 across numerous verticals.",
        ["-15", "[12]", "p<0.05"],
    ),
    (
        "Furthermore, the release v2.1.3 shipped on 2024-03-15 to numerous customers. "
        "Moreover, adoption increased 3.5% and the ratio held at 3:1 throughout.",
        ["v2.1.3", "2024-03-15", "3.5%", "3:1"],
    ),
]


def _stub_detectors(monkeypatch, score_value=0.9, stub_similarity=True):
    """Deterministic detector so the loop actually rewrites, without loading any models.

    Also stubs the embedding similarity by default: these tests assert the LOCK and the NLI
    gate, and loading sentence-transformers per test dominated the runtime (9+ minutes) for no
    added coverage of the guarantee under test.
    """
    import untell.scripts.run as run_mod
    import untell.scripts.score as score_mod

    if stub_similarity:
        monkeypatch.setattr(run_mod, "similarity", lambda a, b: 1.0)

    def _fake(text, tier="full", threshold=0.3):
        return {
            "tier": tier, "detectors": {"stub": score_value}, "max": score_value,
            "mean": score_value, "threshold": threshold, "flagged": score_value >= threshold,
        }

    # Patch the SOURCE module, not just run.py's binding. CompositeRewriter and TargetedRewriter do
    # `from untell.scripts.score import score_text` inside their rewrite() methods for their own
    # internal best-of selection, so stubbing only run_mod left them loading the real detector stack
    # — which is what made this file take 9 minutes.
    monkeypatch.setattr(score_mod, "score_text", _fake)
    monkeypatch.setattr(run_mod, "score_text", _fake)


@pytest.mark.parametrize("text,must_survive", FACT_TEXTS)
def test_every_locked_fact_survives_a_real_loop_run(monkeypatch, text, must_survive):
    """The core promise: rewrite the prose, never the facts."""
    from untell.rewriter import get_rewriter
    from untell.scripts.run import untell_text

    _stub_detectors(monkeypatch)
    res = untell_text(
        text, tier="lite", threshold=0.3, max_iters=1, best_of=1, sim_bar=0.0,
        rewriter=get_rewriter(prefer="composite"), veto_contradictions=False,
    )
    final = res["final"]
    for fact in must_survive:
        assert fact in final, (
            f"locked fact {fact!r} did not survive the loop.\nIN : {text!r}\nOUT: {final!r}"
        )


@pytest.mark.parametrize("text,must_survive", FACT_TEXTS)
def test_facts_survive_the_targeted_rewriter_too(monkeypatch, text, must_survive):
    """Sentence-targeted rewriting takes a different path through the lock — cover it explicitly."""
    from untell.rewriter import get_rewriter
    from untell.scripts.run import untell_text

    _stub_detectors(monkeypatch)
    res = untell_text(
        text, tier="lite", threshold=0.3, max_iters=1, best_of=1, sim_bar=0.0,
        rewriter=get_rewriter(prefer="targeted"), veto_contradictions=False,
    )
    for fact in must_survive:
        assert fact in res["final"], f"{fact!r} lost via the targeted rewriter: {res['final']!r}"


def test_loop_output_does_not_contradict_its_input(monkeypatch):
    """The second promise. Uses the REAL NLI gate — the component that exists because embedding
    similarity rated "runs faster" -> "runs slower" at 0.974 and let it through."""
    from untell.rewriter import get_rewriter
    from untell.scripts import entailment
    from untell.scripts.run import untell_text

    if not entailment.available():
        pytest.skip("NLI stack unavailable")

    _stub_detectors(monkeypatch)
    text = (
        "Moreover, the deployment significantly improved throughput across numerous services. "
        "Furthermore, the team utilized robust monitoring to demonstrate these gains."
    )
    res = untell_text(
        text, tier="lite", threshold=0.3, max_iters=1, best_of=1, sim_bar=0.0,
        rewriter=get_rewriter(prefer="composite"),
    )
    try:
        contradiction = entailment.contradiction_score(text, res["final"])
    except Exception:
        pytest.skip("NLI model failed to load")
    if contradiction is None:
        pytest.skip("NLI model unavailable")

    assert contradiction < 0.5, (
        f"the loop produced output contradicting its input (contradiction={contradiction:.3f})\n"
        f"IN : {text!r}\nOUT: {res['final']!r}"
    )


def test_loop_never_returns_empty_or_truncated_output(monkeypatch):
    """A rewrite that silently drops half the document would still 'pass' every detector."""
    from untell.rewriter import get_rewriter
    from untell.scripts.run import untell_text

    _stub_detectors(monkeypatch)
    text = (
        "Moreover, artificial intelligence has fundamentally transformed numerous industries. "
        "Furthermore, organizations utilize these technologies to optimize operational efficiency. "
        "Overall, the transformative impact continues to expand across various sectors."
    )
    res = untell_text(
        text, tier="lite", threshold=0.3, max_iters=1, best_of=1, sim_bar=0.0,
        rewriter=get_rewriter(prefer="composite"), veto_contradictions=False,
    )
    final = res["final"]
    assert final.strip()
    # Allow compression from plainer wording, but not the loss of a third of the document.
    assert len(final) > 0.5 * len(text), f"output truncated: {len(final)} vs {len(text)} chars"
