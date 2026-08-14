"""A 272-word code block was reported as AI with nothing said about it being code.

FOUND by asking what the loop does with an input people actually paste — a README section, a config
block, a table. MEASURED at `tier=lite` on a pure Python fence:

    flagged: True   stopped: max_iters   changed: False

The loop ran every iteration, adopted nothing, and returned an AI verdict. The only caveat attached
was the generic lite-path one. Nothing said the document contains no prose, that the rewriter had
nothing it was permitted to touch, or that the detectors were scoring a kind of text they were never
built for.

The discriminator already existed. `layout._prose_line_mask` marks the lines the rewriter may edit:

    pure code fence     0 of 62 lines prose
    ordinary prose      1 of 1
    prose + a fence     1 of 64

MEASURED on 120 corpus texts, both halves of HC3 and RAID: **0** have zero prose lines, so this
cannot fire on real writing.

**What it covers, stated rather than implied.** Fenced code, markdown tables and YAML front matter.
It does NOT fire on a bullet list or a bare URL list, because `_prose_line_mask` counts list items as
prose and the rewriter does rewrite them — right for bullets, a miss for URLs, and a caveat firing on
every list would be noise on the most common markdown there is.
"""

from __future__ import annotations

import logging

import pytest

from untell.scripts.score import _no_prose_warning, score_text

CODE = "```python\n" + "\n".join(f"def f{i}(a, b):\n    return a + b * {i}" for i in range(30)) + "\n```"
TABLE = "| name | value |\n|---|---|\n| alpha | 1 |\n| beta | 2 |\n| gamma | 3 |"
FRONT_MATTER = "---\ntitle: Example\ntags: [a, b, c]\ndate: 2026-01-01\n---"
PROSE = (
    "Salt lowers the freezing point of water, which is why councils spread it on roads in winter. "
    "It works down to about minus nine degrees, below which other chemicals are needed instead."
)


@pytest.fixture(autouse=True)
def _quiet(caplog):
    caplog.set_level(logging.CRITICAL)


@pytest.mark.parametrize("text", [CODE, TABLE, FRONT_MATTER], ids=["code", "table", "front matter"])
def test_a_document_with_no_prose_is_flagged_as_undefined(text: str) -> None:
    assert _no_prose_warning(text)


def test_ordinary_prose_says_nothing(prose: str = PROSE) -> None:
    """Guards the guard. A note on every document is a note nobody reads, and 0 of 120 corpus texts
    trigger this one."""
    assert _no_prose_warning(prose) is None


def test_prose_with_a_code_block_still_counts_as_prose() -> None:
    """The mixed case is the common one — a paragraph with an example under it — and the rewriter
    genuinely has something to do there. MEASURED: 1 prose line of 64."""
    assert _no_prose_warning(PROSE + "\n\n" + CODE) is None


def test_it_reaches_a_real_score_result(stdlib_lite) -> None:
    """Wired, not merely defined. The defect this session has hit most often is a function that
    works and is never called.

    Pinned to the stdlib lite path: on a torch machine `tier="lite"` silently upgrades to
    GPT-2 perplexity (~10.6s first call plus seconds per score), and this test only asserts
    that a warning string appears — which the pure-Python path answers identically in
    milliseconds. The scoring path is pinned, the wiring contract is unchanged.
    """
    assert "no prose lines" in (score_text(CODE, tier="lite").get("warning") or "")
    assert "no prose lines" not in (score_text(PROSE, tier="lite").get("warning") or "")


def test_the_note_does_not_claim_the_text_is_human() -> None:
    """It has to survive being read by someone whose code really was machine-written. The claim is
    that the verdict is undefined for this input, not that the input is innocent."""
    from untell.scripts.score import _NO_PROSE_NOTE

    assert "undefined" in _NO_PROSE_NOTE
    for overclaim in ("is human", "not ai", "ignore this"):
        assert overclaim not in _NO_PROSE_NOTE.lower()


def test_a_broken_layout_module_does_not_break_scoring(monkeypatch) -> None:
    """A caveat must never break the score it qualifies."""
    import untell.layout as layout

    def _boom(_text):
        raise RuntimeError("layout is unavailable")

    monkeypatch.setattr(layout, "_prose_line_mask", _boom)
    assert _no_prose_warning(CODE) is None
    assert score_text(PROSE, tier="lite").get("max") is not None
