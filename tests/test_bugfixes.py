"""Regression tests for the five loop/rewriter correctness bugs fixed this session.

Each test pins the exact failure mode so the fix cannot silently regress:

* Bug 1 — a candidate that DUPLICATES a locked sentinel must be rejected (multiset, not set).
* Bug 2 — participial-trailer flattening must slice by match offset, not assume ``", verb"``.
* Bug 3 — ``boasts`` flattens to ``has`` (not ``is``); ``marks`` is a real verb, left untouched.
* Bug 4 — a score with no real detector signal must never be declared a "pass".
* Bug 5 — reported similarity must reflect the true final output after polish, not stale locked text.
"""
from __future__ import annotations

from untell.scripts.quality import similarity


def _num_score(mx: float, flagged: bool = True):
    """A fake score_text returning a real numeric detector signal at ``mx``."""
    def _s(text, tier="full", threshold=0.3):
        return {
            "tier": tier,
            "detectors": {"perplexity_burstiness": mx},
            "max": mx,
            "mean": mx,
            "threshold": threshold,
            "flagged": flagged,
        }
    return _s


class _NoOp:
    name = "noop"
    deterministic = True

    def available(self) -> bool:
        return True

    def rewrite(self, text, score, threshold: float = 0.3) -> str:
        return text


# --------------------------------------------------------------------------- Bug 1
def test_duplicate_sentinel_candidate_is_rejected(monkeypatch):
    """A rewrite that duplicates a locked span must be thrown out, or restore doubles the citation."""
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "score_text", _num_score(0.9))

    class _Dup:
        name = "dup"
        deterministic = True

        def available(self) -> bool:
            return True

        def rewrite(self, text, score, threshold: float = 0.3) -> str:
            from untell.scripts.preserve import SENTINEL_RE

            m = SENTINEL_RE.search(text)
            return f"{text} {m.group(0)}" if m else text  # duplicate a sentinel

    out = run_mod.untell_text(
        "AI changed the field [1] a lot. It works well overall.",
        tier="lite", threshold=0.3, max_iters=2, rewriter=_Dup(), scrub=False, sim_bar=0.0,
    )
    assert out["final"].count("[1]") == 1        # citation NOT duplicated on restore
    assert out["rewrites"] >= 1                   # the dup rewriter really ran
    assert out["stopped"] in ("stalled", "max_iters")  # dup candidate never adopted


# --------------------------------------------------------------------------- Bug 2
def test_participial_offset_survives_extra_whitespace():
    from untell.rewriter.structural import _flatten_participial_trailers

    # Two spaces after the comma: the old len(", verb") slice ate a char ("underscoresg its ...").
    out = _flatten_participial_trailers("The system evolved,  underscoring its importance.")
    assert "underscores its importance" in out
    assert "underscoresg" not in out          # no eaten/duplicated boundary char
    assert ", underscoring" not in out


def test_participial_single_space_still_works():
    from untell.rewriter.structural import _flatten_participial_trailers

    out = _flatten_participial_trailers("The system evolved rapidly, underscoring its importance.")
    assert "underscores its importance" in out
    assert ", underscoring" not in out


# --------------------------------------------------------------------------- Bug 3
def test_boasts_flattens_to_has_not_is():
    from untell.rewriter.structural import _flatten_copula

    assert _flatten_copula("The city boasts a museum.") == "The city has a museum."


def test_marks_is_not_flattened():
    from untell.rewriter.structural import _flatten_copula

    # "marks" is a genuine transitive verb here — flattening to "is" would corrupt meaning.
    assert _flatten_copula("The referee marks the score.") == "The referee marks the score."


def test_serves_as_still_flattens_to_is():
    from untell.rewriter.structural import _flatten_copula

    assert _flatten_copula("Python serves as a scripting language.") == "Python is a scripting language."


# --------------------------------------------------------------------------- Bug 4
def test_no_pass_on_vacuous_all_failed_score(monkeypatch):
    """Every detector errored -> low placeholder max -> must NOT be reported as a pass."""
    import untell.scripts.run as run_mod

    def _all_failed(text, tier="full", threshold=0.3):
        return {
            "tier": tier,
            "detectors": {"perplexity_burstiness": None, "perplexity_burstiness__error": "boom"},
            "max": 0.1,  # below threshold, but there is NO real signal behind it
            "mean": 0.1,
            "threshold": threshold,
            "flagged": False,
        }

    monkeypatch.setattr(run_mod, "score_text", _all_failed)
    out = run_mod.untell_text(
        "Some plain sentence with no citations at all here.",
        tier="lite", threshold=0.3, max_iters=2, rewriter=_NoOp(), scrub=False,
    )
    assert out["stopped"] != "passed"


def test_real_low_signal_still_passes(monkeypatch):
    """The guard must not break a legitimate pass on a real, numeric, low score."""
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "score_text", _num_score(0.1, flagged=False))
    out = run_mod.untell_text(
        "Some plain sentence with no citations at all here.",
        tier="lite", threshold=0.3, max_iters=2, rewriter=_NoOp(), scrub=False, sim_bar=0.0,
    )
    assert out["stopped"] == "passed"


# --------------------------------------------------------------------------- Bug 5
def test_polish_reports_true_similarity(monkeypatch):
    """After polish rewrites the restored text, similarity must compare original->final, not stale."""
    import untell.attacks as attacks_mod
    import untell.scripts.run as run_mod

    src = "The quick brown fox jumps over the lazy dog every single morning."
    polished = "The quick brown fox leaps over the lazy dog every single morning."

    # Polish must genuinely IMPROVE the score to be adopted (ties go to the unpolished text), so
    # score the polished variant strictly lower than everything else.
    def _score(text, tier="full", threshold=0.3):
        m = 0.02 if text == polished else 0.10
        return {"tier": tier, "detectors": {"perplexity_burstiness": m}, "max": m, "mean": m,
                "threshold": threshold, "flagged": False}

    monkeypatch.setattr(run_mod, "score_text", _score)
    monkeypatch.setattr(
        attacks_mod, "surgical_substitute",
        lambda t, tier=None, threshold=0.3: {"text": polished},
    )
    out = run_mod.untell_text(
        src, tier="lite", threshold=0.3, max_iters=1, rewriter=_NoOp(),
        polish=True, scrub=False, sim_bar=0.1,
    )
    assert out["final"] == polished
    assert abs(out["similarity"] - similarity(src, polished)) < 1e-9


# --------------------------------------------------------------------------- Bug 1 (mt_pivot + t5)
def test_mt_pivot_duplicate_sentinel_falls_back(monkeypatch):
    from untell.rewriter.mt_pivot import MTPivotRewriter

    rw = MTPivotRewriter()
    monkeypatch.setattr(rw._bt, "available", lambda: True)
    monkeypatch.setattr(rw._bt, "back_translate", lambda text, pivots=("fr",): f"{text} {text}")
    masked = "AI changed ⟦HZ0000⟧ significantly."
    assert rw.rewrite(masked, {}) == masked  # dup placeholder -> safe no-op


def test_mt_pivot_keeps_a_rewrite_that_preserved_a_repeated_sentinel(monkeypatch):
    """A locked entity mentioned twice must not disable the rewriter.

    The survival check compared the output's sentinel counts against a *deduplicated* list, so a
    second mention of the same entity always looked like MT had duplicated it. Any text naming a
    person, place or org more than once — the normal case — got the original back untouched.
    """
    from untell.rewriter.mt_pivot import MTPivotRewriter

    rw = MTPivotRewriter()
    monkeypatch.setattr(rw._bt, "available", lambda: True)
    # Faithful MT: placeholders copied verbatim, surrounding wording changed.
    monkeypatch.setattr(
        rw._bt, "back_translate", lambda text, pivots=("fr",): text.replace("visited", "went to")
    )
    masked = "⟦HZ0000⟧ visited ⟦HZ0001⟧, and ⟦HZ0000⟧ stayed for a week."

    out = rw.rewrite(masked, {})
    assert out != masked  # the rewrite was kept, not discarded
    assert out.count("⟦HZ0000⟧") == 2 and out.count("⟦HZ0001⟧") == 1


def test_mt_pivot_still_rejects_a_dropped_repeat(monkeypatch):
    """Loosening the check must not stop it catching a genuinely lost occurrence."""
    from untell.rewriter.mt_pivot import MTPivotRewriter

    rw = MTPivotRewriter()
    monkeypatch.setattr(rw._bt, "available", lambda: True)
    monkeypatch.setattr(
        rw._bt,
        "back_translate",
        lambda text, pivots=("fr",): text.replace("ZQXMARK0ZQX stayed", "he stayed"),
    )
    masked = "⟦HZ0000⟧ visited ⟦HZ0001⟧, and ⟦HZ0000⟧ stayed for a week."
    assert rw.rewrite(masked, {}) == masked  # one of the two occurrences lost -> no-op


def test_t5_drops_sentinel_falls_back(monkeypatch):
    from untell.rewriter.t5_paraphrase import T5ParaphraseRewriter

    rw = T5ParaphraseRewriter()
    monkeypatch.setattr(rw, "available", lambda: True)
    monkeypatch.setattr(rw, "_paraphrase_one", lambda s: "totally reworded with no marker at all")
    masked = "AI changed ⟦HZ0000⟧ dramatically."
    assert rw.rewrite(masked, {}) == masked


def test_t5_keeps_a_paraphrase_that_preserved_a_repeated_sentinel(monkeypatch):
    """Same deduplicated-vs-counted mismatch as mt_pivot, same silent no-op."""
    from untell.rewriter.t5_paraphrase import T5ParaphraseRewriter

    rw = T5ParaphraseRewriter()
    monkeypatch.setattr(rw, "available", lambda: True)
    monkeypatch.setattr(rw, "_paraphrase_one", lambda s: s.replace("visited", "went to"))
    masked = "⟦HZ0000⟧ visited ⟦HZ0001⟧. Later ⟦HZ0000⟧ left."

    out = rw.rewrite(masked, {})
    assert out != masked
    assert out.count("⟦HZ0000⟧") == 2 and out.count("⟦HZ0001⟧") == 1


def test_no_rewriter_compares_output_sentinels_against_a_deduplicated_list():
    """Grep guard for the bug class, in both places it was found and anywhere it is added next.

    `Counter(findall(output)) != Counter(dedup(findall(source)))` is always wrong: the left side
    counts occurrences and the right side counts distinct values, so repeated sentinels never
    match and the caller silently falls back. run.py and targeted.py already compare findall to
    findall; this keeps it that way.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    offenders = [
        p.relative_to(root).as_posix()
        for p in root.glob("untell/**/*.py")
        if re.search(r"dict\.fromkeys\(\s*_SENTINEL_RE\.findall", p.read_text(encoding="utf-8", errors="replace"))
    ]
    assert not offenders, (
        f"{offenders} deduplicate sentinels before a Counter comparison — compare findall to "
        "findall, or the rewriter no-ops on any text naming an entity twice"
    )


def test_t5_preserves_copied_sentinel(monkeypatch):
    from untell.rewriter.t5_paraphrase import T5ParaphraseRewriter

    rw = T5ParaphraseRewriter()
    monkeypatch.setattr(rw, "available", lambda: True)
    monkeypatch.setattr(rw, "_paraphrase_one", lambda s: s.replace("changed", "transformed"))
    masked = "AI changed ⟦HZ0000⟧ dramatically."
    out = rw.rewrite(masked, {})
    assert out.count("⟦HZ0000⟧") == 1 and "transformed" in out


def test_t5_duplicate_sentinel_falls_back(monkeypatch):
    from untell.rewriter.t5_paraphrase import T5ParaphraseRewriter

    rw = T5ParaphraseRewriter()
    monkeypatch.setattr(rw, "available", lambda: True)
    monkeypatch.setattr(rw, "_paraphrase_one", lambda s: f"{s} {s}")
    masked = "AI changed ⟦HZ0000⟧ dramatically."
    assert rw.rewrite(masked, {}) == masked


# --------------------------------------------------------------------------- tells-aware selection
def test_tells_tiebreak_prefers_fewer_tells(monkeypatch):
    """Among best-of-N candidates that tie on detector score, keep the more human-reading one."""
    import untell.scripts.run as run_mod

    # Both candidates score identically -> the tie-break must decide on AI tells.
    monkeypatch.setattr(run_mod, "score_text", _num_score(0.50))

    # Source deliberately free of lockable spans: preserve.lock masks entities like "AI", and a fake
    # rewriter that emits a fixed string would drop the sentinel and be (correctly) rejected — which
    # would test the sentinel guard, not the tells tie-break this test is about.
    source = "Some sample paragraph to rewrite here now."
    tell_heavy = "Moreover, it is important to note that we leverage robust synergies across verticals."
    tell_light = "We use a few tools."
    draws = iter([tell_heavy, tell_light])

    class _RW:
        name = "tw"
        deterministic = False

        def available(self):
            return True

        def rewrite(self, text, score, threshold=0.3):
            return next(draws)

    out = run_mod.untell_text(
        source,
        tier="lite", threshold=0.3, max_iters=1, best_of=2, rewriter=_RW(), scrub=False, sim_bar=0.0, veto_contradictions=False,
    )
    assert out["final"] == tell_light  # equal detector score -> fewer-tells candidate wins


def test_tells_tiebreak_never_loses_a_better_adoptable_candidate(monkeypatch):
    """The tells tie-break must NOT displace a lower-detector candidate with a worse-but-fewer-tells
    one, or the strict outer adoption guard silently drops the real improvement (bug-hunt HIGH)."""
    import untell.scripts.run as run_mod

    orig = "Original sample paragraph here to rewrite right now."
    a_text = "Moreover, it is important to note that we leverage robust synergies across verticals."  # many tells
    b_text = "We shifted fast."  # few tells
    # A (0.295) is adoptable vs the running best (pre=0.30); B (0.31) is NOT. B has fewer tells.
    scores = {orig: 0.30, a_text: 0.295, b_text: 0.31}

    def _fake_score(text, tier="full", threshold=0.3):
        m = scores.get(text, 0.30)
        return {"tier": tier, "detectors": {"perplexity_burstiness": m}, "max": m, "mean": m,
                "threshold": threshold, "flagged": m >= 0.3}

    monkeypatch.setattr(run_mod, "score_text", _fake_score)
    draws = iter([a_text, b_text])

    class _RW:
        name = "tw"
        deterministic = False

        def available(self):
            return True

        def rewrite(self, text, score, threshold=0.3):
            return next(draws)

    out = run_mod.untell_text(
        orig, tier="lite", threshold=0.30, max_iters=1, best_of=2, rewriter=_RW(), scrub=False, sim_bar=0.0, veto_contradictions=False,
    )
    assert out["final"] == a_text  # the 0.295 improvement is kept, not lost to B's fewer tells


def test_selection_breaks_ties_on_ensemble_mean(monkeypatch):
    """Two candidates tie on max and tells -> prefer the one that also improves the OTHER detectors.

    `max` alone is blind to a candidate that guts every detector below the max; the ensemble mean
    captures that, so a genuinely better-everywhere rewrite wins the tie."""
    import untell.scripts.run as run_mod

    orig = "Original sample paragraph here to rewrite right now."
    flat = "We use tools."      # same max, high mean (other detectors unmoved)
    deep = "We use gear."       # same max, LOW mean (other detectors also improved)
    table = {orig: (0.30, 0.30), flat: (0.20, 0.60), deep: (0.20, 0.10)}

    def _fake_score(text, tier="full", threshold=0.3):
        mx, mn = table.get(text, (0.30, 0.30))
        return {"tier": tier, "detectors": {"a": mx, "b": mn}, "max": mx, "mean": mn,
                "threshold": threshold, "flagged": mx >= 0.3}

    monkeypatch.setattr(run_mod, "score_text", _fake_score)
    draws = iter([flat, deep])

    class _RW:
        name = "tw"
        deterministic = False

        def available(self):
            return True

        def rewrite(self, text, score, threshold=0.3):
            return next(draws)

    out = run_mod.untell_text(
        orig, tier="lite", threshold=0.30, max_iters=1, best_of=2, rewriter=_RW(), scrub=False, sim_bar=0.0, veto_contradictions=False,
    )
    assert out["final"] == deep  # tie on max+tells -> lower ensemble mean wins


def test_ensemble_does_not_trade_away_a_lower_detector(monkeypatch):
    """MEASURED failure: max-only ranking let a member that nudged `max` while wrecking a lower
    detector win (roberta 0.002 -> 0.933 on one sample). Rank on (max, mean) instead."""
    from untell.rewriter.ensemble import EnsembleRewriter

    rw = EnsembleRewriter()

    class _M:
        def __init__(self, out):
            self._out = out

        def rewrite(self, text, score_result, threshold=0.30):
            return self._out

    good = "member A output"   # same max, much better across the rest of the ensemble
    bad = "member B output"    # same max, wrecks the lower detector
    rw._members = [("a", _M(good)), ("b", _M(bad))]

    import untell.scripts.score as score_mod

    table = {
        "orig text here": (0.90, 0.90),
        good: (0.700, 0.10),   # max ties with bad, mean far lower
        bad: (0.695, 0.65),    # microscopically lower max, much worse mean
    }

    def _fake_score(text, tier="lite", threshold=0.30):
        mx, mn = table.get(text, (0.99, 0.99))
        return {"max": mx, "mean": mn, "detectors": {"a": mx, "b": mn}, "tier": tier}

    monkeypatch.setattr(score_mod, "score_text", _fake_score)
    out = rw.rewrite("orig text here", {"tier": "lite"})
    assert out == good  # within the max noise band -> the better-everywhere candidate wins


def test_ensemble_declines_to_touch_already_clean_text(monkeypatch):
    """No-harm guarantee: if no member beats the original, the ORIGINAL is returned unchanged.

    The measurement that exposed the max-only ranking bug had an already-clean sample driven from
    0.017 to 0.933 by rewriting it. Including the original in the ranking pool makes that impossible:
    a rewrite is adopted only when it genuinely helps."""
    from untell.rewriter.ensemble import EnsembleRewriter

    rw = EnsembleRewriter()

    class _M:
        def __init__(self, out):
            self._out = out

        def rewrite(self, text, score_result, threshold=0.30):
            return self._out

    rw._members = [("a", _M("worse rewrite one")), ("b", _M("worse rewrite two"))]

    import untell.scripts.score as score_mod

    clean = "I went to the store yesterday. Rain, mostly."

    def _fake_score(text, tier="lite", threshold=0.30):
        m = 0.02 if text == clean else 0.90  # every member output is worse than the original
        return {"max": m, "mean": m, "detectors": {"a": m}, "tier": tier}

    monkeypatch.setattr(score_mod, "score_text", _fake_score)
    assert rw.rewrite(clean, {"tier": "lite"}) == clean  # untouched


def test_composite_returns_original_when_no_draw_improves(monkeypatch):
    """No 'consolation' rewrite: if no candidate beats the original, return the original.

    The old fallback ('pick the first one anyway, it still changed the text') measurably HURT —
    an already-clean paragraph (roberta 0.017) was pushed to 0.127 by a forced rewrite that spent
    meaning-similarity for nothing."""
    from untell.rewriter.composite import CompositeRewriter

    rw = CompositeRewriter(best_of=2)
    monkeypatch.setattr(
        rw._structural, "rewrite", lambda t, s, threshold=0.30, intensity=None: "worse rewrite"
    )
    monkeypatch.setattr(rw._surgical, "rewrite", lambda t, s, threshold=0.30: t)

    import untell.scripts.score as score_mod

    clean = "I went to the store yesterday. Rain, mostly."

    def _fake_score(text, tier="lite", threshold=0.30):
        m = 0.02 if text == clean else 0.90  # every rewrite is worse than the original
        return {"max": m, "mean": m, "detectors": {"a": m}, "tier": tier}

    monkeypatch.setattr(score_mod, "score_text", _fake_score)
    assert rw.rewrite(clean, {"tier": "lite"}) == clean  # untouched, not a forced worse rewrite


def test_polish_declines_when_it_does_not_help(monkeypatch):
    """An equal-scoring polish must NOT be adopted: it spends meaning-similarity for nothing and,
    since polish optimizes the detector score alone, can raise the AI-tell count while doing it."""
    import untell.attacks as attacks_mod
    import untell.scripts.run as run_mod

    src = "The quick brown fox jumps over the lazy dog every single morning."
    # Same score, but MORE AI tells -> must be rejected on both counts.
    polished = "Moreover, it is important to note that the fox leverages the lazy dog each morning."

    monkeypatch.setattr(run_mod, "score_text", _num_score(0.10, flagged=False))
    monkeypatch.setattr(
        attacks_mod, "surgical_substitute",
        lambda t, tier=None, threshold=0.3: {"text": polished},
    )
    out = run_mod.untell_text(
        src, tier="lite", threshold=0.3, max_iters=1, rewriter=_NoOp(),
        polish=True, scrub=False, sim_bar=0.0,
    )
    assert out["final"] == src  # unpolished text kept


def test_deterministic_rewriter_draws_once_regardless_of_best_of(monkeypatch):
    """Best-of-N on a deterministic rewriter is pure waste: identical draws, but a full detector
    pass each. It must draw exactly once no matter what --best-of says."""
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "score_text", _num_score(0.9))
    calls = {"n": 0}

    class _Det:
        name = "det"
        deterministic = True

        def available(self):
            return True

        def rewrite(self, text, score, threshold=0.3):
            calls["n"] += 1
            return "a deterministic rewrite of the input text"

    run_mod.untell_text(
        "Some AI paragraph to rewrite here now.",
        tier="lite", threshold=0.3, max_iters=1, best_of=8, rewriter=_Det(), scrub=False, sim_bar=0.0,
    )
    assert calls["n"] == 1  # not 8


def test_randomized_rewriter_still_draws_best_of_n(monkeypatch):
    """The short-circuit must not disable best-of-N for randomized rewriters."""
    import untell.scripts.run as run_mod

    monkeypatch.setattr(run_mod, "score_text", _num_score(0.9))
    calls = {"n": 0}

    class _Rand:
        name = "rand"
        deterministic = False

        def available(self):
            return True

        def rewrite(self, text, score, threshold=0.3):
            calls["n"] += 1
            return f"variant number {calls['n']} of the rewritten text"

    run_mod.untell_text(
        "Some AI paragraph to rewrite here now.",
        tier="lite", threshold=0.3, max_iters=1, best_of=4, rewriter=_Rand(), scrub=False, sim_bar=0.0,
    )
    assert calls["n"] == 4


def test_loop_vetoes_a_meaning_inverting_rewrite(monkeypatch):
    """A rewrite that INVERTS the source must be rejected even though it sails through the
    similarity gate (measured: "runs faster" -> "runs slower" scores 0.974 vs a 0.76 bar) and
    scores beautifully on the detectors."""
    import untell.scripts.run as run_mod

    src = "The build runs significantly faster after the change."
    inverted = "The build runs significantly slower after the change."

    # The inversion looks perfect to the detectors — only the veto can catch it.
    def _score(text, tier="full", threshold=0.3):
        m = 0.02 if text == inverted else 0.90
        return {"tier": tier, "detectors": {"d": m}, "max": m, "mean": m,
                "threshold": threshold, "flagged": m >= 0.3}

    monkeypatch.setattr(run_mod, "score_text", _score)
    monkeypatch.setattr(run_mod, "meaning_preserved",
                        lambda src, cand, sim, bar: cand.strip() != inverted)

    class _Inv:
        name = "inv"
        deterministic = False

        def available(self):
            return True

        def rewrite(self, text, score, threshold=0.3):
            return inverted

    out = run_mod.untell_text(
        src, tier="lite", threshold=0.3, max_iters=1, best_of=1, rewriter=_Inv(),
        scrub=False, sim_bar=0.0,
    )
    assert out["final"] == src  # the inverting rewrite was never adopted


def test_veto_can_be_disabled(monkeypatch):
    """veto_contradictions=False restores the previous behaviour (and is what the NLI-less path
    degrades to), so the flag must actually bypass the check."""
    import untell.scripts.run as run_mod

    src = "The build runs significantly faster after the change."
    inverted = "The build runs significantly slower after the change."

    def _score(text, tier="full", threshold=0.3):
        m = 0.02 if text == inverted else 0.90
        return {"tier": tier, "detectors": {"d": m}, "max": m, "mean": m,
                "threshold": threshold, "flagged": m >= 0.3}

    monkeypatch.setattr(run_mod, "score_text", _score)
    monkeypatch.setattr(run_mod, "meaning_preserved", lambda *a, **k: False)  # would reject all

    class _Inv:
        name = "inv"
        deterministic = False

        def available(self):
            return True

        def rewrite(self, text, score, threshold=0.3):
            return inverted

    out = run_mod.untell_text(
        src, tier="lite", threshold=0.3, max_iters=1, best_of=1, rewriter=_Inv(),
        scrub=False, sim_bar=0.0, veto_contradictions=False,
    )
    assert out["final"] == inverted  # veto bypassed
