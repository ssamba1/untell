"""A correction that is written down but not propagated is not a correction.

The verification ledger records every claim this project retracted. Recording is not removing: round
twenty-two found the collapsed Karr range "38-80%" still live 700 lines below the table retracting
it, and round twenty-three found the same figure in the single most quoted sentence of the research
documents — three lines *underneath* the paragraph correcting it — and in a second document that had
copied that sentence.

So the retraction table needs checking against the body, not only appending to. This test pins the
retired forms that have actually escaped before, or that would be easy to reintroduce by copying an
older paragraph. A hit is not automatically a defect: the ledger has to quote what it retracts, so a
line that is *recording* the correction is allowed. The rule is that the retired form may appear only
alongside a marker that says it is being corrected.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# README.md is in this list because it was NOT, and carried figures superseded twenty-seven rounds
# earlier: 15.8% where the measurement is 20.5%, 26.7% where it is 30.0%, and an n of 120 where the
# corpus now supports 599. `untell-audit` reads the README — it is in LIVE_DOCS — but the attribution
# check only asks whether a number states a source, never whether it is still true. The retraction
# guard is the check that asks that, and the repository's most-read document was outside it.
DOCS = ("README.md", "ROADMAP.md", "ai-writing-research.md", "docs/research-to-build.md",
        "docs/research-verification.md", "docs/strategy-options.md", "docs/index.md",
        "docs/why-best-open-repo.md")

# Code carries measured figures too, in docstrings that explain WHY a threshold or a band boundary
# is what it is. Round thirty-one re-measured the pre-LLM false-positive rate and updated every
# document; `untell/calibrate.py` went on quoting 15.8% and "26.7% at 50 words or fewer" for seven
# rounds, because `untell-audit` scans documents and nothing scanned source. A stale number in a
# docstring is worse than one in a document: it is the stated justification for a shipped default.
CODE = tuple(
    str(p.relative_to(REPO))
    for directory in ("untell", "eval")
    for p in (REPO / directory).rglob("*.py")
)

# Words that mark a line as *discussing* a correction rather than making the retired claim.
_CORRECTING = re.compile(
    r"✗|⚠️|correct|retract|retired|imprecise|misattribut|earlier (draft|version)|used to read"
    r"|superseded|stale|we wrote|no source says|no source supports|asserted, not sourced|unsourced"
    r"|collapsed|not reproducible|round \w+ (fixed|removed|corrected)",
    re.I,
)

# form -> what replaced it, for the failure message.
RETIRED: dict[str, tuple[str, str]] = {
    r"38[–-]80\s*%": ("Karr et al. light-edit range",
                      "64-80% for Pangram and 38-49% for GPTZero — it collapses two detectors"),
    r"\b26\s+detectors": ("MGTEVAL detector count", "the authors' repo says 25+"),
    r"pure false-positive rate": ("Bohler's 8.6%",
                                  "mean detectable AI content per manuscript, which is not a rate"),
    r"on 190 students'": ("Hyatt's sample",
                          "the detectors saw a randomly selected 50 of 190 participants' essays"),
    r"above the GPTZero-derived": ("Goodman comparison",
                                   "an accuracy cannot be ranked against GPTZero's AUC"),
    r"low burstiness, regular sentence length": (
        "the autistic-writing trait list", "no source supports it; see round seventeen"),
    r"length-conditioned quantile": (
        "MCP's quantiles described as length-conditioned",
        "Tier B — the published abstract does not say this, so it must stay hedged"),
    r"nobody publishes what detectors": (
        "the H2L primacy claim", "false — Pratama ran exactly that experiment"),
    r"nobody ships the stratified audit": (
        "the stratified-audit primacy claim", "false — BAID is a bias-assessment benchmark"),
    r"nobody had connected": (
        "the stylistic-distance primacy claim",
        "false — Liang ran the intervention in both directions in 2023"),
    r"2[–-]8×": ("the semantic-diversity figure",
                 "misattributed to the TiCS review, whose abstract states no numbers"),
}

# A table row that merely *counts* how many papers make a claim is not making that claim. The
# ledger's census tables carry rows like `| humans cannot detect | 3 |`, and reading those as
# assertions would force the census to be reworded to satisfy a checker.
_COUNT_ROW = re.compile(r"^\|[^|]+\|\s*\d+\s*\|$")


def _offending_lines(pattern: str) -> list[str]:
    """Lines carrying a retired form with no correction marker nearby.

    The marker is looked for in a small window, not on the line alone: these documents hard-wrap at
    100 columns, so a "✗ An earlier draft said ..." sentence routinely puts the marker two lines
    above the number it is correcting. Checking the line in isolation reported every correction in
    the ledger as a violation.
    """
    rx = re.compile(pattern, re.I)
    bad = []
    for rel in DOCS:
        path = REPO / rel
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if not rx.search(line) or _COUNT_ROW.match(line.strip()):
                continue
            window = "\n".join(lines[max(0, i - 3): i + 4])
            if not _CORRECTING.search(window):
                bad.append(f"{rel}:{i + 1}: {line.strip()[:150]}")
    return bad


@pytest.mark.parametrize("pattern", sorted(RETIRED))
def test_a_retired_claim_appears_only_where_it_is_being_corrected(pattern):
    label, replacement = RETIRED[pattern]
    bad = _offending_lines(pattern)
    assert not bad, (
        f"{label}: this form was retracted and should read {replacement}. It appears on a line that "
        f"does not mark itself as a correction:\n" + "\n".join(bad)
    )


def test_the_check_can_actually_fire(tmp_path, monkeypatch):
    """Guards the guard: if `_CORRECTING` matched everything, every case above would pass forever."""
    line = "detectors flag light editing at 38–80% of the time"
    assert not _CORRECTING.search(line), "a plain restatement must not read as a correction"


def test_a_line_that_records_the_correction_is_allowed():
    """The ledger must be able to quote what it retracts, or it cannot document anything."""
    line = '✗ An earlier draft said "38–80%"; the paper splits it by detector.'
    assert _CORRECTING.search(line)


def test_a_census_row_counting_a_claim_is_not_making_it():
    """The suppression rule, pinned. `| humans cannot detect | 3 |` is the ledger counting how many
    papers assert something — reading it as an assertion would force the census to be reworded to
    satisfy a checker."""
    assert _COUNT_ROW.match("| humans cannot detect | 3 |")


def test_the_suppression_does_not_swallow_prose_or_data_rows():
    """A skip rule that is too broad hides real hits, which is worse than no rule at all."""
    assert not _COUNT_ROW.match("detectors flag light editing at 38-80% of the time")
    # A results row carrying a claim plus a non-integer measurement must still be read.
    assert not _COUNT_ROW.match("| humans cannot detect | 27.2% |")
    # Three columns is a findings table, not a claim count.
    assert not _COUNT_ROW.match("| humans cannot detect | 3 | source |")


# --- superseded measurements must not survive in source ------------------------------------------

# Figures this repository re-measured and replaced. Each maps to what it became, so a failure names
# the fix rather than only the fault. Historical references are allowed only where the surrounding
# text says the number is historical — see `_is_historical` below.
SUPERSEDED: tuple[tuple[str, str], ...] = (
    ("15.8%", "20.5% — re-measured in round 31 on the restored pre-LLM corpus"),
    ("26.7%", "30.0% at <=50 words — re-measured in round 31"),
    ("15.6%", "21.7% at 50-100 words — re-measured in round 31"),
)


def _is_historical(line: str) -> bool:
    """A line allowed to quote a superseded figure because it is describing the correction."""
    markers = ("round 31", "round thirty-one", "was published", "used to", "no longer",
               "could not be reproduced", "most-quoted", "which `ROADMAP.md` called")
    return any(m in line.lower() for m in markers)


@pytest.mark.parametrize("stale,replacement", SUPERSEDED, ids=[s for s, _ in SUPERSEDED])
def test_no_source_file_still_quotes_a_superseded_measurement(stale, replacement):
    """`untell-audit` scans documents. Nothing scanned source, so `untell/calibrate.py` justified its
    per-band thresholds with '26.7% at 50 words or fewer' for seven rounds after that number was
    replaced. A stale figure in a docstring is worse than one in a document: it is the stated reason
    a shipped default is what it is."""
    offenders = []
    for rel in CODE:
        for i, line in enumerate((REPO / rel).read_text(encoding="utf-8").splitlines(), 1):
            if stale in line and not _is_historical(line):
                offenders.append(f"{rel}:{i}: {line.strip()[:90]}")
    assert not offenders, (
        f"superseded figure {stale} still stated as current — it is now {replacement}:\n"
        + "\n".join(offenders)
    )


def test_the_historical_exemption_cannot_swallow_everything():
    """Guards the guard. If `_is_historical` matched ordinary lines, the check above would pass on a
    genuinely stale docstring."""
    assert not _is_historical("This repo measured 26.7% false positives at 50 words or fewer.")
    assert _is_historical("the number published before round 31 was 15.8%")
