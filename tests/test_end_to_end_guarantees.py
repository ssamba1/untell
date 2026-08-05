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

# Every test here loads a real model; see the `slow` marker note in pyproject.toml.
pytestmark = pytest.mark.slow

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


class TestRepeatedHumanizationConverges:
    """Running the loop on its own output must converge, not drift.

    Re-running is ordinary user behaviour ("still flagged, try again"), and the failure it invites
    is silent: each pass is individually gated for meaning, but nothing checks the composition. A
    loop that kept finding new rewrites would walk away from the ORIGINAL a little at a time while
    every single step passed its gate.

    MEASURED on three real HC3 paragraphs, three passes each: pass 1 improves, passes 2 and 3 are
    bit-identical, and similarity to the original holds at 0.96-0.99 throughout. One document needed
    two passes (0.558 -> 0.388 -> 0.224) and then froze.
    """

    AI_TEXT = (
        "Furthermore, artificial intelligence has fundamentally transformed numerous industries. "
        "Moreover, organizations increasingly leverage these robust technologies to optimize "
        "operational efficiency. Overall, the transformative impact continues to expand across "
        "various sectors, and it is important to note that adoption keeps accelerating."
    )

    def _passes(self, n: int):
        from untell.scripts.quality import similarity
        from untell.scripts.run import untell_text

        original = current = self.AI_TEXT
        out = []
        for _ in range(n):
            r = untell_text(current, tier="lite", rewriter="composite", threshold=0.30,
                            max_iters=2, best_of=2)
            assert "error" not in r, r.get("error")
            current = r["final"]
            out.append((current, similarity(original, current)))
        return out

    def test_a_second_pass_does_not_drift_from_the_original(self):
        results = self._passes(3)
        sims = [s for _, s in results]
        assert sims[-1] >= sims[0] - 0.05, f"similarity to original decayed across passes: {sims}"

    def test_output_stabilises(self):
        """Once the loop stops flagging, further passes must be a no-op — not an endless reroll."""
        texts = [t for t, _ in self._passes(3)]
        assert texts[-1] == texts[-2], "loop kept rewriting text it had already accepted"

    def test_length_does_not_run_away(self):
        texts = [t for t, _ in self._passes(3)]
        assert 0.5 * len(self.AI_TEXT) < len(texts[-1]) < 2.0 * len(self.AI_TEXT)


class TestFactsSurviveAtScaleOnRealProse:
    """The hand-made cases above prove the mechanism; this proves it does not fail RARELY.

    docs/free-ceiling-measured.md says outright that no ceiling figure exercises this machinery —
    the built-in corpus has zero locked spans — so the fact guarantee is covered only here. A
    corruption that fires on one paragraph in fifty would pass every test above and never appear in
    any published number.

    Measured over 80 runs (40 real HC3 paragraphs with facts spliced in, x 2 seeds): 0 sentinels
    lost, 0 duplicated, 0 facts altered. Reduced to the packaged corpus so it needs no download.
    """

    FACTS = [
        "Smith (2020) reported 47% adoption.",
        "See https://example.org/a_b/c?d=1#e for the full table.",
        'The report called it "a decisive shift" on March 3, 2021.',
        "Revenue reached $1,234,567.89 in Q4 2023.",
        "Contact hello@example.com or call +1 (555) 010-9999.",
        "The ratio was 3.5:1 across 12,000 samples (p < 0.001).",
    ]

    def _corpus(self):
        from eval.ceiling import _SAMPLE
        from eval.datasets import _BUILTIN

        return list(_BUILTIN) + list(_SAMPLE)

    @pytest.mark.parametrize("seed", [0, 1, 2])
    def test_no_locked_span_is_lost_altered_or_duplicated(self, seed):
        import random

        from untell.rewriter import get_rewriter
        from untell.scripts.preserve import SENTINEL_RE, lock, restore

        rw = get_rewriter(prefer="composite")
        score = {"tier": "lite", "max": 0.9, "detectors": {}}

        for i, base in enumerate(self._corpus()):
            text = f"{self.FACTS[i % len(self.FACTS)]} {base}"
            random.seed(seed * 977 + i)
            masked, mapping = lock(text)
            expected = SENTINEL_RE.findall(masked)
            assert expected, f"nothing locked in {text[:60]!r} — the probe would prove nothing"

            out = rw.rewrite(masked, score, 0.30)
            got = SENTINEL_RE.findall(out)
            assert sorted(got) == sorted(expected), (
                f"sentinels changed (seed {seed}, text {i}): "
                f"lost={sorted(set(expected) - set(got))} extra={sorted(set(got) - set(expected))}"
            )

            final = restore(out, mapping)
            for literal in mapping.values():
                assert literal in final, f"fact not restored byte-exact (seed {seed}, text {i}): {literal!r}"
