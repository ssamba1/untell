"""Every rewriter's `deterministic` flag is a claim. Check it against behaviour.

The loop trusts the declaration in two places, and never verifies it:

    run.py:661  draws = 1 if getattr(rw, "deterministic", False) else max(1, best_of)
    run.py:796  if getattr(rw, "deterministic", False) and best_masked == prev_masked:

Both failure directions are silent:

  - **declares True, actually varies** — `best_of` becomes a no-op and the loop stops early on a
    round that would have improved next time. The user asked for N draws and got one.
  - **declares nothing, actually fixed** — N-1 wasted draws every round, and each draw is the
    expensive part (a full-tier detector pass plus the meaning gate on top of the rewrite itself).

`mt_pivot` was the second kind. It declared False on the reasoning that beam-search output is
"not guaranteed no-op", which is a statement about a different property; its decode is
`generate(..., num_beams=4)` with no sampling and no RNG, so all draws were identical. MEASURED on
one document at the default `best_of=3`: 6 rewrite calls collapsed to 2 and 12.9s to 4.6s, with
byte-identical output and an identical score.

So make the claim checkable. Each rewriter that constructs and runs here is drawn from repeatedly,
exactly as the loop draws, and the distinctness of the results is compared with what it declares.
Rewriters needing an API key or an uninstalled extra are skipped rather than assumed — an
unavailable rewriter that no-ops looks perfectly deterministic, and reading that as a pass would be
the more comfortable answer rather than the true one.
"""

from __future__ import annotations

import importlib
import random

import pytest

TEXT = (
    "Moreover, the framework leverages a robust approach to deliver transformative outcomes "
    "for every stakeholder. Furthermore, it underscores the pivotal integration of modern "
    "methodologies. In conclusion, the comprehensive solution demonstrates significant value "
    "across the entire organizational landscape and beyond."
)

# Every rewriter that can run without a network call or an API key. LLM-backed ones (anthropic,
# openai) are excluded by construction: their determinism is a property of a remote service.
REWRITERS = [
    ("structural", "untell.rewriter.structural", "StructuralRewriter"),
    ("surgical", "untell.rewriter.surgical", "SurgicalRewriter"),
    ("composite", "untell.rewriter.composite", "CompositeRewriter"),
    ("ensemble", "untell.rewriter.ensemble", "EnsembleRewriter"),
    ("mt_pivot", "untell.rewriter.mt_pivot", "MTPivotRewriter"),
    ("t5_paraphrase", "untell.rewriter.t5_paraphrase", "T5ParaphraseRewriter"),
    ("local_policy", "untell.rewriter.local_policy", "LocalPolicyRewriter"),
]

DRAWS = 4


def _build(module_path: str, cls_name: str):
    try:
        cls = getattr(importlib.import_module(module_path), cls_name)
        return cls()
    except Exception as exc:  # missing extra, missing weights, missing key
        pytest.skip(f"not constructible here: {type(exc).__name__}: {exc}")


@pytest.mark.parametrize("name,module_path,cls_name", REWRITERS, ids=[r[0] for r in REWRITERS])
def test_the_declared_flag_matches_what_the_draws_do(name, module_path, cls_name, monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    rw = _build(module_path, cls_name)

    if hasattr(rw, "available") and not rw.available():
        pytest.skip(f"{name} reports itself unavailable; a no-op looks deterministic")

    random.seed(4242)
    try:
        drawn = [rw.rewrite(TEXT, {"max": 0.9}, 0.30) for _ in range(DRAWS)]
    except Exception as exc:
        pytest.skip(f"{name} cannot rewrite here: {type(exc).__name__}: {exc}")

    if all(d.strip() == TEXT.strip() for d in drawn):
        pytest.skip(f"{name} left the text unchanged on every draw; nothing to compare")

    declared = bool(getattr(rw, "deterministic", False))
    measured = len(set(drawn)) == 1

    assert declared == measured, (
        f"{name} declares deterministic={declared} but produced {len(set(drawn))} distinct "
        f"results from {DRAWS} consecutive draws. "
        + ("The loop will collapse best_of to 1 and may stop early on a round that would still "
           "improve." if declared else
           "The loop will draw best_of times per round for identical candidates, paying a "
           "full-tier detector pass and the meaning gate on each.")
    )


CLEAN_SENTENCE = "An unsupervised segmentation approach was used throughout the study."
TELLY_SENTENCE = (
    "Moreover, the framework leverages robust methodologies to deliver transformative outcomes."
)


def test_composite_stillness_on_a_clean_sentence_is_a_no_op_not_determinism(monkeypatch):
    """The distinction that let a false claim spread to four files.

    A test measured 40 draws of composite on this sentence, got one output, and wrote it down as
    "composite is deterministic on a sentence this short". Those 40 draws were 40/40 UNCHANGED — the
    rewriter declined to touch it, which looks exactly like perfect determinism from outside. Three
    other files then repeated "deterministic composite member" as though it were a property of the
    rewriter rather than of that input.

    THE FIXTURE NO LONGER SHOWS A NO-OP, and that is the right outcome rather than a problem here.
    A later fix ("a paragraph of one sentence is still prose") made single-sentence input eligible
    for the transforms that were skipping it, so composite now changes this sentence at 2 of 8
    seeds:

        An unsupervised segmentation approach was used throughout the study.
        Basically, an unsupervised segmentation method was used throughout the study.

    Which settles the original question in the same direction by a different route: composite is
    stochastic on this input, so declaring no `deterministic` flag is correct. What this case now
    asserts is that reading — that the stillness was never determinism — and it would fail if the
    sentence went back to being untouched at every seed without the docstrings being revisited.

    Seeded per draw. Unseeded it asserted a property of whatever RNG state the suite happened to be
    in, passing standalone and failing inside a selection where other tests had drawn first.
    """
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    from untell.rewriter.composite import CompositeRewriter
    from untell.scripts.tells import score_tells

    assert score_tells(CLEAN_SENTENCE)["tells"] == 0, "fixture no longer clean; premise gone"

    rw = CompositeRewriter()
    drawn = []
    for seed in range(8):
        random.seed(seed)
        drawn.append(rw.rewrite(CLEAN_SENTENCE, {"max": 0.9}, 0.30))

    assert len(set(drawn)) > 1, (
        "composite gives one output at every seed on this sentence. That is what it did when the "
        "single-sentence transforms were skipping it, and it was read as determinism — check "
        "whether the rewriter has stopped treating a lone sentence as prose before relaxing this."
    )


def test_composite_varies_as_soon_as_there_is_something_to_fix(monkeypatch):
    """Same length, same single sentence — only the tell content differs."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    from untell.rewriter.composite import CompositeRewriter
    from untell.scripts.tells import score_tells

    assert score_tells(TELLY_SENTENCE)["tells"] > 0, "fixture carries no tells; premise gone"

    rw = CompositeRewriter()
    drawn = []
    for seed in range(8):
        random.seed(seed)
        drawn.append(rw.rewrite(TELLY_SENTENCE, {"max": 0.9}, 0.30))
    assert len(set(drawn)) > 1, (
        f"composite gave one output from 8 draws on tell-bearing input; that WOULD make it "
        f"deterministic and the flag it declares (absent, i.e. stochastic) wrong: {drawn[0]!r}"
    )
    assert not all(d.strip() == TELLY_SENTENCE.strip() for d in drawn)


def test_at_least_one_rewriter_of_each_kind_was_actually_checked():
    """Guards the guard. Every case above can skip itself, and an all-skipped file passes."""
    checked_det, checked_stoch = [], []
    for name, module_path, cls_name in REWRITERS:
        try:
            cls = getattr(importlib.import_module(module_path), cls_name)
            rw = cls()
        except Exception:
            continue
        if hasattr(rw, "available") and not rw.available():
            continue
        (checked_det if bool(getattr(rw, "deterministic", False)) else checked_stoch).append(name)

    assert checked_stoch, "no stochastic rewriter was available; the mismatch check saw nothing"
    assert checked_det, "no deterministic rewriter was available; the mismatch check saw nothing"
