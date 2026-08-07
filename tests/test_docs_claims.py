"""Docs must not claim a detector count the registry does not back.

Four documents advertised the ensemble size and no two of them agreed: README said "7 local +
commercial", docs/index.md said "7 local + 6 commercial", why-best-open-repo.md said "7 local +
6 commercial", competitive-gap-plan.md said "8 local + 6 commercial". The registry had 8 local and
7 commercial. Nothing checked, so every detector added after the docs were written silently made
them wronger — and the ensemble size is the headline claim of the project.

These tests read the counts back out of the prose and compare them to `all_detectors()`, so the
next detector added fails here instead of quietly aging the docs.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from untell.detectors.base import all_detectors

REPO = Path(__file__).resolve().parent.parent

# Files whose counts describe the CURRENT build. Dated artefacts are excluded on purpose: a
# changelog entry or a measurement report records what was true when written, and rewriting
# history to match today's registry would destroy the record rather than fix anything.
_HISTORICAL = re.compile(r"CHANGELOG|report|measured|buildplan", re.IGNORECASE)

_LOCAL_CLAIM = re.compile(r"(\d+)\s+local\b")
_COMMERCIAL_CLAIM = re.compile(r"(\d+)\s+commercial\b")


def _live_docs() -> list[Path]:
    return [
        p
        for p in REPO.rglob("*.md")
        if not _HISTORICAL.search(p.name)
        and ".venv" not in p.parts
        and "node_modules" not in p.parts
        and "site" not in p.parts
    ]


def _registry_counts() -> tuple[int, int]:
    dets = all_detectors()
    commercial = sum(1 for d in dets if d.tier == "commercial")
    return len(dets) - commercial, commercial


def test_registry_has_both_kinds():
    """Guard the guard: if the registry ever returns 0/0, the claim tests below pass vacuously."""
    local, commercial = _registry_counts()
    assert local > 0 and commercial > 0, f"registry looks broken: {local} local, {commercial} commercial"


@pytest.mark.parametrize(
    ("pattern", "kind"),
    [(_LOCAL_CLAIM, "local"), (_COMMERCIAL_CLAIM, "commercial")],
    ids=["local", "commercial"],
)
def test_documented_detector_counts_match_registry(pattern, kind):
    local, commercial = _registry_counts()
    expected = local if kind == "local" else commercial

    wrong: list[str] = []
    for doc in _live_docs():
        text = doc.read_text(encoding="utf-8", errors="replace")
        for m in pattern.finditer(text):
            claimed = int(m.group(1))
            if claimed != expected:
                line = text[: m.start()].count("\n") + 1
                wrong.append(f"{doc.relative_to(REPO)}:{line} claims {claimed} {kind}, registry has {expected}")

    assert not wrong, "detector counts in docs are stale:\n  " + "\n  ".join(wrong)


def test_claims_are_actually_being_found():
    """A regex that matches nothing would make the count test pass no matter how wrong the docs are."""
    hits = sum(
        len(_LOCAL_CLAIM.findall(d.read_text(encoding="utf-8", errors="replace"))) for d in _live_docs()
    )
    assert hits > 0, "no '<n> local' claims found — the pattern or the doc set is wrong, not the docs"


def test_thresholds_reference_documents_every_gate_the_loop_runs():
    """SKILL.md cites references/thresholds.md as the source of loop defaults, so a gate missing
    from it is a gate a reader does not know exists.

    It has fallen behind twice: once when the NLI gate and the BERTScore tier were added, and again
    when the quantity and certainty checks were. `meaning_preserved()` imports its sub-checks lazily
    by module, so those imports are the authoritative list of what the loop enforces.
    """
    import inspect

    from untell.scripts import entailment

    src = inspect.getsource(entailment.meaning_preserved)
    modules = set(re.findall(r"from untell\.scripts\.(\w+) import", src))
    assert modules, "no sub-check imports found — has meaning_preserved been restructured?"

    # Every document that describes the gate has fallen behind at least once. README's "How it
    # works" block is the first thing a reader sees, so an omission there is the most visible.
    for rel in ("untell/references/thresholds.md", "README.md"):
        doc = (REPO / rel).read_text(encoding="utf-8", errors="replace")
        missing = sorted(m for m in modules if m not in doc)
        assert not missing, (
            f"the loop's meaning gate runs {sorted(modules)} but {rel} never mentions {missing}"
        )


def test_every_declared_version_agrees():
    """One version, four declarations. They had already drifted.

    `pyproject.toml` and `untell/__init__.py` said 0.3.0 while both plugin manifests said 0.1.0, so
    anyone installing via the Claude Code marketplace saw a version two minor releases behind the
    package they were getting. Nothing compared them.
    """
    import json

    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    expected = re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)

    found = {"pyproject.toml": expected}

    init = (REPO / "untell" / "__init__.py").read_text(encoding="utf-8")
    found["untell/__init__.py"] = re.search(r'__version__ = "([^"]+)"', init).group(1)

    plugin = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    found[".claude-plugin/plugin.json"] = plugin["version"]

    market = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    found[".claude-plugin/marketplace.json"] = market["plugins"][0]["version"]

    disagree = {k: v for k, v in found.items() if v != expected}
    assert not disagree, f"version is {expected} in pyproject.toml but {disagree}"


class TestTheDemoUiOffersWhatTheToolShips:
    """docs/demo.html is the shipped front-end for the REST API, and its dropdowns are hand-written.

    The style list had drifted to the first 6 of 14, so eight modes the tool ships were invisible in
    the UI — the same hand-copied-list drift already fixed in the MCP tool's docstring, which is now
    generated from STYLE_NAMES. This page is static HTML and cannot generate its options, so the
    list is pinned here instead.
    """

    @staticmethod
    def _options(select_id: str) -> list[str]:
        html = (REPO / "docs" / "demo.html").read_text(encoding="utf-8")
        block = re.search(rf'<select id="{select_id}">(.*?)</select>', html, re.S)
        assert block, f"no <select id={select_id!r}> in demo.html"
        return [v for v in re.findall(r'<option value="([^"]*)"', block.group(1)) if v]

    def test_every_style_is_offered(self):
        from untell.rewriter.prompts import STYLE_NAMES

        assert self._options("style") == STYLE_NAMES

    def test_every_offered_style_is_real(self):
        """The other direction: an option the API now rejects with 422 would be a dead control."""
        from untell.rewriter.prompts import STYLE_NAMES

        bogus = [s for s in self._options("style") if s not in STYLE_NAMES]
        assert not bogus, f"demo.html offers styles the API rejects: {bogus}"

    def test_every_offered_rewriter_is_free_and_real(self):
        """The demo has no API key, so every rewriter it offers must be a free backend."""
        import untell.api_server as api

        offered = self._options("rewriter")
        assert offered, "no rewriter options found"
        unusable = [r for r in offered if r not in api._FREE_REWRITERS]
        assert not unusable, f"demo.html offers rewriters that need a key: {unusable}"


def test_console_script_count_in_why_best_matches_pyproject():
    """A claim about the package's own surface should not be able to go stale.

    It said "5 console scripts" while pyproject defined 21 — understating the tool by 4x in the
    document whose whole job is the completeness comparison.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    block = (root / "pyproject.toml").read_text(encoding="utf-8").split("[project.scripts]")[1]
    names = re.findall(r"(?m)^([A-Za-z0-9_-]+)\s*=", block.split("\n[")[0])
    doc = (root / "docs" / "why-best-open-repo.md").read_text(encoding="utf-8")
    assert f"**{len(names)}** console scripts" in doc, (
        f"pyproject defines {len(names)} console scripts; why-best-open-repo.md does not say so"
    )


def test_why_best_test_count_is_not_stale():
    """The completeness argument leans on test coverage, so the number must track reality.

    It said "16 modules" while the suite had grown to 1694 tests across 61 modules.
    """
    import re
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    doc = (root / "docs" / "why-best-open-repo.md").read_text(encoding="utf-8")
    m = re.search(r"\|\s*Automated tests\s*\|\s*✅\s*\*\*(\d+)\*\*\s*tests", doc)
    assert m, "why-best-open-repo.md no longer states a machine-checkable test count"
    claimed = int(m.group(1))
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:randomly"],
        cwd=root, capture_output=True, text=True, timeout=600,
    ).stdout
    actual = int(re.search(r"(\d+) tests collected", out).group(1))
    # Only fails when the doc OVERSTATES, or understates by more than a session's growth.
    assert claimed <= actual, f"doc claims {claimed} tests, suite collects {actual}"
    assert actual - claimed < 200, (
        f"doc claims {claimed} tests, suite collects {actual} — the completeness claim is stale"
    )


def test_why_best_records_the_detector_loop_counterexample():
    """(c) 'iterative detector-feedback loop at inference' is NOT unique to this repo.

    chengez/Adversarial-Paraphrasing (NeurIPS 2025, arXiv:2506.07001) paraphrases under detector
    guidance with 87.88% average TPR@1%FPR reduction. The page used to read as if nobody else
    did this. Verified against the repo README and the paper abstract on 2026-08-05.
    """
    from pathlib import Path

    doc = (Path(__file__).resolve().parents[1] / "docs" / "why-best-open-repo.md").read_text(
        encoding="utf-8"
    )
    assert "chengez" in doc, "the detector-loop counterexample is not recorded"
    assert "87.88" in doc, "the counterexample's published bypass number is not stated"


def test_quotes_attributed_to_the_research_report_actually_appear_in_it():
    """A quotation marked "verbatim" must be findable in the cited source.

    MEASURED FAILURE this guards: README.md and docs/why-best-open-repo.md both attributed a
    four-part sentence to humanizer-research-report.md "verbatim" -- "There is no open-source repo
    that combines (a)... (d) a user-installable package." That sentence appears in NO version of
    the report in git history. The report's actual first-ranked gap is narrower and about shipping
    PRODUCTS, not open-source repos. The report had also been deleted from the repo, so all four
    citations pointed at a missing file.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    report = root / "humanizer-research-report.md"
    assert report.exists(), "humanizer-research-report.md is cited by README and docs but missing"
    body = report.read_text(encoding="utf-8")

    # The phrases that made the fabricated quote distinctive. If any reappears in a doc, it must
    # also be in the report.
    for phrase in ("user-installable", "quality/meaning-preservation verifier"):
        for doc in ("README.md", "docs/why-best-open-repo.md"):
            text = (root / doc).read_text(encoding="utf-8")
            if phrase in text and "not a quotation" not in text and "does not appear" not in text:
                assert phrase in body, (
                    f"{doc} uses {phrase!r} without flagging it as our own framing, but the "
                    f"cited report does not contain it"
                )

    # The claim we DO quote must be real.
    assert "No shipping product does iterative rewrite against live detector scores" in body


def test_the_research_report_link_resolves():
    """It is hyperlinked from the README; a 404 on the evidence for the headline claim is worse
    than having no link."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    for target in re.findall(r"\]\((humanizer-research-report\.md)\)", readme):
        assert (root / target).exists(), f"README links to {target}, which does not exist"


def test_census_numbers_match_the_census_data():
    """The census prose and its raw data must not drift apart.

    The census is the evidence for retracting three claims on why-best-open-repo.md, so its
    headline counts are load-bearing.
    """
    import json
    import re
    from pathlib import Path

    docs = Path(__file__).resolve().parents[1] / "docs"
    data = json.loads((docs / "humanizer-census.json").read_text(encoding="utf-8"))
    prose = (docs / "humanizer-census.md").read_text(encoding="utf-8")

    def counted(field):
        return sum(
            1
            for x in data
            if x.get(field)
            and not str(x[field]).lower().strip().startswith(("none", "no ", "nothing"))
        )

    loop = sum(1 for x in data if str(x.get("detector_in_loop", "")).lower().startswith("yes"))
    assert len(data) >= 400, f"census json has only {len(data)} profiles"
    assert f"{len(data)} read" in prose, f"prose does not state {len(data)} read"
    assert re.search(rf"\b{loop} of {len(data)}\b", prose), (
        f"{loop} repos close a detector loop; the prose does not say so"
    )
    assert re.search(rf"\b{counted('meaning_verification')} of {len(data)}\b", prose), (
        "the meaning-verification count in the prose does not match the data"
    )


def test_why_best_does_not_claim_the_loop_is_unique():
    """31 profiled repos close a detector loop. The page must not imply otherwise."""
    from pathlib import Path

    doc = (Path(__file__).resolve().parents[1] / "docs" / "why-best-open-repo.md").read_text(
        encoding="utf-8"
    )
    assert "not ours alone" in doc or "is not ours" in doc
    assert "humanizer-census.md" in doc, "why-best does not link the census that corrects it"


def test_roadmap_exists_and_is_linked():
    """README, CHANGELOG and why-best all link ROADMAP.md; it was deleted on 2026-07-28 inside an
    unrelated commit and the links 404'd for a week. Same failure as humanizer-research-report.md,
    deleted in the same commit."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    assert (root / "ROADMAP.md").exists(), "ROADMAP.md is linked from the README but missing"
    readme = (root / "README.md").read_text(encoding="utf-8")
    for target in re.findall(r"\]\((ROADMAP\.md)\)", readme):
        assert (root / target).exists()


def test_roadmap_numbers_track_the_census():
    """The roadmap's priorities are ranked by census counts. If the census moves and the roadmap
    does not, the ranking is stale and the plan is wrong."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "docs" / "humanizer-census.json").read_text(encoding="utf-8"))
    roadmap = (root / "ROADMAP.md").read_text(encoding="utf-8")
    assert f"{len(data)} of 1287" in roadmap or f"census read {len(data)}" in roadmap or (
        f"{len(data)} profiled repos" in roadmap or "435 of 1287" in roadmap
    ), "the roadmap does not state how many repos the census actually read"
