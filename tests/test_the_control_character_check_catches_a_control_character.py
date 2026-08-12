"""The check that would have caught last commit's bug, tested on the thing it is named for.

`check_no_control_characters` scans every tracked text file for C0 bytes. It exists because an
escape mangled by a shell or a non-raw string literal is invisible in a diff — a regex ending in
0x08 reads as `\\b` to any reviewer and matches nothing at runtime.

It works. VERIFIED by injecting a backspace into untell/scripts/numerals.py and running the check
directly: FAIL, detail `found: ['untell/scripts/numerals.py:122 U+0008']`. The previous commit
introduced exactly that byte and the check did not fire, for the dull reason that nothing ran it
between the edit and the fix.

What was missing is a known-positive. `test_every_audit_check_can_fail.py` mutates this check by
taking git away — it asserts that scanning zero files reports a failure rather than "clean", which
is a different property. Nothing asserted that a real control byte in a real file is reported, so
the detection could have regressed to a no-op and both suites would have stayed green.

Runs against a temporary tree rather than the repository, so a failing assertion can never leave a
control character in a tracked file.
"""
from __future__ import annotations

import pytest

import untell.scripts.audit as audit


@pytest.fixture
def fake_tree(tmp_path, monkeypatch):
    """A stand-in repo whose 'tracked' files are whatever the test writes."""
    (tmp_path / "untell").mkdir()
    monkeypatch.setattr(audit, "REPO", tmp_path)
    monkeypatch.setattr(audit, "_tracked_text_files", lambda: ["untell/thing.py"])
    return tmp_path


def _run(tree) -> tuple[bool, str]:
    report = audit.Report()
    audit.check_no_control_characters(report)
    finding = report.findings[-1]
    return finding.ok, finding.detail


def test_a_backspace_in_a_source_file_is_reported(fake_tree):
    """The exact byte from the numerals regex, in the exact position it took."""
    (fake_tree / "untell" / "thing.py").write_bytes(b'PATTERN = r"(\\d+)\x08"\n')

    ok, detail = _run(fake_tree)
    assert not ok, "a literal backspace in a source file was reported as clean"
    assert "U+0008" in detail, detail
    assert "thing.py" in detail, detail


@pytest.mark.parametrize("byte,name", [(b"\x07", "BEL"), (b"\x0c", "FF"), (b"\x7f", "DEL")])
def test_other_control_characters_are_reported_too(fake_tree, byte: bytes, name: str):
    (fake_tree / "untell" / "thing.py").write_bytes(b"x = 1" + byte + b"\n")
    ok, _ = _run(fake_tree)
    assert not ok, f"{name} was not reported"


def test_ordinary_source_is_clean(fake_tree):
    """Guards the guard: a check that fails on everything is no more useful than one that passes."""
    (fake_tree / "untell" / "thing.py").write_text(
        'PATTERN = r"(\\d+)\\b"\n\ttabbed = True\n', encoding="utf-8"
    )
    ok, detail = _run(fake_tree)
    assert ok, detail


def test_a_carriage_return_inside_a_line_ending_is_not_an_offender(fake_tree):
    """CRLF is a normal Windows line ending; flagging it would make the check unusable."""
    (fake_tree / "untell" / "thing.py").write_bytes(b"x = 1\r\ny = 2\r\n")
    ok, detail = _run(fake_tree)
    assert ok, detail


def test_the_line_number_points_at_the_byte(fake_tree):
    """A report that names the file but not the line sends the reader hunting for an invisible byte."""
    (fake_tree / "untell" / "thing.py").write_bytes(b"one\ntwo\nthree\x08\nfour\n")
    _, detail = _run(fake_tree)
    assert ":3 " in detail, detail
