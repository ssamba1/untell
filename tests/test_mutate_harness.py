"""Contract tests for .claude/mutate.py — the mutation harness itself.

Pins the machinery every kill in this repo was produced by:
  - mutable_lines()  which lines are mutation candidates (executable code only)
  - mask()           how a line is masked for reporting (literals blanked)
  - candidates()     the mutation generation (operator + old + new)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude"))
import mutate as M  # noqa: E402


class TestMutableLines:
    def test_code_lines_are_mutable(self) -> None:
        src = "x = 1\nif a >= b:\n    return True\n"
        out = M.mutable_lines(src)
        assert out == {1, 2, 3}

    def test_comments_blank_and_decorators_not_mutable(self) -> None:
        src = "# comment\n\n@pytest.fixture\ndef f():\n    pass\n"
        out = M.mutable_lines(src)
        assert 1 not in out
        assert 2 not in out
        assert 3 not in out
        assert 4 in out  # def line
        assert 5 in out

    def test_docstrings_not_mutable(self) -> None:
        src = '"""module doc"""\nx = 1\n'
        out = M.mutable_lines(src)
        assert 1 not in out
        assert 2 in out


class TestMask:
    def test_mask_blanks_string_literals(self) -> None:
        out = M.mask('x = "text with and or"')
        assert '"' not in out
        assert "text" not in out

    def test_mask_keeps_operators(self) -> None:
        out = M.mask("if a >= b:")
        assert ">=" in out

    def test_mask_blanks_trailing_comment(self) -> None:
        out = M.mask("x = 1  # note with 8")
        assert "note" not in out
        assert "x = 1" in out


class TestCandidates:
    def test_candidates_are_triples(self, tmp_path) -> None:
        src = "if a >= b:\n    return True\n"
        p = tmp_path / "fake_module.py"
        p.write_text(src, encoding="utf-8")
        cs = M.candidates(p)
        assert cs, "a comparison line must yield candidates"
        for line_no, new, label, old in cs:
            assert isinstance(line_no, int)
            assert isinstance(label, str)
            assert isinstance(old, str)
            assert isinstance(new, str)
            assert new != old

    def test_comparison_flip_candidate(self, tmp_path) -> None:
        src = "if a >= b:\n    pass\n"
        p = tmp_path / "fake_module.py"
        p.write_text(src, encoding="utf-8")
        cs = M.candidates(p)
        # >= is flipped to > (per the OPERATORS table)
        flips = [c for c in cs if c[2] == "boundary: >= -> >" and c[1] == "if a > b:"]
        assert flips, f"expected >= -> < flip in {cs}"

    def test_constant_bump_candidate(self, tmp_path) -> None:
        src = "if len(x) < 12:\n    pass\n"
        p = tmp_path / "fake_module.py"
        p.write_text(src, encoding="utf-8")
        cs = M.candidates(p)
        bumps = [c for c in cs if "constant" in c[2]]
        assert bumps, f"expected constant bump in {cs}"


class TestRecordSurvivors:
    """Survivor mutate.py:159 — `s not in` -> `in` (ledger dedup).

    A survivor already listed must NOT be re-appended. The mutation (`in`)
    appends it again, doubling the row and breaking the converge-don't-circle
    property that makes lanes finish."""

    def test_already_recorded_survivor_not_reappended(self, tmp_path, monkeypatch) -> None:
        ledger = tmp_path / "survivors.md"
        ledger.write_text(
            "# Mutation survivors\n\n"
            "| module | line | mutation | source |\n"
            "| --- | --- | --- | --- |\n"
            "| fake_mod.py | 5 | boundary: >= -> > | `if a >= b:` |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(M, "LEDGER", ledger)
        added = M.record_survivors("fake_mod.py", [(5, "boundary: >= -> >", "if a >= b:")])
        assert added == 0, "already-listed survivor must not be re-appended"
        text = ledger.read_text(encoding="utf-8")
        assert text.count("| fake_mod.py | 5 |") == 1, text

    def test_new_survivor_appended(self, tmp_path, monkeypatch) -> None:
        ledger = tmp_path / "survivors.md"
        ledger.write_text(
            "# Mutation survivors\n\n"
            "| module | line | mutation | source |\n"
            "| --- | --- | --- | --- |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(M, "LEDGER", ledger)
        added = M.record_survivors("fake_mod.py", [(5, "boundary: >= -> >", "if a >= b:")])
        assert added == 1
        text = ledger.read_text(encoding="utf-8")
        assert "| fake_mod.py | 5 |" in text, text
