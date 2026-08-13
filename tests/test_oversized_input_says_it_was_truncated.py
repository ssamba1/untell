"""50,000 characters in, a verdict about the first 50,000 out, and nothing said so.

`_truncate` silently returns `text[:50_000]`. MEASURED on a 67,200-character input: `score_text`
returns a max identical to the first 50,000 characters scored alone, to machine precision. The last
17,200 characters — 26% of the document — contribute nothing, and the result dict carried no hint.

Two things made this worth a caveat rather than a shrug:

  - `score_tells` does NOT truncate. The same document reports 10,774 tells against the scorer's
    view of 8,010 — two surfaces of one tool describing different documents, with no way to tell
    from either result.
  - the rewrite loop rewrites the WHOLE text while scoring the prefix, so `post` is a verdict on
    74% of what it hands back.

The REST surface already rejects oversized input with a 422, which is the other reasonable answer.
The CLI and the Python API cannot refuse work a caller has already asked for, so they now say what
they did — and the caveat is PREPENDED, because the file's own ordering rule puts rare and
actionable notes first and "you got a number about a quarter less than you sent" is the most
actionable of them.
"""

from __future__ import annotations

import pytest

from untell.scripts.score import MAX_INPUT_CHARS, batch_score_texts, score_text
from untell.scripts.tells import score_tells

_PARA = (
    "Moreover, the framework leverages a robust approach to deliver transformative outcomes "
    "for every stakeholder involved in the programme of work across the organisation. "
)
OVERSIZED = _PARA * 400          # ~67k chars
WITHIN = _PARA * 20              # ~3.4k chars


@pytest.fixture(autouse=True)
def stdlib_lite(monkeypatch):
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")


def test_the_fixtures_straddle_the_cap() -> None:
    """The premise. If both fixtures fell the same side of the bound, every case below is vacuous."""
    assert len(OVERSIZED) > MAX_INPUT_CHARS
    assert len(WITHIN) < MAX_INPUT_CHARS


def test_the_tail_really_is_ignored() -> None:
    """The defect itself, asserted rather than assumed — otherwise the caveat might be describing
    a truncation that does not actually cost anything."""
    full = score_text(OVERSIZED, tier="lite")["max"]
    prefix = score_text(OVERSIZED[:MAX_INPUT_CHARS], tier="lite")["max"]
    assert full == pytest.approx(prefix, abs=1e-12), (
        "the tail changed the score, so it is not being discarded and this file is describing "
        "something that no longer happens"
    )


def test_oversized_input_is_told_it_was_truncated() -> None:
    warning = str(score_text(OVERSIZED, tier="lite").get("warning") or "")
    assert "first 50,000 characters only" in warning, f"no truncation caveat: {warning[:160]!r}"
    assert "not seen by any detector" in warning


def test_the_caveat_comes_first() -> None:
    """Ordering is the point of prepending. This text also triggers the standing caveats, and the
    note that the number covers three quarters of the document must not arrive behind them."""
    warning = str(score_text(OVERSIZED, tier="lite").get("warning") or "")
    assert warning.startswith("scored the first"), f"caveat is not first: {warning[:120]!r}"


def test_input_within_the_cap_gets_no_such_caveat() -> None:
    """Guards the guard. A caveat on everything says nothing."""
    warning = str(score_text(WITHIN, tier="lite").get("warning") or "")
    assert "first 50,000 characters only" not in warning


def test_the_batch_path_reports_it_too() -> None:
    """`batch_score_texts` truncates with the same helper and had the same silence. It is the path
    `sentences` uses, so a long document reaches it in the ordinary course of things."""
    results = batch_score_texts([WITHIN, OVERSIZED], tier="lite")
    assert "first 50,000 characters only" not in str(results[0].get("warning") or "")
    assert "first 50,000 characters only" in str(results[1].get("warning") or "")


def test_the_caveat_names_the_disagreement_with_the_tell_catalogue() -> None:
    """The specific thing a reader cannot otherwise discover: the two surfaces are describing
    different amounts of text."""
    assert score_tells(OVERSIZED)["tells"] > score_tells(OVERSIZED[:MAX_INPUT_CHARS])["tells"], (
        "the catalogue no longer sees more than the scorer; the caveat's claim needs re-checking"
    )
    warning = str(score_text(OVERSIZED, tier="lite").get("warning") or "")
    assert "tell catalogue is NOT truncated" in warning
