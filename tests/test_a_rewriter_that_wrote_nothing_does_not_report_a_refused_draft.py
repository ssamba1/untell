"""A rewriter with no edit surface returned its input, and every surface called it a refused draft.

FOUND by running the humanizer on real machine text rather than on the demo corpus. Machine-written
abstracts (`eval/data/generated_abstracts.py`, 70 of them), `tier=lite`, `--rewriter surgical`,
`max_iters=5`:

    changed 0/10   adopted 0   0.3025 -> 0.3025   stopped: stalled on 6, passed on 4

`SurgicalRewriter` ranks words by whether swapping one removes a catalogued tell. 36 of 40 of these
abstracts carry no catalogued tell at all, so `_tell_ranks` is EMPTY, the substitution loop never
runs an iteration, and the rewriter returns its argument byte-identical. On the same corpus
`structural` changes 18 of 20 and `composite` 14 of 20, so this is specific to the one rewriter
whose edit surface is the tell catalogue — and the catalogue reads register, so formal prose is the
ordinary case for it, not an edge.

An identical candidate then passes every gate by construction: it reproduces every locked span, the
meaning gate sees similarity 1.0, and it ties on detector score — so it even satisfies the adoption
guard's `<=`. The only thing that stops it is the separate `cand_best != best_masked` check, which
compares the TEXT rather than the score the user is then told about. So every surface that reports
on the run described a draft that was never written:

    result["adopted"]   0                       (correct)
    result["inspect"]   candidate_accepted, adopted   <- says a draft was taken
    result["warning"]   "every draft scored worse than your text ... Try --best-of 3 for more
                         draws"                 <- wrong cause, and the remedy cannot work:
                                                   the rewriter is deterministic, so N draws are
                                                   byte-identical by construction

This is the same defect `_nothing_adopted_warning` already fixes for `vetoed` and `sentinel_failed`
— "scored worse" describing a comparison that did not happen — one step earlier in the chain, where
there is no draft to compare at all.

The alternative fix, giving the tells objective a score-ranked fallback so tell-free text still has
words to try, was measured and rejected: on the same 40 abstracts `prefer_tells=False` gets 40 of 40
zero-substitution runs against 37 of 40 for the tells objective. The score-only rule is a worse
version of the same dead end, because the stdlib heuristic cannot see a synonym swap. So the fix is
to report the cause and name a rewriter that can act, not to pretend there is an edit surface.
"""

from __future__ import annotations

import logging

import pytest

from eval.data.generated_abstracts import ABSTRACTS
from untell.attacks.word_importance import _tell_ranks, surgical_substitute
from untell.rewriter import get_rewriter
from untell.scripts.run import _nothing_adopted_warning, untell_text

# One of the committed machine-written abstracts, so the finding stays traceable to the corpus it
# was measured on rather than to a paraphrase of it. It has to clear the loop threshold as well as
# carry no tell: a text scoring under 0.30 is `passed` before the rewriter is ever called, and a
# no-op rewriter is then indistinguishable from a correct early exit. `test_the_premise_holds`
# asserts both, so a corpus change fails there with the reason rather than here with a symptom.
TELL_FREE = ABSTRACTS[0]


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


def test_the_premise_holds_this_text_has_no_edit_surface() -> None:
    """The whole finding rests on it, so assert it rather than assuming it."""
    from untell.scripts.run import score_text

    assert score_text(TELL_FREE, tier="lite")["max"] > 0.30, "must enter the loop at all"
    assert _tell_ranks(TELL_FREE) == []
    out = surgical_substitute(TELL_FREE, tier="lite", max_subs=12, prefer_tells=True)
    assert out["text"] == TELL_FREE and out["substitutions"] == 0


def test_the_note_does_not_claim_a_draft_was_scored() -> None:
    note = _nothing_adopted_warning(1, 0, False, 0, 0, 1, True) or ""
    assert "identical to your text" in note
    assert "scored worse" not in note
    assert "there was no draft to refuse" in note


def test_the_remedy_is_not_more_draws_of_a_deterministic_rewriter() -> None:
    """A rewriter with no edit surface has none on the next draw either, and for a deterministic
    one that is a guarantee, not a heuristic. `--best-of` is exactly the wrong advice — it is the
    advice the catch-all branch gives, which is why this needs its own branch."""
    note = _nothing_adopted_warning(1, 0, False, 0, 0, 1, True, "surgical") or ""
    assert "--best-of" not in note
    assert "--rewriter composite" in note and "--rewriter structural" in note


def test_a_mixed_run_counts_the_identical_draws_apart_from_the_refused_ones() -> None:
    note = _nothing_adopted_warning(3, 0, False, 0, 0, 2, False) or ""
    assert "2 came back identical" in note and "1 scored worse" in note


def test_identical_draws_are_not_folded_into_the_meaning_gate_tally() -> None:
    """An identical candidate cannot be vetoed — it scores similarity 1.0 — so the mixed veto
    branch must subtract it rather than call it a draft that scored worse."""
    note = _nothing_adopted_warning(4, 0, False, 1, 0, 2, False) or ""
    assert "1 changed the meaning" in note
    assert "2 came back identical" in note
    assert "1 scored worse" in note


def test_a_real_no_op_run_says_so_end_to_end() -> None:
    result = untell_text(TELL_FREE, tier="lite", rewriter="surgical", max_iters=5)
    assert result["changed"] is False and result["adopted"] == 0
    note = result.get("warning") or ""
    assert "identical to your text" in note, note
    assert "every draft scored worse" not in note, note


def test_inspect_does_not_report_an_adoption_the_counter_denies() -> None:
    """The two accountings of the same decision disagreed, and the one a user opens to find out why
    nothing changed was the one that said something had."""
    result = untell_text(TELL_FREE, tier="lite", rewriter="surgical", max_iters=5, inspect=True)
    kinds = [e["type"] for e in result["inspect"]]
    assert "candidate_identical" in kinds
    assert result["adopted"] == 0
    assert "adopted" not in kinds, result["inspect"]


def test_a_rewriter_that_does_have_an_edit_surface_still_reports_none_of_this() -> None:
    """The paired control: the SAME text, one rewriter that cannot act on it and one that can. That
    pairing is what makes the finding about the rewriter's edit surface rather than about this
    document — `structural` rewrites this exact abstract, so no identical draw is counted and no
    such note is produced. Without it the test would also pass if the note had simply been wired to
    fire on every unchanged run."""
    rw = get_rewriter("structural")
    from untell.scripts.run import score_text

    assert rw.rewrite(TELL_FREE, score_text(TELL_FREE, tier="lite"), 0.30) != TELL_FREE
    result = untell_text(TELL_FREE, tier="lite", rewriter="structural", max_iters=5)
    assert "identical to your text" not in (result.get("warning") or "")


def test_the_inspect_report_does_not_silently_drop_the_draw() -> None:
    """A new event type the renderer does not know is worse than the wrong label: the draw vanishes
    from `--inspect` entirely, and the iteration reads as though no candidate was ever produced."""
    from untell.inspect_report import render_inspect_report

    result = untell_text(TELL_FREE, tier="lite", rewriter="surgical", max_iters=5, inspect=True)
    report = render_inspect_report(TELL_FREE, result["final"], result["inspect"])
    assert "IDENTICAL to the input" in report, report
    assert "nothing to adopt: every draw was the input itself" in report, report
    assert "none beat the incumbent" not in report, report


def test_every_event_the_loop_emits_has_a_renderer_branch() -> None:
    """The general form of the defect above, so the next event type cannot be added silently."""
    import re
    from pathlib import Path

    run_src = Path("untell/scripts/run.py").read_text(encoding="utf-8")
    report_src = Path("untell/inspect_report.py").read_text(encoding="utf-8")
    # Scoped to `inspect_events.append(...)` calls. A bare search for `"type": "..."` also picks up
    # unrelated dicts elsewhere in the module (it found `"type": "block"`), which would make this
    # test fail for a reason that has nothing to do with the inspect schema.
    emitted: set[str] = set()
    for m in re.finditer(r"inspect_events\.append\(", run_src):
        depth, j = 0, m.end() - 1
        while j < len(run_src):
            if run_src[j] == "(":
                depth += 1
            elif run_src[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        call = run_src[m.end() : j]
        # Values of the "type" key only. Widening this to every string literal in the call also
        # collects GATE names ("meaning_gate", "sentinels"), which belong to the `gate` key and
        # have no renderer branch of their own — a different vocabulary, wrongly conflated.
        for seg in re.findall(r'"type":([^,}]*)', call):
            emitted |= set(re.findall(r'"(\w+)"', seg))
    assert emitted, "no inspect events found in run.py — the scan is broken, not the code"
    assert "candidate_identical" in emitted, emitted
    for kind in sorted(emitted):
        assert f'== "{kind}"' in report_src, f"{kind} is emitted but render_inspect_report ignores it"


def test_the_note_never_suggests_the_rewriter_that_just_failed() -> None:
    """The first version recommended `composite` unconditionally — and `composite` is the DEFAULT,
    so a user who had changed nothing was told to try what they were already running. It fires
    there for real: 1 of 20 abstracts, 15 identical draws."""
    for name in ("surgical", "composite", "structural", "targeted"):
        note = _nothing_adopted_warning(3, 0, False, 0, 0, 3, False, name) or ""
        assert f"--rewriter {name}" not in note, (name, note)
        assert "--rewriter " in note, (name, note)


def test_a_stochastic_rewriter_is_not_told_its_draws_are_guaranteed_identical() -> None:
    """"Deterministic" is a guarantee about future draws; a stochastic rewriter that happened to
    return its input N times gives evidence, not proof, and the note must not overstate it."""
    fixed = _nothing_adopted_warning(3, 0, False, 0, 0, 3, True, "surgical") or ""
    drawn = _nothing_adopted_warning(3, 0, False, 0, 0, 3, False, "composite") or ""
    assert "deterministic" in fixed and "by construction" in fixed
    assert "deterministic" not in drawn and "all 3 draws came back the same" in drawn


def test_the_tell_catalogue_explanation_is_only_given_where_it_applies() -> None:
    """Explaining `composite`'s empty run by the tell catalogue would name a mechanism that was not
    the one that failed — the catalogue is `surgical`'s edit surface, not `composite`'s."""
    surgical = _nothing_adopted_warning(1, 0, False, 0, 0, 1, True, "surgical") or ""
    composite = _nothing_adopted_warning(1, 0, False, 0, 0, 1, False, "composite") or ""
    assert "catalogued tells" in surgical
    assert "catalogued tells" not in composite
