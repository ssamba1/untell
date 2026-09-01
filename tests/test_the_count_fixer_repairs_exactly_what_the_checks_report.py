"""The check and the repair it recommends must agree on what a claim is.

`untell-audit` reports a stale count and tells the reader to run `untell-audit --fix-counts`. Until
round sixty-two those were two different notions of "count claim", and the gap ran both ways:

* The checks read `without_code_spans(...)`; the fixer read raw text. So the fixer rewrote
  `the 63 modules they most import` — a code span, a quotation of a past false positive — into
  `the 624 modules they most import`, a false statement, in a sentence explaining a bug.
* The checks matched `9202 tests` and `9,958 tests`; the fixer required `**N**` with no comma. So of
  the three claims the checks were reporting, the fixer repaired **zero**.

Running the repair the audit recommended therefore corrupted a document and fixed nothing. Both
patterns are now defined once and shared, and the substitution is applied only where a check would
have looked.

The third defect was scope: the fixer rewrote the verification ledger, whose entries are historical
by convention — round fifty-nine established that a superseded entry is annotated, not rewritten.
"""

from __future__ import annotations

import re

from untell.scripts import audit
from untell.scripts.audit import (
    _MODULE_CLAIM,
    _TEST_CLAIM,
    LEDGER,
    counted_docs,
    substitute_outside_code_spans,
    without_code_spans,
)


def _fix_modules(text: str, n: int) -> str:
    return substitute_outside_code_spans(_MODULE_CLAIM, lambda m: f"{n}{m.group(2)}", text)


def _fix_tests(text: str, n: int) -> str:
    return substitute_outside_code_spans(
        _TEST_CLAIM,
        lambda m: f"{m.group(1)}{audit._regroup(n, m.group(2))}{m.group(3)}{m.group(4)}",
        text)


def test_a_count_inside_a_code_span_is_quoted_not_claimed_and_survives_repair():
    """The exact corruption, pinned. This sentence describes a past defect; rewriting the number in
    it makes the sentence false while leaving it looking repaired."""
    line = "round forty-six's `the 63 modules they most import` read as a test-module count."
    assert _fix_modules(line, 624) == line


def test_the_same_number_outside_backticks_is_a_claim_and_is_repaired():
    """The other half. A rule that protected everything would protect the stale counts too."""
    assert _fix_modules("the suite is 620 modules today", 624) == "the suite is 624 modules today"


def test_the_fixer_repairs_the_unbolded_claim_the_checks_report():
    """`docs/humanizer-census.md` said `9202 tests` for as long as the fixer existed, because the
    fixer's pattern required bold and the document's claim was not."""
    before = "**Test depth** — 9202 tests (reproduce with a collect-only run)"
    assert "10278 tests" in _fix_tests(before, 10278)


def test_a_grouped_number_stays_grouped_and_a_bold_one_stays_bold():
    """Repairing a count must not silently restyle the document around it."""
    assert _fix_tests("we run 9,958 tests", 10278) == "we run 10,278 tests"
    assert _fix_tests("we run **9958** tests", 10278) == "we run **10278** tests"
    assert _fix_tests("we run **9,958** tests", 10278) == "we run **10,278** tests"


def test_the_checks_and_the_fixer_use_the_same_patterns():
    """The defect was two notions of a claim, so the guard is that there is now one of each.

    Asserting the constants exist is not enough — this asserts they still *match* the forms both
    sides have to agree on.
    """
    assert re.search(_MODULE_CLAIM, "620 modules") and re.search(_MODULE_CLAIM, "620 test modules")
    for form in ("9202 tests", "9,958 tests", "**9958** tests", "**9,958** tests"):
        assert re.search(_TEST_CLAIM, form), form


def test_the_ledger_is_outside_both_the_counting_checks_and_the_repair():
    """An append-only audit trail cannot be auto-rewritten; its figures describe past rounds."""
    assert LEDGER == "docs/research-verification.md"
    assert LEDGER not in counted_docs()
    assert LEDGER in audit.COMPARATIVE_DOCS, (
        "the ledger stays a live document for every other check — only counting stops at it")
    assert len(counted_docs()) == len(audit.COMPARATIVE_DOCS) - 1


def test_the_doc_list_is_derived_live_so_patching_the_public_name_still_works(monkeypatch):
    """Three tests in this suite patch `COMPARATIVE_DOCS`. A constant computed at import would
    ignore them and scan the real repository instead — five cases passing vacuously, which is the
    defect `test_the_dead_function_check_is_fast_and_still_works.py` already records once."""
    monkeypatch.setattr(audit, "COMPARATIVE_DOCS", ("README.md", LEDGER))
    assert counted_docs() == ("README.md",)


def test_the_substitution_preserves_everything_it_does_not_replace():
    """Offset splicing is easy to get wrong by one character, and the failure is silent."""
    text = "a 1 modules b `2 modules` c 3 modules d"
    assert _fix_modules(text, 9) == "a 9 modules b `2 modules` c 9 modules d"
    # The splice relies on the blanked copy being the same length as the original, so a match
    # offset means the same position in both. Blanking, not deleting, is what buys that.
    assert len(without_code_spans(text)) == len(text)
    assert without_code_spans(text).count("modules") == 2, (
        "the code span's count must be invisible to the matcher, which is the point")


def test_the_substitution_is_a_no_op_when_nothing_matches():
    for text in ("", "no counts here", "`620 modules`"):
        assert _fix_modules(text, 624) == text
