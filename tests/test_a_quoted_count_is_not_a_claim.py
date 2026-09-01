"""A document may quote a count without asserting it — the use/mention distinction, in Markdown.

Five times in three rounds, a ledger entry **describing** a count-drift defect reproduced the literal
it warned about and re-triggered the check. Every one of those checks was right on its own terms: a
document did state a count next to a noun the audit tracks. What was missing was any way to write
about a count at all, and the workaround each time was to contort the prose — spelling a number out
in words, renaming a noun — which produces a worse document and buys no safety.

Markdown already encodes the distinction. `the suite is 9,958 tests` is a claim; the same text inside
backticks is a quotation of a string. `without_code_spans` blanks inline code before the count checks
read a document.

**The cost is real**: a genuinely stale count written inside backticks is now invisible. That is the
price of being able to quote one, and these tests hold the boundary tight enough for it to be worth
paying — prose, bold and italics are all still claims.
"""

from __future__ import annotations

from untell.scripts import audit as A


def test_a_plain_prose_count_is_still_a_claim():
    assert "9958" in A.without_code_spans("the suite is 9958 tests").replace(",", "")


def test_a_bolded_count_is_still_a_claim():
    """Bold is emphasis, not quotation. Every real count in these documents is written this way."""
    assert "**9958**" in A.without_code_spans("the suite is **9958** tests")


def test_an_italicised_count_is_still_a_claim():
    assert "958" in A.without_code_spans("it claimed *958 tests*")


def test_an_inline_code_span_is_blanked():
    out = A.without_code_spans("the check read `958 tests` from the line")
    assert "958" not in out
    assert "the check read" in out and "from the line" in out


def test_blanking_preserves_offsets():
    """Replaced with spaces rather than removed, so any line or column a check reports still points
    at the right place in the original file."""
    text = "abc `xyz` def"
    assert len(A.without_code_spans(text)) == len(text)


def test_a_multiline_backtick_run_is_not_treated_as_a_span():
    """An unclosed backtick must not blank the rest of the document — that would exempt every claim
    after a stray character."""
    text = "a claim of 9958 tests\nand a stray ` backtick\nanother claim of 7777 tests\n"
    out = A.without_code_spans(text)
    assert "9958" in out and "7777" in out


def test_the_repositorys_live_count_is_stated_outside_backticks():
    """The risk this exemption creates, pinned at the only place it matters.

    The first version of this test asserted that blanking code spans loses no match in any audited
    document. That was true when it was written and **wrong by the end of the same round**: the
    point of the change is to let the ledger quote counts, and the first sentences to use it broke
    the test immediately. A guard that fails on every correct use of the feature it guards is not a
    guard.

    The real hazard is narrower and specific: the repository's own **current** figures live in
    `docs/why-best-open-repo.md`, and if those were written inside backticks the audit would stop
    checking the one claim it exists to check. So that is what this asserts — the live count must be
    visible to the checker, whatever the ledger does when quoting history.
    """
    import re
    from pathlib import Path

    repo = Path(__file__).resolve().parent.parent
    text = (repo / "docs" / "why-best-open-repo.md").read_text(encoding="utf-8")
    visible = A.without_code_spans(text)
    for pattern, what in ((r"\*{0,2}(\d[\d,]{2,6})\*{0,2}\s+tests\b", "test count"),
                          (r"(\d+)\s+(?:test\s+)?modules\b", "module count")):
        assert re.search(pattern, visible), (
            f"why-best-open-repo.md states no {what} the audit can see — if it is written inside "
            f"backticks the drift check silently stops running on the repo's own headline figure"
        )


def test_the_count_checks_actually_use_it():
    """A helper nothing calls is a helper that guards nothing."""
    import inspect

    source = inspect.getsource(A)
    assert source.count("without_code_spans(") >= 3, (
        "both count checks must read documents through it, and it must be defined"
    )
