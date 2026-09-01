"""A citation that does not resolve looks like evidence and is not.

This repo refuses to publish an unattributed number. A fabricated or mistyped *attribution* is the
same failure one level down, and nothing checked for it until the research documents started citing
dozens of papers.

`eval.litreview.verify_citations` resolves every ACL Anthology id the repo cites against the real
corpus. These tests pin the extraction (which is what would silently break) and skip the resolution
itself when the corpus is not cached, because it is a 181 MB download.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from eval.litreview import cited_acl_ids, paper_index, verify_citations

REPO = Path(__file__).resolve().parent.parent


def test_the_repo_cites_anthology_papers_at_all():
    """Guards the guard: an extraction regex that matched nothing would make the resolution check
    vacuously green while every citation went unverified."""
    cited = cited_acl_ids(REPO)
    assert len(cited) >= 30, f"only found {len(cited)} citations — extraction is probably broken"


def test_every_citation_records_where_it_came_from():
    for cid, files in cited_acl_ids(REPO).items():
        assert files, f"{cid} has no source file recorded"


def test_extraction_finds_ids_in_both_markdown_and_python(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "untell").mkdir()
    (tmp_path / "eval").mkdir()
    (tmp_path / "a.md").write_text("see https://aclanthology.org/2025.acl-long.601/ ok", "utf-8")
    (tmp_path / "untell" / "m.py").write_text(
        '"""ref https://aclanthology.org/2024.acl-long.674/ """', "utf-8")
    found = cited_acl_ids(tmp_path)
    assert set(found) == {"2025.acl-long.601", "2024.acl-long.674"}


def test_a_bad_id_is_reported_as_unresolved(tmp_path):
    """The failure this exists to catch: a plausible-looking id that is not a paper."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "untell").mkdir()
    (tmp_path / "eval").mkdir()
    (tmp_path / "a.md").write_text("https://aclanthology.org/2025.acl-long.99999/", "utf-8")
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "v.xml").write_text(
        "<collection id='2025.acl'><volume id='long'><paper id='601'>"
        "<title>Real</title><abstract>x</abstract></paper></volume></collection>", "utf-8")
    report = verify_citations(tmp_path, cache)
    assert "2025.acl-long.99999" in report["unresolved"]


@pytest.mark.skipif(not os.environ.get("UNTELL_ANTHOLOGY_CACHE"),
                    reason="set UNTELL_ANTHOLOGY_CACHE to the volume dir to resolve for real")
def test_every_cited_paper_resolves_against_the_real_corpus():
    cache = Path(os.environ["UNTELL_ANTHOLOGY_CACHE"])
    report = verify_citations(REPO, cache)
    assert not report["unresolved"], (
        f"{len(report['unresolved'])} citation(s) do not resolve: "
        f"{sorted(report['unresolved'])[:5]}")


def test_paper_index_reads_titles(tmp_path):
    (tmp_path / "v.xml").write_text(
        "<collection id='2025.acl'><volume id='long'><paper id='1'>"
        "<title>A <fixed-case>T</fixed-case>itle</title></paper></volume></collection>", "utf-8")
    assert paper_index(tmp_path)["2025.acl-long.1"] == "A Title"
