"""audit --fix-counts and the census-parse failure: the two repair/error paths the
doc-state tests do not reach."""

from __future__ import annotations

from untell.scripts import audit


def _repo_with(tmp_path, census: str | None = None) -> None:
    """A minimal repo tree check_derivable can walk: README (early-return guard),
    a tests dir for the module count, pyproject for the console-script check."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# x\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\n[project.scripts]\nfoo = "x:main"\n', encoding="utf-8"
    )
    if census is not None:
        (tmp_path / "docs").mkdir(exist_ok=True)
        (tmp_path / "docs" / "humanizer-census.json").write_text(census, encoding="utf-8")


def test_fix_counts_rewrites_stale_numbers(monkeypatch, tmp_path) -> None:
    """--fix-counts replaces the test/module numbers in the comparative docs with the
    measured ones, and only those numbers."""
    _repo_with(tmp_path)
    doc = tmp_path / "README.md"
    doc.write_text("The suite has **100** tests in 9 modules.\n", encoding="utf-8")
    monkeypatch.setattr(audit, "REPO", tmp_path)
    monkeypatch.setattr(audit, "_collected_test_count", lambda: 42)

    edits = audit.fix_counts()
    assert len(edits) == 1
    assert "README.md" in edits[0]
    text = doc.read_text(encoding="utf-8")
    assert "**42** tests" in text
    assert "1 modules" in text
    assert "100" not in text and "9" not in text


def test_fix_counts_says_nothing_when_already_current(monkeypatch, tmp_path) -> None:
    _repo_with(tmp_path)
    doc = tmp_path / "README.md"
    doc.write_text("The suite has **42** tests in 1 modules.\n", encoding="utf-8")
    monkeypatch.setattr(audit, "REPO", tmp_path)
    monkeypatch.setattr(audit, "_collected_test_count", lambda: 42)
    assert audit.fix_counts() == []


def test_fix_counts_main_prints_the_edits(monkeypatch, tmp_path, capsys) -> None:
    _repo_with(tmp_path)
    doc = tmp_path / "README.md"
    doc.write_text("The suite has **100** tests in 9 modules.\n", encoding="utf-8")
    monkeypatch.setattr(audit, "REPO", tmp_path)
    monkeypatch.setattr(audit, "_collected_test_count", lambda: 42)
    audit.main(["--fix-counts"])
    out = capsys.readouterr().out
    assert "counts set to 42 tests, 1 modules" in out


def test_census_json_that_does_not_parse_is_a_named_failure(monkeypatch, tmp_path) -> None:
    """A corrupt census file must fail loudly under its own check name, not vanish."""
    _repo_with(tmp_path)
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs" / "humanizer-census.json").write_text("{not valid json", encoding="utf-8")
    (tmp_path / "docs" / "humanizer-census.md").write_text("# census\n", encoding="utf-8")
    monkeypatch.setattr(audit, "REPO", tmp_path)
    report = audit.Report()
    audit.check_derivable(report)
    finding = next(f for f in report.findings if f.name == "the census raw data parses")
    assert finding.ok is False
    assert "JSONDecodeError" in finding.detail
