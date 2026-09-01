"""Making a check fast is worthless if it stops checking.

`check_no_dead_functions` was 58 of the audit's 70 seconds: it ran `re.findall(rf"\\b{name}\\b",
corpus)` once for each of ~570 functions over a multi-megabyte string, which is O(functions x
codebase). Tokenising the corpus once and counting is O(corpus + functions) — MEASURED at 59.0s
against 0.3s, a 212x speedup, with identical counts for every name and an identical verdict.

That matters beyond tidiness: `untell-audit` runs in the pre-commit hook, and a gate slow enough to
skip is a gate nobody runs. But an optimisation that quietly stops finding things looks exactly like
a fast, passing check — so these tests exercise the check against a function that really is dead.
"""

from __future__ import annotations

import pytest

from untell.scripts import audit as A


def test_a_genuinely_unreferenced_function_is_still_caught(tmp_path, monkeypatch):
    """The behaviour, not the speed. A function defined once and mentioned nowhere else must be
    reported — if the rewrite had broken the counting, everything would simply pass."""
    (tmp_path / "untell").mkdir()
    (tmp_path / "eval").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "untell" / "m.py").write_text(
        "def a_function_nobody_calls():\n    return 1\n\n\n"
        "def a_function_that_is_called():\n    return 2\n",
        encoding="utf-8")
    (tmp_path / "tests" / "t.py").write_text("a_function_that_is_called()\n", encoding="utf-8")

    monkeypatch.setattr(A, "REPO", tmp_path)
    report = A.Report()
    A.check_no_dead_functions(report)
    finding = next(f for f in report.findings if "unreferenced" in f.name)
    assert not finding.ok, "a function mentioned nowhere but its own def must be reported"
    assert "a_function_nobody_calls" in finding.detail
    assert "a_function_that_is_called" not in finding.detail


def test_a_referenced_function_is_not_reported(tmp_path, monkeypatch):
    """Guards the guard: a check that flagged everything would also 'still work'."""
    (tmp_path / "untell").mkdir()
    (tmp_path / "eval").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "untell" / "m.py").write_text(
        "def helper():\n    return 1\n\n\ndef caller():\n    return helper()\n", encoding="utf-8")
    (tmp_path / "tests" / "t.py").write_text("caller()\n", encoding="utf-8")

    monkeypatch.setattr(A, "REPO", tmp_path)
    report = A.Report()
    A.check_no_dead_functions(report)
    finding = next(f for f in report.findings if "unreferenced" in f.name)
    assert finding.ok, f"nothing here is dead, but it reported: {finding.detail}"


def test_a_name_mentioned_only_in_prose_counts_as_referenced(tmp_path, monkeypatch):
    """The reason this is a textual count rather than a call graph: the repo dispatches rewriters and
    detectors by string name, so a registry entry or a document naming a function is a real
    reference. Word-boundary tokenising has to keep that behaviour."""
    (tmp_path / "untell").mkdir()
    (tmp_path / "eval").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "untell" / "m.py").write_text("def dispatched_by_name():\n    return 1\n",
                                              encoding="utf-8")
    (tmp_path / "docs" / "d.md").write_text("The `dispatched_by_name` entry point.\n",
                                            encoding="utf-8")

    monkeypatch.setattr(A, "REPO", tmp_path)
    report = A.Report()
    A.check_no_dead_functions(report)
    assert next(f for f in report.findings if "unreferenced" in f.name).ok


def test_a_substring_of_another_name_is_not_a_reference(tmp_path, monkeypatch):
    """Word boundaries, which is the property the tokenised version has to preserve. `score` must not
    be counted as referenced merely because `score_text` appears."""
    (tmp_path / "untell").mkdir()
    (tmp_path / "eval").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "untell" / "m.py").write_text(
        "def score():\n    return 1\n\n\ndef score_text():\n    return 2\n", encoding="utf-8")
    (tmp_path / "tests" / "t.py").write_text("score_text()\nscore_text()\n", encoding="utf-8")

    monkeypatch.setattr(A, "REPO", tmp_path)
    report = A.Report()
    A.check_no_dead_functions(report)
    finding = next(f for f in report.findings if "unreferenced" in f.name)
    assert not finding.ok
    assert "score (" in finding.detail, "`score` is dead; `score_text` must not rescue it"


@pytest.mark.parametrize("seconds", [30])
def test_the_whole_audit_stays_fast_enough_to_keep_in_a_commit_hook(seconds):
    """The optimisation's actual purpose. MEASURED after the rewrite: about 11 seconds, against 70
    before. The bar is deliberately loose — this guards against a regression to the old shape, not
    against ordinary growth."""
    import time

    start = time.monotonic()
    A.run()
    elapsed = time.monotonic() - start
    assert elapsed < seconds, (
        f"untell-audit took {elapsed:.0f}s. It runs in the pre-commit hook; past about half a "
        f"minute people stop running the gate. Check for a per-item scan over the whole corpus."
    )


# --- comma-formatted counts ----------------------------------------------------------------------


@pytest.mark.parametrize("text,expected", [
    ("the suite is 9,958 tests", 9958),
    ("the suite is 9958 tests", 9958),
    ("**9,958** tests across 614 modules", 9958),
    ("1,234 tests", 1234),
    ("500 tests", 500),
])
def test_a_comma_formatted_test_count_is_read_whole(text, expected, tmp_path, monkeypatch):
    """Without commas in the pattern, "9,958 tests" matched as **958** — the digit run stops at the
    comma — and the check reported a document as claiming 958 tests when it claimed 9,958. A false
    alarm accusing a correct document of understating by an order of magnitude, which is the kind
    that gets a check ignored.

    Found by writing "9,958 tests" in the ledger, in a sentence about this very number.
    """
    monkeypatch.setattr(A, "REPO", tmp_path)
    # COMPARATIVE_DOCS, not LIVE_DOCS: `check_test_count_claims` iterates the former.
    # Patching the wrong one made the five passing cases below pass VACUOUSLY — the
    # file was never scanned — and only the negative case noticed.
    monkeypatch.setattr(A, "COMPARATIVE_DOCS", ("d.md",))
    monkeypatch.setattr(A, "_collected_test_count", lambda: expected)
    (tmp_path / "d.md").write_text(text, encoding="utf-8")

    report = A.Report()
    A.check_test_count_claims(report)
    assert not report.count_drifts, (
        f"{text!r} should read as {expected}, but the check reported: "
        f"{[d.detail for d in report.count_drifts]}"
    )


def test_a_genuinely_wrong_comma_formatted_count_is_still_caught(tmp_path, monkeypatch):
    """Guards the guard: accepting commas must not make the check accept anything."""
    monkeypatch.setattr(A, "REPO", tmp_path)
    # COMPARATIVE_DOCS, not LIVE_DOCS: `check_test_count_claims` iterates the former.
    # Patching the wrong one made the five passing cases below pass VACUOUSLY — the
    # file was never scanned — and only the negative case noticed.
    monkeypatch.setattr(A, "COMPARATIVE_DOCS", ("d.md",))
    monkeypatch.setattr(A, "_collected_test_count", lambda: 9958)
    (tmp_path / "d.md").write_text("the suite is 1,200 tests", encoding="utf-8")

    report = A.Report()
    A.check_test_count_claims(report)
    assert report.count_drifts, "1,200 against 9,958 is real drift and must be reported"
