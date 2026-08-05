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
