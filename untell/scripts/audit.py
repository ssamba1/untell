"""``untell-audit`` — re-check every documented claim that CAN be re-checked, and say how many cannot.

The competitive argument this repo makes is *correctness*, not evasion strength, and a correctness
argument decays the moment a number in a document stops matching the code. That has already
happened here repeatedly: a detector-count claim no two documents agreed on, a competitive quote
attributed to a sentence present in no commit, a per-category table that drifted 969 -> 1014 while
the prose still said 969.

Claims split into two kinds and only one of them belongs in CI:

**Derivable** — determined by the repository as it stands: how many detectors are registered, which
rewriters resolve, what a constant is set to, how many tests exist. These are checked here, and a
drift is a failure.

**Measured** — produced by running a corpus through the stack. Re-deriving one needs a download and
minutes of compute, so it cannot run in CI, and pretending otherwise would make the audit slow and
flaky rather than trustworthy. What IS enforced is that such a number is never unattributable: the
document has to say what produced it.

The command therefore reports three totals — checked, unverifiable-but-attributed, and
**unattributed** — and fails on the last. An audit that claimed 100% coverage would be the same
kind of lie it exists to catch.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

# Documents that describe the CURRENT build. Dated artefacts are excluded on purpose: a changelog
# entry or a measurement log records what was true when it was written, and "fixing" those to match
# today's code would destroy the record rather than repair anything.
LIVE_DOCS = ("README.md", "ROADMAP.md", "docs/why-best-open-repo.md", "docs/index.md")

# A measured number is attributed when its section says how to reproduce it. These are the phrases
# the documents actually use.
_ATTRIBUTION = re.compile(
    # Our own measurements.
    r"MEASURED|Measured|measured|Reproduce:|reproduce with|`untell-ceiling|`untell-prove"
    r"|free-ceiling-measured|Result \d+|n\s*=\s*\d+"
    # The census, which is itself a documented method with raw data attached.
    r"|census|humanizer-census"
    # A citation is provenance: an external claim is attributed when it names its source.
    r"|arXiv|arxiv\.org|doi\.org|https?://|\]\(",
)


@dataclass
class Finding:
    name: str
    ok: bool
    detail: str


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    attributed: int = 0
    unattributed: list[str] = field(default_factory=list)

    @property
    def failures(self) -> list[Finding]:
        return [f for f in self.findings if not f.ok]

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.findings.append(Finding(name, bool(ok), detail))


# ---------------------------------------------------------------------------
# Derivable claims
# ---------------------------------------------------------------------------

def _detector_counts() -> tuple[int, int]:
    from untell.detectors.base import all_detectors

    # `tier == "commercial"`, not a `commercial` attribute — the first version of this used
    # getattr(d, "commercial", False), which is False for every adapter and reported 15/0. A count
    # that is silently always-zero is precisely the defect this command exists to catch, so it is
    # taken from the same expression tests/test_docs_claims.py uses.
    dets = all_detectors()
    commercial = sum(1 for d in dets if d.tier == "commercial")
    return len(dets) - commercial, commercial


def check_derivable(report: Report) -> None:
    """Everything the repository determines about itself."""
    # --- the registries the docs quote sizes for -------------------------------------------------
    local, commercial = _detector_counts()
    report.check(
        "the detector registry has both kinds",
        local > 0 and commercial > 0,
        f"{local} local, {commercial} commercial",
    )
    # Every document that states the ensemble size must agree with the registry.
    for rel in LIVE_DOCS:
        doc = REPO / rel
        if not doc.exists():
            continue
        body = doc.read_text(encoding="utf-8")
        for pattern, expected, kind in (
            (r"(\d+)\s+local", local, "local"),
            (r"(\d+)\s+commercial", commercial, "commercial"),
        ):
            for found in re.findall(pattern, body):
                report.check(
                    f"{rel}: '{found} {kind}' matches the registry",
                    int(found) == expected,
                    f"registry has {expected}",
                )

    from untell.rewriter import get_rewriter

    names = ["structural", "surgical", "composite", "targeted", "neural", "ensemble", "max"]
    missing = [n for n in names if get_rewriter(n) is None]
    report.check("every documented rewriter resolves", not missing, f"missing: {missing}")

    # `max` is an alias of `ensemble`; a benchmark listing both reports one method twice.
    report.check(
        "max is an alias of ensemble",
        type(get_rewriter("max")) is type(get_rewriter("ensemble")),
        "same implementation",
    )

    # --- console scripts the README promises -----------------------------------------------------
    # Scoped to the [project.scripts] TABLE, not the whole file. A bare `^untell\s*=` also matches
    # the package name in [project], so the naive pattern counted 23 where there are 22 — an
    # off-by-one in the direction of overstating what the tool ships.
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    scripts_table = pyproject.split("[project.scripts]", 1)[-1].split("\n[", 1)[0]
    declared = set(re.findall(r"^([\w-]+)\s*=", scripts_table, re.MULTILINE))
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    promised = set(re.findall(r"`(untell-[\w-]+)`", readme))
    absent = sorted(promised - declared)
    report.check(
        "every console script the README names is declared",
        not absent,
        f"promised but undeclared: {absent}" if absent else f"{len(declared)} declared",
    )

    # --- calibration constants the docs quote ----------------------------------------------------
    from untell.scripts.score import _STDLIB_PERPLEXITY_VERDICT_THRESHOLD, DEFAULT_THRESHOLD

    report.check(
        "the verdict threshold is above the loop target",
        _STDLIB_PERPLEXITY_VERDICT_THRESHOLD > DEFAULT_THRESHOLD,
        f"verdict {_STDLIB_PERPLEXITY_VERDICT_THRESHOLD} > loop {DEFAULT_THRESHOLD}",
    )

    from untell.rewriter.structural import _MERGE_CONNECTORS, _MERGE_WEIGHTS, _NEUTRAL

    report.check(
        "merge connectors and weights line up",
        len(_MERGE_CONNECTORS) == len(_MERGE_WEIGHTS)
        and abs(sum(_MERGE_WEIGHTS) - 1.0) < 0.01,
        f"{len(_MERGE_CONNECTORS)} connectors, weights sum {sum(_MERGE_WEIGHTS):.3f}",
    )
    report.check(
        "the neutral burstiness target is unchanged",
        _NEUTRAL["burstiness"] == 0.45,
        "every prior measurement was taken against 0.45",
    )

    # --- census figures quoted outside the census ------------------------------------------------
    # The README said "1124 candidate repos" while the census said 1287. Both were written by the
    # same person days apart; nothing compared them.
    census = REPO / "docs" / "humanizer-census.md"
    if census.exists():
        head = census.read_text(encoding="utf-8")
        m = re.search(r"(\d{3,5})\s+candidate repos", head)
        n = re.search(r"(\d{3,4})\s+repos found,\s*(\d{3,4})\s+read", head)
        truth = {}
        if m:
            truth["candidates"] = int(m.group(1))
        if n:
            truth["candidates"] = int(n.group(1))
            truth["read"] = int(n.group(2))
        for rel in LIVE_DOCS:
            doc = REPO / rel
            if not doc.exists():
                continue
            body = doc.read_text(encoding="utf-8")
            if "candidates" in truth:
                for found in re.findall(r"(\d{3,5})\s+candidate repos", body):
                    report.check(
                        f"{rel}: '{found} candidate repos' matches the census",
                        int(found) == truth["candidates"],
                        f"census says {truth['candidates']}",
                    )
            if "read" in truth:
                for found in re.findall(r"(\d{3,4})\s+(?:of \d+ )?(?:repos )?read", body):
                    report.check(
                        f"{rel}: '{found} read' matches the census",
                        int(found) == truth["read"],
                        f"census says {truth['read']}",
                    )

    # --- links that documents make to each other -------------------------------------------------
    broken: list[str] = []
    for rel in LIVE_DOCS:
        doc = REPO / rel
        if not doc.exists():
            continue
        for target in re.findall(r"\]\(([^)#][^)]*\.md)[^)]*\)", doc.read_text(encoding="utf-8")):
            if target.startswith("http"):
                continue
            resolved = (doc.parent / target).resolve()
            if not resolved.exists():
                broken.append(f"{rel} -> {target}")
    report.check("no live document links to a missing file", not broken, f"broken: {broken}")


# ---------------------------------------------------------------------------
# Measured claims: every number must at least say where it came from
# ---------------------------------------------------------------------------

_BOLD_NUMBER = re.compile(r"\*\*([^*\n]{0,80}?\d[^*\n]{0,80}?)\*\*")


def check_attribution(report: Report) -> None:
    """A measured number with no stated provenance is the failure this repo has already shipped."""
    for rel in LIVE_DOCS:
        doc = REPO / rel
        if not doc.exists():
            continue
        lines = doc.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            for m in _BOLD_NUMBER.finditer(line):
                claim = m.group(1).strip()
                # Percentages, scores and counts are claims; version strings and dates are not.
                # Not every bolded string containing a digit is a measurement. A link, a date and
                # a version are claims about nothing that could drift under us.
                if re.fullmatch(r"[\d.]+", claim) or "](" in claim or "http" in claim:
                    continue
                if re.fullmatch(r"[A-Za-z, ]*\d{4}-\d{2}-\d{2}[.A-Za-z, ]*", claim):
                    continue
                # Attribution may sit in the surrounding paragraph, not the same line.
                window = "\n".join(lines[max(0, i - 12): i + 13])
                if _ATTRIBUTION.search(window):
                    report.attributed += 1
                else:
                    report.unattributed.append(f"{rel}:{i + 1}: {claim}")


def run() -> Report:
    report = Report()
    check_derivable(report)
    check_attribution(report)
    return report


def _render(report: Report, as_json: bool) -> str:
    if as_json:
        return json.dumps(
            {
                "checks": [{"name": f.name, "ok": f.ok, "detail": f.detail} for f in report.findings],
                "attributed_claims": report.attributed,
                "unattributed_claims": report.unattributed,
                "ok": not report.failures and not report.unattributed,
            },
            indent=2,
        )
    out = ["Derivable claims — re-checked against the code as it stands:"]
    for f in report.findings:
        out.append(f"  {'PASS' if f.ok else 'FAIL'}  {f.name}" + (f"  ({f.detail})" if f.detail else ""))
    out.append("")
    out.append(
        "Measured claims — cannot run in CI, so provenance is what is enforced:"
    )
    out.append(f"  {report.attributed} numeric claims carry a stated source")
    if report.unattributed:
        out.append(f"  {len(report.unattributed)} do NOT:")
        for u in report.unattributed:
            out.append(f"    {u}")
    else:
        out.append("  0 unattributed")
    out.append("")
    out.append("OK" if not report.failures and not report.unattributed else "FAILED")
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="untell-audit",
        description=(
            "Re-check documented claims. Derivable ones are verified against the code; measured "
            "ones cannot run in CI, so what is enforced is that each states its source."
        ),
    )
    p.add_argument("--json", action="store_true", help="machine-readable output")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run()
    print(_render(report, args.json))
    return 0 if (not report.failures and not report.unattributed) else 1


if __name__ == "__main__":
    sys.exit(main())
