"""Boundaries in `rich_output`, `audit` and `preserve` that survived the boundary sweep.

Each case sits ON its constant. A `>=`/`>` swap is invisible everywhere else, which is why ten
thousand tests left these three alone.
"""

from __future__ import annotations

import math

from untell import rich_output
from untell.rich_output import _SATURATED_MAX
from untell.scripts.audit import _MODULE_DRIFT
from untell.scripts.preserve import _MIN_WORD_CHAR_SHARE, _word_char_share

# --- rich_output: `pre["max"] >= _SATURATED_MAX and post["max"] >= _SATURATED_MAX` ---

def _mean_note_shown(monkeypatch, capsys, pre_max: float, post_max: float) -> bool:
    """True when the saturation note — the ensemble-mean fallback — reached the terminal.

    Captured from real stdout rather than by patching a name: this module prints through a `rich`
    Console when one is available and through the builtin otherwise, so patching either alone reads
    as "note absent" on the path that uses the other.
    """
    rich_output.print_humanize_result(
        original="the original text",
        final="the rewritten text",
        pre_score={"max": pre_max, "mean": 0.80},
        post_score={"max": post_max, "mean": 0.40},
        iterations=1,
        stopped="done",
        tells_before=4,
        tells_after=1,
    )
    out = capsys.readouterr().out
    return "Ensemble mean" in out or "pinned at" in out


def test_both_scores_exactly_at_the_saturation_bar_count_as_pinned(monkeypatch, capsys):
    """A detector sitting exactly on `_SATURATED_MAX` is pinned, and the delta cannot show change.

    Under `>`, a document whose max is exactly at the bar loses the ensemble-mean fallback and the
    reader is left with the one number the module's own comment proves cannot see the improvement.
    """
    assert _mean_note_shown(monkeypatch, capsys, _SATURATED_MAX, _SATURATED_MAX)


def test_a_hair_under_the_saturation_bar_on_either_side_is_not_pinned(monkeypatch, capsys):
    """Both operands are separate boundaries, so each is dropped below the bar on its own."""
    under = math.nextafter(_SATURATED_MAX, 0.0)
    assert not _mean_note_shown(monkeypatch, capsys, under, _SATURATED_MAX)
    assert not _mean_note_shown(monkeypatch, capsys, _SATURATED_MAX, under)


# --- preserve: `_word_char_share(text) < _MIN_WORD_CHAR_SHARE` ---

def _text_with_word_char_share(share: float, length: int = 100) -> str:
    """``length`` characters of which exactly ``share`` are word characters."""
    n_word = round(share * length)
    text = ("a" * n_word) + ("$" * (length - n_word))
    assert len(text) == length
    return text


def _guard_short_circuited(monkeypatch, text: str) -> bool:
    """True when the degenerate-input guard returned before the NER path was entered.

    An earlier version of this test asserted `_spacy_entity_spans_impl(text) is not None`, which is
    true of `[]` as well — it passed whichever way the comparison pointed. The guard's ONLY
    observable is whether execution reaches the code after it, so that is what this watches: the
    env gate immediately below, forced on so the probe is deterministic rather than dependent on
    whether this machine has spaCy.
    """
    from untell.scripts import preserve

    reached = []
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    monkeypatch.setattr(preserve, "_warn_no_ner_env", lambda: reached.append(True))
    preserve._spacy_entity_spans_impl(text)
    return not reached


def test_text_exactly_on_the_word_character_floor_is_not_treated_as_degenerate(monkeypatch):
    """`< _MIN_WORD_CHAR_SHARE` gates the whole NER pass.

    At exactly the floor the input is real text and its entities must still be locked. Under `<=`,
    a document sitting on the floor silently returns no spans — quotations, citations and URLs stop
    being protected, which is the one promise the preserve layer makes.
    """
    text = _text_with_word_char_share(_MIN_WORD_CHAR_SHARE)
    assert _word_char_share(text) == _MIN_WORD_CHAR_SHARE, "the fixture must sit ON the floor"
    assert not _guard_short_circuited(monkeypatch, text), (
        "text exactly at the floor must reach the NER path, not be discarded as degenerate")


def test_just_under_the_word_character_floor_is_discarded_as_degenerate(monkeypatch):
    """The neighbour, so the case above cannot pass by the guard being dead entirely."""
    text = _text_with_word_char_share(_MIN_WORD_CHAR_SHARE - 0.01)
    assert _guard_short_circuited(monkeypatch, text)


def test_the_word_character_share_helper_brackets_the_floor():
    """The arithmetic the guard reads, pinned either side of the constant."""
    assert _word_char_share(_text_with_word_char_share(_MIN_WORD_CHAR_SHARE)) == _MIN_WORD_CHAR_SHARE
    assert _word_char_share(_text_with_word_char_share(_MIN_WORD_CHAR_SHARE - 0.01)) < _MIN_WORD_CHAR_SHARE
    assert _word_char_share(_text_with_word_char_share(_MIN_WORD_CHAR_SHARE + 0.01)) > _MIN_WORD_CHAR_SHARE


# --- audit: `len(modules) - claimed > _MODULE_DRIFT` ---

def test_a_claim_exactly_the_drift_window_behind_is_tolerated(tmp_path, monkeypatch):
    """Drift of exactly `_MODULE_DRIFT` is inside the window the comment says is deliberate.

    The asymmetry is on purpose: a doc lands one behind whenever a module arrives between reading
    the count and writing it. Under `>=`, a document exactly at the window edge is reported stale,
    and a check that cries wolf at the tolerance it advertises is one people stop reading.
    """
    from untell.scripts import audit

    (tmp_path / "tests").mkdir()
    n = _MODULE_DRIFT + 10
    for i in range(n):
        (tmp_path / "tests" / f"test_{i}.py").write_text("", encoding="utf-8")
    doc = tmp_path / "LIVE.md"
    doc.write_text(f"the suite is {n - _MODULE_DRIFT} test modules\n", encoding="utf-8")

    monkeypatch.setattr(audit, "REPO", tmp_path)
    monkeypatch.setattr(audit, "COMPARATIVE_DOCS", ("LIVE.md",))
    monkeypatch.setattr(audit, "HISTORICAL_DOCS", ())

    report = audit.Report()
    audit.check_test_inventory(report)
    assert not report.count_drifts, (
        f"drift of exactly {_MODULE_DRIFT} is inside the tolerated window and must not be reported")


def test_one_module_past_the_drift_window_is_reported(tmp_path, monkeypatch):
    """The neighbour, so the tolerance test above cannot pass by the check being dead."""
    from untell.scripts import audit

    (tmp_path / "tests").mkdir()
    n = _MODULE_DRIFT + 10
    for i in range(n):
        (tmp_path / "tests" / f"test_{i}.py").write_text("", encoding="utf-8")
    doc = tmp_path / "LIVE.md"
    doc.write_text(f"the suite is {n - _MODULE_DRIFT - 1} test modules\n", encoding="utf-8")

    monkeypatch.setattr(audit, "REPO", tmp_path)
    monkeypatch.setattr(audit, "COMPARATIVE_DOCS", ("LIVE.md",))
    monkeypatch.setattr(audit, "HISTORICAL_DOCS", ())

    report = audit.Report()
    audit.check_test_inventory(report)
    assert report.count_drifts, "one past the window must be reported as stale"
