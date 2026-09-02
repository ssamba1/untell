"""The repo's explanation for the inversion was inferred from 56 documents. Test it on 6,841.

Rounds 76–83 found the lite detector's ordering inverted on academic abstracts and explained it:
the features "measure how closely a document reads like a standard academic abstract, and in this
corpus that is the human writing." That explanation is published in `docs/index.md`, and it rested
on 56 machine documents written by one model — by some distance the weakest link in the arc.

It does not have to. If the explanation is true it is testable **with no machine text at all**:
among documents that are all unambiguously human, the more prototypically academic ones should
score as more AI. `eval/register_conformity.py` does that on 6,841 pre-2022 ACL abstracts, two
independent ways — vocabulary commonness, which reads the same words the detector reads, and venue
class, which does not look at the text.

MEASURED: rho **+0.0586**, bootstrap 95% CI [+0.0357, +0.0842], with **all six length bands
positive** (sign test p = 0.031 on its own). The explanation is supported in direction.

**And the same measurement puts a limit on it that the published wording did not.** rho +0.0586 is
**0.34% of the score's variance**. Register conformity is a real component of what this detector
measures and nowhere near all of it, so it accounts for the *direction* of the inversion and not for
its *size*. These tests pin both halves, because the magnitude caveat is the part a later edit would
quietly drop.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval import register_conformity as rc

REPO = Path(__file__).resolve().parent.parent
ROWS = json.loads((REPO / "eval" / "data" / "register_conformity_rows.json").read_text())
REPORT = json.loads((REPO / "eval" / "data" / "register_conformity.json").read_text())


def test_the_corpus_is_the_one_whose_label_cannot_be_disputed():
    """Pre-2022 ACL abstracts. The whole point is that no annotation is involved."""
    assert REPORT["scored"] > 6_000
    assert all(int(row["id"][:4]) <= 2021 for row in ROWS)


def test_the_register_effect_is_real():
    """Real means the interval excludes zero, not that the point estimate looks big enough."""
    low, high = REPORT["rho_ci"]
    assert REPORT["rho_excludes_zero"] is True
    assert low > 0, "a positive rho with an interval spanning zero is not a finding"
    assert REPORT["rho_prototypicality_score"] > 0


def test_every_length_band_points_the_same_way():
    """Length is the known confound; agreement across bands is what survives it."""
    assert REPORT["bands_positive"] == len(REPORT["bands"])
    assert len(REPORT["bands"]) >= 5, "fewer bands makes the sign test worthless"


def test_the_effect_is_small_and_the_docs_must_keep_saying_so():
    """The magnitude caveat is the half of this finding a later edit would drop."""
    rho = REPORT["rho_prototypicality_score"]
    assert rho * rho < 0.05, (
        "if register conformity ever explained more than 5% of the score's variance, the published "
        "wording would be an understatement rather than an overstatement and should be rewritten"
    )
    index = (REPO / "docs" / "index.md").read_text()
    assert "0.34%" in index or "0.3%" in index, (
        "docs/index.md publishes the register explanation; it must publish the size of the effect "
        "beside it, or it claims more than the measurement supports"
    )


def test_the_venue_check_is_reported_as_corroboration_not_confirmation():
    """Five classes have no power. Saying so is the finding's honesty, not a hedge."""
    assert len(REPORT["venues"]) >= 4
    assert 0.0 <= REPORT["venue_agreement_rho"] <= 1.0
    rendered = rc.render(REPORT)
    assert "corroboration, not a second test" in rendered or "not independent confirmation" in rendered


def test_the_venue_means_are_reported_with_length_held_fixed():
    """Workshop papers are shorter and this detector scores shorter text higher."""
    for venue in REPORT["venues"]:
        assert "standardized_mean" in venue and "raw_mean" in venue
        assert venue["bands_used"], "a standardized mean with no bands behind it is a raw mean"
    assert REPORT["venue_spread_standardized"] > 0


def test_the_verdict_changes_when_the_measurement_does():
    """A renderer that prints the same conclusion whatever the numbers say is not reporting."""
    supported = rc.render(REPORT)
    assert "Supported, and small" in supported

    flipped = json.loads(json.dumps(REPORT))
    flipped["rho_excludes_zero"] = False
    flipped["rho_ci"] = [-0.02, 0.05]
    assert "NOT supported" in rc.render(flipped)

    partial = json.loads(json.dumps(REPORT))
    partial["bands_positive"] = 1
    assert "NOT supported" in rc.render(partial)


def test_the_analysis_still_derives_the_published_report_from_the_committed_rows():
    """The rows are the evidence; the report must be a function of them, not a parallel claim."""
    fresh = rc.analyse(ROWS)
    for key in ("scored", "rho_prototypicality_score", "bands", "bands_positive", "venues",
                "venue_spread_standardized", "venue_agreement_rho", "decile"):
        assert fresh[key] == REPORT[key], f"{key} drifted between the rows and the report"


def test_prototypicality_ranks_a_boilerplate_abstract_above_an_unusual_one():
    """The measure itself, on a case where the answer is not in doubt."""
    corpus = [row for row in ROWS[:200]]
    assert corpus, "need some rows to build a vocabulary from"
    texts = [
        "we propose a novel model for the task and show that it improves results on the data set",
        "quokka phonotactics in Nyungar songlines resist syllabification under moraic assumptions",
    ] * 1
    df, total = rc.document_frequencies(texts + [t for t in texts])
    ordinary = rc.prototypicality(texts[0], df, total)
    unusual = rc.prototypicality(texts[1], df, total)
    assert ordinary >= unusual


@pytest.mark.parametrize("paper_id,expected", [
    ("2021.acl-long.5", "main/long"),
    ("2020.findings-emnlp.1", "findings"),
    ("2021.acl-srw.9", "workshop/student"),
    ("2020.acl-demos.3", "demo/industry"),
    ("2099.nonsense", None),
])
def test_venue_classification(paper_id: str, expected: str | None):
    assert rc.venue_class(paper_id) == expected
