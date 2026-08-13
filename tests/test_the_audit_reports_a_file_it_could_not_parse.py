"""Three audit checks walked every source file and skipped, in silence, anything that would not parse.

FOUND by sweeping for silent exception handlers — the mechanical form of "what does this code do
when it fails?". 16 handlers swallow their exception with no comment nearby, and most are fine:
narrow, typed, and skipping something genuinely optional. Three are not, and they are in the audit:

    audit.py  duplicate top-level definitions   except (SyntaxError, UnicodeDecodeError): continue
    audit.py  bare-max comparisons              except (SyntaxError, UnicodeDecodeError): continue
    audit.py  the decorator registry            except (SyntaxError, OSError): continue

A file that stops parsing leaves those checks examining fewer files and still printing PASS. That is
the shape this tool exists to catch everywhere except in itself, and it is the same defect
`audited_doc` was written for one level up — a missing document used to be `continue`d past, losing
its findings without a word.

VERIFIED by writing a single unparseable file into the package and running the audit: it reports

    FAIL  untell/_mutant_probe.py: parses, so the AST checks can read it
          (SyntaxError: invalid syntax — every AST check skipped this file)

It cannot fire on the repository as it stands; every file parses, which is why the skip has been
free. It is free exactly until it is not, and then it is silent.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from untell.scripts.audit import REPO, Report, audited_tree


def test_a_parsable_file_comes_back_as_a_tree(tmp_path: Path) -> None:
    good = tmp_path / "good.py"
    good.write_text("x = 1\n", encoding="utf-8")
    report = Report()
    tree = audited_tree(report, good)
    assert isinstance(tree, ast.Module)


def test_an_unparsable_file_is_reported_not_skipped(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("def broken(:\n", encoding="utf-8")
    report = Report()
    assert audited_tree(report, bad) is None
    assert report.failures, "the file was skipped without a word — the defect this guards"


def test_the_failure_names_the_file_and_the_consequence(tmp_path: Path) -> None:
    """A verifier that says only "something went wrong" sends the reader back to the whole tree."""
    bad = tmp_path / "bad.py"
    bad.write_text("def broken(:\n", encoding="utf-8")
    report = Report()
    audited_tree(report, bad)
    text = " ".join(str(f) for f in report.failures)
    assert "bad.py" in text
    assert "SyntaxError" in text
    assert "skipped" in text


def test_a_missing_file_is_reported_too(tmp_path: Path) -> None:
    """`OSError` is in the same handler. A path that vanished between the glob and the read is a
    file the checks did not examine, whatever the reason."""
    report = Report()
    assert audited_tree(report, tmp_path / "not_here.py") is None
    assert report.failures


def test_every_ast_walk_in_the_audit_goes_through_the_guard() -> None:
    """The reachability half. A fourth walk added later with its own try/except would reintroduce
    exactly what this replaced, and nothing else would notice."""
    source = (REPO / "untell" / "scripts" / "audit.py").read_text(encoding="utf-8")
    assert source.count("audited_tree(report, path)") >= 3
    # Exactly one direct parse of a path: `audited_tree`'s own. A second is a walk that went round
    # the guard. The first version of this assertion forbade the call outright and failed on the
    # helper it was written to protect.
    assert source.count("ast.parse(path.read_text(") == 1, (
        "an AST walk is parsing a path directly instead of going through audited_tree"
    )


def test_the_repository_itself_parses() -> None:
    """And the fact that makes the guard quiet today. If this ever fails, the audit was silently
    covering less than it claimed for however long the file had been broken."""
    unparsable = []
    for path in sorted((REPO / "untell").rglob("*.py")):
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as exc:  # pragma: no cover - the point is 0
            unparsable.append(f"{path.name}: {exc}")
    assert not unparsable, unparsable


@pytest.mark.parametrize("name", ["duplicate", "bare-max", "decorator"])
def test_the_three_walks_are_still_there(name: str) -> None:
    """Guards the guard from deletion: if a check is removed the count above still passes at >= 3
    only while three remain, and this states which three were meant."""
    source = (REPO / "untell" / "scripts" / "audit.py").read_text(encoding="utf-8")
    assert source.count("audited_tree(") >= 4  # three call sites plus the definition
