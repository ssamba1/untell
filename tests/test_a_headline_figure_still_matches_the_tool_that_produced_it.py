"""Attribution says a figure named a source. This asks whether the source still contains it.

`untell-audit` enforces that every bolded figure carries a stated provenance, and 1,045 claims pass
it. That is a real guard and it is strictly weaker than it sounds: **naming a source and agreeing
with it are different properties.** Round eighty-four is the proof — a published AUROC of 0.3538
whose own reproduction command printed 0.3529. Attributed, correctly attributed, and still not the
number the tool produced. It was found by reading.

✗ **The obvious way to mechanise that does not work.** Linking a figure to an artefact by proximity —
if the prose near a number names a tool, the number should be in that tool's output — reported **15
contradictions of which every one was false**, and narrowing the scope from 900 characters to the
paragraph to the table row changed nothing. The premise is untrue: a sentence may legitimately name
a tool and quote a figure from elsewhere. `ROADMAP.md` row 33 does exactly that. No amount of
tightening rescues a false rule, and the attempt is kept in the module docstring so the next person
to have the idea finds it already tried.

✅ **What works is the opposite direction.** An explicit registry names the artefact key behind each
headline figure, so there are no false positives at all and the cost is that coverage is what
somebody registered. For a check that gates a commit, that is the right trade — this repository's
own note on the subject is that false alarms are how a checker gets ignored.

These tests exist mostly to prove the check can fail. It passes 19 of 19 today and found nothing;
its whole value is prospective, and a guard whose failure modes are never exercised is a guard that
quietly stops working.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval import claim_verification as cv

REPO = Path(__file__).resolve().parent.parent


def test_every_registered_figure_matches_its_artefact_and_its_documents():
    report = cv.check()
    assert report["drifted"] == 0, [
        f"{d['artefact']}{d['path']}: docs say {d['render']}, artefact holds {d['value']} "
        f"({d['why']})" for d in report["drift"]
    ]
    assert report["unverifiable"] == 0, report["unverifiable_detail"]
    assert report["verified"] == report["registered"]


def test_the_registry_covers_the_figures_this_repo_actually_leads_with():
    """A registry that drifts toward the easy figures stops guarding the important ones."""
    registered = {(c.artefact, c.path) for c in cv.CLAIMS}
    assert ("detection_power.json", ("auroc",)) in registered, "the inversion is the headline"
    assert ("detection_power.json", ("matched", "human", "rate")) in registered
    assert ("survey_counts.json", ("topics", "false positives/accusation")) in registered, (
        "the 13-paper row carries the whole strategy"
    )
    assert len(cv.CLAIMS) >= 15


def test_it_fails_when_the_artefact_moves_and_the_prose_does_not(tmp_path, monkeypatch):
    """The round-84 defect, mechanised. This is the case the check exists for."""
    staging = tmp_path / "data"
    staging.mkdir()
    for source in (REPO / "eval" / "data").glob("*.json"):
        (staging / source.name).write_text(source.read_text())
    moved = json.loads((staging / "detection_power.json").read_text())
    moved["auroc"] = 0.4001
    (staging / "detection_power.json").write_text(json.dumps(moved))

    monkeypatch.setattr(cv, "DATA", staging)
    report = cv.check()
    assert report["drifted"] >= 1
    assert any(d["path"] == ["auroc"] for d in report["drift"])


def test_it_fails_when_a_document_stops_stating_a_figure(tmp_path, monkeypatch):
    """The other direction: the tool is right and the prose lost the number."""
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "index.md").write_text("this document mentions no figures at all")
    (root / "ROADMAP.md").write_text("nor does this one")
    (root / "README.md").write_text("nor this")

    report = cv.check(root=root)
    assert report["drifted"] >= 1
    assert any("not stated in" in d["why"] for d in report["drift"])


def test_it_reports_a_vanished_key_as_unverifiable_rather_than_as_agreement(tmp_path, monkeypatch):
    """A missing key must never read as a pass — that is how a check silently stops checking."""
    staging = tmp_path / "data"
    staging.mkdir()
    for source in (REPO / "eval" / "data").glob("*.json"):
        (staging / source.name).write_text(source.read_text())
    stripped = json.loads((staging / "detection_power.json").read_text())
    del stripped["auroc"]
    (staging / "detection_power.json").write_text(json.dumps(stripped))

    monkeypatch.setattr(cv, "DATA", staging)
    report = cv.check()
    assert report["unverifiable"] >= 1
    assert report["verified"] < report["registered"]


def test_it_reports_an_uncommitted_artefact_rather_than_skipping_it(tmp_path, monkeypatch):
    """An artefact that stops being committed is exactly what round 86 found untracked for rounds."""
    empty = tmp_path / "nothing"
    empty.mkdir()
    monkeypatch.setattr(cv, "DATA", empty)
    report = cv.check()
    assert report["unverifiable"] == report["registered"]
    assert report["verified"] == 0


@pytest.mark.parametrize("value,render,expected", [
    (0.3529, "0.3529", True),
    (0.3044, "30.4%", True),
    (46905, "46,905", True),
    (0.996, "99.6%", True),
    (0.3538, "0.3529", False),
    (612, "613", False),
])
def test_rendering_a_stored_value_the_way_a_document_writes_it(value, render, expected):
    assert cv._renders_as(value, render) is expected


def test_the_headline_artefact_is_committed():
    """Until round 91 the most-quoted numbers here had no machine-readable source at all."""
    path = REPO / "eval" / "data" / "detection_power.json"
    assert path.exists(), "the inversion's own figures must be checkable"
    data = json.loads(path.read_text())
    assert data["auroc"] == 0.3529
    assert data["matched"]["human"]["n"] == 634
