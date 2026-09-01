"""A ✅ "read at source" marker must not sit on a source this environment cannot read.

The research documents grade every claim by how far it was verified: ✅ means the abstract was read
at its source, not inferred from a search result or a secondary description. That grade is only
meaningful if it cannot be applied to something unreadable — and in the environment these documents
were compiled in, `arxiv.org` is blocked by egress policy while the ACL Anthology (via its GitHub
repository), PubMed/PMC and github.com are reachable.

So a ✅ on a line whose only identifier is an arXiv preprint is a contradiction: it claims a
verification that could not have happened. That is not hypothetical — Beemo carried
`arXiv:2411.04032` with a ✅ in two documents while the ledger cited the same paper as
`2025.naacl-long.357`, the Anthology version that actually was read. One paper, two identifiers, and
the ✅ pointing at the unreadable one.

This test does not judge whether a claim is *true*. It judges whether the document is entitled to
say it was checked.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

RESEARCH_DOCS = (
    "ROADMAP.md",
    "ai-writing-research.md",
    "docs/research-to-build.md",
    "docs/research-verification.md",
    "docs/strategy-options.md",
)

# Both spellings that appear in these documents: a linked abstract and a bare identifier.
_ARXIV = re.compile(r"arxiv\.org/abs/\d{4}\.\d{4,5}|arXiv:\d{4}\.\d{4,5}")

# Hosts and identifiers this environment can actually resolve. The Anthology is reachable because
# its XML lives in a GitHub repository; PubMed and PMC through the MCP server; DOIs because the
# PubMed records carry them.
_REACHABLE = re.compile(r"aclanthology\.org|doi\.org|PMID|PMC\d|github\.com")

_VERIFIED = "✅"


def _violations(text: str, rel: str) -> list[str]:
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if _VERIFIED in line and _ARXIV.search(line) and not _REACHABLE.search(line):
            out.append(f"{rel}:{i}: {line.strip()[:160]}")
    return out


@pytest.mark.parametrize("rel", RESEARCH_DOCS)
def test_no_verified_claim_rests_on_an_unreachable_preprint(rel):
    doc = REPO / rel
    if not doc.exists():
        pytest.skip(f"{rel} not present")
    bad = _violations(doc.read_text(encoding="utf-8"), rel)
    assert not bad, (
        "a ✅ read-at-source marker sits on an arXiv-only citation, which this environment cannot "
        "read. Either cite the venue version (the Anthology, a DOI, a PMID, or the authors' "
        "repository) or drop the ✅ to the tier the claim was actually checked to:\n"
        + "\n".join(bad)
    )


def test_the_check_can_actually_fire():
    """Guards the guard. A regex that matched nothing would pass the test above forever."""
    fabricated = "- ✅ **Some Paper** ([arXiv:2411.04032](https://arxiv.org/abs/2411.04032)) says X"
    assert _violations(fabricated, "fake.md"), "the invariant cannot detect its own violation"


def test_a_venue_citation_alongside_the_preprint_is_accepted():
    """The convention these documents settled on: name the venue, keep the preprint id for
    traceability. That must not be flagged."""
    ok = ("- ✅ **Beemo** ([2025.naacl-long.357](https://aclanthology.org/2025.naacl-long.357/), "
          "formerly arXiv:2411.04032) reports 33 detector configurations")
    assert not _violations(ok, "fake.md")


def test_the_arxiv_format_example_is_not_treated_as_a_citation():
    """`arXiv:2301.00000` is a format example in `untell/scripts/preserve.py` — it illustrates the
    identifier shape the citation-locking regex is tested against. An ad-hoc extractor written
    during this research reported it as an unresolvable citation, which is a false alarm about a
    string that was never a reference. The shipped extractor reads Anthology ids only, so it is
    unaffected; this pins that, so a future arXiv-aware extractor inherits the exclusion.
    """
    from eval.litreview import cited_acl_ids

    preserve = (REPO / "untell" / "scripts" / "preserve.py").read_text(encoding="utf-8")
    assert "2301.00000" in preserve, "the fixture this test describes has moved"
    assert not any("2301.00000" in c for c in cited_acl_ids(REPO)), (
        "the format example must never be collected as a real citation"
    )


@pytest.mark.parametrize("rel", RESEARCH_DOCS)
def test_every_arxiv_identifier_is_well_formed(rel):
    """A malformed id cannot be resolved by anyone later, and is indistinguishable from a typo in a
    real one."""
    doc = REPO / rel
    if not doc.exists():
        pytest.skip(f"{rel} not present")
    text = doc.read_text(encoding="utf-8")
    malformed = re.findall(r"arXiv:(?!\d{4}\.\d{4,5})(\S+)", text)
    assert not malformed, f"{rel}: not arXiv identifiers: {malformed}"
