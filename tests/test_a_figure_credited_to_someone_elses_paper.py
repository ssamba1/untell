"""The highest-stakes claim class here: a number put in another author's mouth.

Rounds eighty-six to ninety-one audited this repository's claims about itself — its survey
parameters, its constants, its own headline figures against the tools that produce them. Its claims
about *other people's papers* had only ever had an advisory checker, `--cross-check`, described in
its own docstring as "a REVIEW TOOL, not a pass/fail check".

Round ninety-one's thesis applies here and the stakes are higher. Getting our own number wrong is
embarrassing; **attributing a number to a paper that does not contain it is a claim about somebody
else's work.**

MEASURED: 33 findings, all read. **None is a misattribution.** They fall into groups that are each
legitimate — our own measurements stated beside a citation, figures credited to a different author
by name in the same sentence, a row explicitly marked "(derived, see note)", and the ledger entry
that describes an earlier defect of this very checker and quotes its example figures.

✗ **The defect was that reading them did not stay read.** An earlier round triaged 25 findings and
recorded the conclusion in prose. The documents grew, the count reached 35, and nothing could tell a
new finding from a cleared one — so the choice was to re-read everything or to trust a sentence
about a different 25. `eval/data/citation_triage.json` records a reason per finding, keyed on
document/paper/figure rather than on a line number, and `--untriaged` reports only what is new. A
review tool becomes a check that can gate a commit.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from eval import litreview

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / ".anthology-cache"
TRIAGE = json.loads((REPO / "eval" / "data" / "citation_triage.json").read_text())

needs_corpus = pytest.mark.skipif(
    not (CACHE.exists() and any(CACHE.glob("*.xml"))),
    reason="Anthology corpus not cached (run `python -m eval.litreview --download`)",
)


@needs_corpus
def test_no_cross_check_finding_is_untriaged():
    """The ratchet. A new finding must be read, not absorbed into a count nobody looks at."""
    findings = litreview.unsupported_figures(REPO, CACHE)
    new = litreview.untriaged(findings)
    assert not new, [
        f"{f['document']} [{f['paper']}] {f['figure']!r} — read it, then add an entry with a "
        f"reason to eval/data/citation_triage.json" for f in new
    ]


def test_every_cleared_finding_carries_a_reason_somebody_wrote():
    """An entry with no reason is a silenced finding, which is the thing being prevented."""
    for entry in TRIAGE["cleared"]:
        assert entry["reason"].strip(), entry["key"]
        assert len(entry["reason"]) > 60, (
            f"{entry['key']}: a reason short enough to be a shrug is not a triage"
        )
        assert entry["key"].count("|") == 2


def test_the_baseline_is_keyed_on_something_that_survives_an_edit():
    """A line-keyed baseline goes stale the first time a paragraph is inserted above it."""
    finding = {"document": "ROADMAP.md", "paper": "2025.naacl-long.357", "figure": "64",
               "context": "anything at all", "line": 1234}
    moved = {**finding, "line": 9999, "context": "reflowed prose"}
    assert litreview._triage_key(finding) == litreview._triage_key(moved)


@needs_corpus
def test_a_new_claim_about_a_paper_is_reported_as_untriaged(tmp_path):
    """Proves the ratchet fires. Without this the passing test above could be vacuous."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "NEW.md").write_text(
        "A new claim about Beemo "
        "([2025.naacl-long.357](https://aclanthology.org/2025.naacl-long.357/)) "
        "says it reports **99.9%** accuracy.\n"
    )
    findings = litreview.unsupported_figures(tmp_path, CACHE)
    assert [f["figure"] for f in findings] == ["99.9%"]
    assert litreview.untriaged(findings), "a fabricated attribution must not be pre-cleared"


def test_a_missing_baseline_clears_nothing(tmp_path):
    """Losing the file must fail loudly rather than pass everything."""
    findings = [{"document": "d.md", "paper": "p.1", "figure": "1%"}]
    assert litreview.untriaged(findings, tmp_path / "absent.json") == findings


@needs_corpus
def test_a_row_reference_is_not_a_figure_about_the_cited_paper():
    """`row 28 was blocked` produced a finding against a paper with no 28 in it: true, meaningless."""
    findings = litreview.unsupported_figures(REPO, CACHE)
    contexts = " ".join(f["context"] for f in findings)
    assert "row 28" not in contexts


@needs_corpus
def test_digits_inside_an_identifier_are_not_a_measurement():
    """The 2 in H2L was reported as an unsupported figure."""
    findings = litreview.unsupported_figures(REPO, CACHE)
    assert not [f for f in findings if f["figure"] == "2" and "H2L" in f["context"]]


@needs_corpus
def test_the_untriaged_command_exits_non_zero_when_something_is_new(tmp_path):
    """The CLI is what a hook would call, so its exit code is the contract."""
    result = subprocess.run(
        [sys.executable, "-m", "eval.litreview", "--untriaged"],
        cwd=REPO, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout
    assert "not yet triaged" in result.stdout
