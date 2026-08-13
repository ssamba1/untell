"""The per-sentence flags handed to the caller described neither the output nor, usually, anything.

FOUND by asking whether `post.flagged_sentences` describes `final`. Two independent defects, and the
second is the one that matters.

**It named sentences that are not in the output.** The list is computed on MASKED text — the form the
rewriter works in — so any sentence containing a locked span came back carrying a `⟦HZ…⟧` sentinel:

    'Overall, the controversy surrounding unions in ⟦HZ0001⟧ is complex and multifaceted, ...'

MEASURED on the 7 HC3 documents (of 60) whose per-sentence pass flags anything, each run plain and
with a citation and URL welded in — 12 runs, 6 with a non-empty list: 4 sentences carried a sentinel
and 4 were absent from `final`. It fires on plain input too, because `lock` masks entities, numbers
and dates rather than only citations.

**And usually it was not there at all.** `best_score` is replaced wholesale when a candidate is
adopted (`best_masked, best_score = cand_best, cand_best_score`), when the result is rescored, and
when it is polished. The key is set at the TOP of each iteration, so it survives only when none of
those three happened afterwards. Instrumented on a document whose per-sentence pass was forced to
flag every sentence:

    patched scorer calls: 2, returning 5 flagged sentences each
    post flagged_sentences: 0

The loop computed the list twice and the caller received an empty one. When the field did arrive
populated it described the text as it stood at the start of some earlier iteration — never `final`.

So the fix is not to translate what the loop carried out; it is to score the text the caller got.
The loop keeps its masked list for `rewriter/prompts.py` and the targeted rewriter, which are editing
masked text and must not be shown a restored citation.

MEASURED after, same documents and the same forced-flag arm:

    forced arm   n=4   sentinels 0   absent from final 0     (was: caller got 0 of 5 computed)
    real arm     6 runs, 5 non-empty, sentinels 0, absent 0  (was: 6 non-empty, 4 and 4)

One extra lite per-sentence pass per call; a full run measures 0.56s.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.run import _flagged_sentences_of, untell_text

SENTINEL = "⟦HZ"
TEXT = (
    "Moreover, the framework leverages a robust approach to delivery [3] at scale across the "
    "programme. Furthermore, it is important to note that this underscores the pivotal "
    "integration for every team (see https://example.com/docs) in the organisation. "
    "The system utilizes a comprehensive methodology throughout the year. Additionally, the "
    "platform empowers users to streamline their daily workflows considerably. In conclusion, "
    "organizations must harness these seamless solutions today without further delay."
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.fixture
def flag_everything(monkeypatch):
    """Force the per-sentence pass, rather than hoping a fixed document trips it.

    At `tier=lite` only 7 of 60 corpus documents flag anything and this one flags zero, so an
    unpatched assertion here passes over an empty list and proves nothing — the first version of
    this file did exactly that. `run.py` imports the scorer inside the function, so the SOURCE
    module is what has to be patched; patching `run.score_sentences` raises AttributeError.
    """
    import untell.scripts.sentences as sentences
    from untell.text_split import split_sentences

    monkeypatch.setattr(
        sentences,
        "score_sentences",
        lambda text, **_kw: {"flagged": [s for s in split_sentences(text) if s.strip()]},
    )


def test_the_flags_describe_the_text_the_caller_received(flag_everything) -> None:
    """The whole point of the field. Both halves of the defect show up here: a sentinel makes the
    sentence unreadable, and a sentence absent from `final` cannot be looked up in the output."""
    result = untell_text(
        TEXT, tier="lite", threshold=0.3, max_iters=2, rewriter="structural", best_of=1, seed=3
    )
    flagged = result["post"].get("flagged_sentences") or []
    final = result.get("final") or ""
    assert flagged, "the per-sentence patch did not reach the result; this asserts nothing"
    assert not [s for s in flagged if SENTINEL in s], flagged
    assert not [s for s in flagged if s.strip() and s.strip() not in final], flagged


def test_the_loop_actually_rewrote_the_text(flag_everything) -> None:
    """The denominator. If the text came back untouched, `final` is the input, every sentence
    trivially occurs in it, and the assertion above holds for the wrong reason."""
    result = untell_text(
        TEXT, tier="lite", threshold=0.3, max_iters=2, rewriter="structural", best_of=1, seed=3
    )
    assert result.get("changed"), "nothing was rewritten; the flags were never at risk of drifting"


def test_it_scores_the_final_text_not_a_draft() -> None:
    """Stated directly. The helper takes the text and nothing else, so there is no draft for it to
    describe by accident — which is what the loop's own copy did on every adopted candidate."""
    flagged = _flagged_sentences_of(TEXT, 0.3)
    assert all(s.strip() in TEXT for s in flagged), flagged


def test_a_broken_scorer_does_not_break_the_result(monkeypatch) -> None:
    """A reporting field must never break the result it rides in."""
    import untell.scripts.sentences as sentences

    def _boom(*_args, **_kwargs):
        raise RuntimeError("per-sentence scoring is unavailable")

    monkeypatch.setattr(sentences, "score_sentences", _boom)
    assert _flagged_sentences_of(TEXT, 0.3) == []
    result = untell_text(
        TEXT, tier="lite", threshold=0.3, max_iters=1, rewriter="structural", best_of=1, seed=3
    )
    assert result["post"].get("max") is not None
    assert result["post"].get("flagged_sentences") == []


def test_the_field_is_always_present(flag_everything) -> None:
    """It is documented in `result-shapes.md` as an unconditional key of `post`. Before this change
    it was present only when the last iteration happened not to adopt, rescore or polish."""
    result = untell_text(
        TEXT, tier="lite", threshold=0.3, max_iters=1, rewriter="structural", best_of=1, seed=1
    )
    assert "flagged_sentences" in result["post"]


def test_the_loop_still_gets_masked_sentences() -> None:
    """The guard on the other consumer. `rewriter/prompts.py` and the targeted rewriter read this
    key while editing MASKED text; handing them a restored citation invites the model to rewrite the
    one span that must survive byte-for-byte. The in-loop assignment is untouched by this change —
    only the returned payload is recomputed.
    """
    import inspect

    import untell.scripts.run as run

    source = inspect.getsource(run)
    assert '"flagged_sentences": flagged, "style": style' in source, (
        "the in-loop assignment that feeds the rewriter prompt is gone"
    )
