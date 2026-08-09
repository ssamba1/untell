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
    # No backtick before the command names: the first version required one, and the README quotes
    # its reproduction command BARE inside a fenced block, so a number with the command sitting
    # three lines above it was reported unattributed. A checker that cannot recognise the most
    # common form of the thing it looks for produces false alarms, and false alarms are how a
    # checker gets ignored.
    r"MEASURED|Measured|measured|Reproduce:|reproduce with|untell-ceiling|untell-prove"
    r"|untell-audit|free-ceiling-measured|Result \d+|n\s*=\s*\d+"
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

    # --- every declared entry point must actually import and expose its callable -----------------
    # A broken one is "command not found" or an ImportError on a user's very first command, which
    # is the worst possible first impression and is invisible to a test suite that imports modules
    # directly. This resolves them the way pip does. `untell-humanize` already shipped once as a
    # promise the entry-point table did not keep.
    import importlib

    broken_entries: list[str] = []
    for name, module, func in re.findall(
        r"^([\w-]+)\s*=\s*\"([\w.]+):(\w+)\"", scripts_table, re.MULTILINE
    ):
        try:
            mod = importlib.import_module(module)
            if not callable(getattr(mod, func, None)):
                broken_entries.append(f"{name} -> {module}:{func} is not callable")
        except Exception as exc:  # noqa: BLE001 - any import failure is a broken command
            broken_entries.append(f"{name} -> {type(exc).__name__}: {str(exc)[:60]}")
    report.check(
        "every declared console script resolves",
        not broken_entries,
        f"broken: {broken_entries}" if broken_entries else f"{len(declared)} resolve",
    )

    # --- every CLI flag the README shows must exist ------------------------------------------------
    # Read from the module SOURCE, not by running `--help`. The subprocess approach looks obvious
    # and has a silent failure mode that manufactures false alarms: the console scripts are not
    # necessarily on PATH, `subprocess.run` then raises, and an `except` that yields empty help text
    # makes EVERY flag look missing. A checker whose failure mode is "everything is broken" gets
    # ignored, which is worse than not having it.
    entry_modules: dict[str, str] = dict(
        re.findall(r"^([\w-]+)\s*=\s*\"([\w.]+):\w+\"", scripts_table, re.MULTILINE)
    )
    documented: set[tuple[str, str]] = set()
    for block in re.findall(r"```(?:bash|sh|console)\n(.*?)```", readme, re.DOTALL):
        for line in block.splitlines():
            head = line.split("#")[0].strip()
            m = re.match(r"(?:\w+=\S+\s+)*(untell[\w-]*)\s+(.*)", head)
            if not m or m.group(1) not in entry_modules:
                continue
            for flag in re.findall(r"(--[a-z][a-z0-9-]*)", m.group(2)):
                documented.add((m.group(1), flag))

    # Loaded up front, not lazily. The dispatcher's fallback below searches every entry module, and
    # with a lazy cache that search saw only the modules visited SO FAR — so `untell --best-of`
    # passed or failed depending on alphabetical order. An order-dependent check is a coin flip
    # wearing a checkmark.
    source_cache: dict[str, str] = {}
    for module in set(entry_modules.values()):
        path = REPO / Path(*module.split(".")).with_suffix(".py")
        source_cache[module] = path.read_text(encoding="utf-8") if path.exists() else ""

    unknown_flags: list[str] = []
    for command, flag in sorted(documented):
        module = entry_modules[command]
        body = source_cache[module]
        if not body:
            unknown_flags.append(f"{command}: source for {module} not found")
        elif flag not in body:
            # The dispatcher delegates, so a subcommand's flag lives in the module it dispatches to.
            if command == "untell" and any(flag in s for s in source_cache.values()):
                continue
            unknown_flags.append(f"{command} {flag}")
    report.check(
        "every CLI flag the README shows exists",
        not unknown_flags,
        f"unknown: {unknown_flags[:5]}" if unknown_flags else f"{len(documented)} pairs checked",
    )

    # --- every environment variable the code reads must be documented ----------------------------
    # Sixteen of the twenty were undocumented, including the REST server's auth key and two
    # switches that DISABLE a meaning gate. Configuration that exists but cannot be discovered is
    # a feature nobody can use and a guarantee nobody knows they have turned off.
    read_vars: set[str] = set()
    for folder in ("untell", "eval", "training"):
        base = REPO / folder
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            read_vars |= set(re.findall(r"\b(UNTELL_[A-Z0-9_]+)\b", path.read_text(encoding="utf-8")))
    undocumented = sorted(v for v in read_vars if v not in readme)
    report.check(
        "every UNTELL_* variable the code reads is documented",
        not undocumented,
        f"undocumented: {undocumented[:6]}" if undocumented else f"{len(read_vars)} documented",
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

    # --- the census document against its own raw data ---------------------------------------------
    # The census is cited as provenance all over these documents, which makes IT a claim. Its
    # judgement calls ("49 of 435 put a detector in the loop") come from reading prose fields and
    # cannot be re-derived here — attempting it with a keyword heuristic gives 78, and a checker
    # that is confidently wrong is worse than no checker. What IS derivable is checked.
    census_json = REPO / "docs" / "humanizer-census.json"
    census_md = REPO / "docs" / "humanizer-census.md"
    if census_json.exists() and census_md.exists():
        import json as _json

        try:
            records = _json.loads(census_json.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            records = None
            report.check("the census raw data parses", False, f"{type(exc).__name__}: {exc}")
        if isinstance(records, list):
            body = census_md.read_text(encoding="utf-8")
            claimed = re.search(r"(\d{3,4})\s+read", body)
            report.check(
                "the census says how many repos it read",
                bool(claimed),
                "no 'N read' figure found" if not claimed else f"claims {claimed.group(1)}",
            )
            if claimed:
                report.check(
                    "the census record count matches its own prose",
                    len(records) == int(claimed.group(1)),
                    f"{len(records)} records vs {claimed.group(1)} claimed",
                )
            # Every repo the prose names in a table must exist in the data behind it.
            known = {r.get("name", "") for r in records if isinstance(r, dict)}
            named = set(re.findall(r"`([\w.-]+/[\w.-]+)`", body))
            absent = sorted(n for n in named if not any(n in k for k in known))
            report.check(
                "every repo the census names is in its raw data",
                not absent,
                f"named but absent: {absent[:5]}" if absent else f"{len(named)} named",
            )

    check_demo_privacy_claims(report)
    check_corpus_bound_claims(report)

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


_LOCAL_SCORING_CLAIMS = (
    "nothing uploaded",
    "never uploaded",
    "client-side port",
    "scores in the browser",
    "runs entirely in your browser",
)


_CORPUS_BOUND_CLAIMS: tuple[tuple[str, str, str], ...] = (
    # (phrase that overclaims, a qualifier that makes it honest, why it matters)
    (
        "drives the AI-tells rate to zero",
        "demo corpus",
        "true on the three built-in demo paragraphs (14.46 -> 0.0) and false on real HC3 text "
        "(4.22 -> 3.81); docs/humanizer-comparison.md already says the zero belongs to the demo "
        "corpus alone",
    ),
    (
        "drives the tell rate to zero",
        "demo corpus",
        "same claim, other phrasing",
    ),
)


def check_corpus_bound_claims(report: Report) -> None:
    """Fail when a headline states a corpus-bound result without naming its corpus.

    Found by running `untell-compare` on two corpora. The README said the loop "drives the
    AI-tells rate to zero while preserving meaning" full stop; measured, that is 14.46 -> 0.0 on
    the three built-in demo paragraphs and 4.22 -> 3.81 on HC3. Worse, the document the sentence
    links to had already been corrected and read "Any claim of 'drives the tell rate to zero' is a
    property of the demo corpus alone" — so the summary was contradicted by its own evidence and
    nothing noticed.

    This is the one failure mode `untell-audit`'s attribution check cannot see: the sentence
    carries no number, so there is nothing to demand provenance for. The claim IS the number.
    """
    offenders: list[str] = []
    for rel in (*LIVE_DOCS, "README.md", "CHANGELOG.md"):
        doc = REPO / rel
        if not doc.exists():
            continue
        text = doc.read_text(encoding="utf-8", errors="replace")
        # Emphasis markers are stripped before matching, and positions are preserved by replacing
        # each with a space rather than deleting it. The first version matched the raw text and
        # missed the exact sentence it was written for, because the README writes the claim as
        # "to **zero while preserving meaning**" and the asterisks sit inside the phrase. A checker
        # that any bold-face defeats is worse than none: it reports PASS.
        lowered = re.sub(r"[*_`]", " ", text.lower())
        lowered = re.sub(r"\s+", " ", lowered)
        flat_offsets = text.lower()
        for raw_phrase, raw_qualifier, _why in _CORPUS_BOUND_CLAIMS:
            # Case-fold the NEEDLE too. The first version compared a phrase written with its
            # natural capitalisation ("drives the AI-tells rate to zero") against lowercased text,
            # so it never matched anything and reported PASS on the exact sentence it was written
            # for. A check that cannot fail is worse than no check: it converts "nobody looked"
            # into "we verified it", which is the sentence at the top of this file.
            phrase, qualifier = raw_phrase.lower(), raw_qualifier.lower()
            start = 0
            while (idx := lowered.find(phrase, start)) != -1:
                start = idx + 1
                # The qualifier has to be near the claim, not merely somewhere in the file.
                window = lowered[max(0, idx - 400) : idx + 400]
                if qualifier not in window:
                    # `lowered` has collapsed whitespace so its offsets no longer map to the file;
                    # locate a stable anchor in the original for the line number.
                    anchor = phrase.split()[0]
                    pos = flat_offsets.find(anchor)
                    line = text[:pos].count(chr(10)) + 1 if pos != -1 else 0
                    offenders.append(f"{rel}:{line}: {phrase!r} with no corpus named")
    report.check(
        "no headline states a corpus-bound result without naming the corpus",
        not offenders,
        "; ".join(offenders) if offenders else f"{len(_CORPUS_BOUND_CLAIMS)} phrases checked",
    )


def check_demo_privacy_claims(report: Report) -> None:
    """Fail if a document says the browser demo scores locally while the page calls out.

    The changelog advertised ``docs/demo.html`` as a client-side port of the lite scorer that
    uploaded nothing. The page POSTs the text to an ``untell-server``. Of every kind of
    documentation drift, this is the one a reader can be harmed by acting on — pasting something
    they would not have sent had the page said where it was going.

    No attempt is made to distinguish a claim from a disavowal of one: that needs to read the
    prose, and a heuristic for it broke on the first correction that spanned two lines. The rule
    is that the phrases do not appear, so a correction must describe the old wording, not quote it.
    """
    demo = REPO / "docs" / "demo.html"
    if not demo.exists():
        return
    posts = "fetch(" in demo.read_text(encoding="utf-8", errors="replace")
    offenders: list[str] = []
    if posts:
        for rel in (*LIVE_DOCS, "CHANGELOG.md"):
            doc = REPO / rel
            if not doc.exists():
                continue
            text = doc.read_text(encoding="utf-8", errors="replace").lower()
            offenders += [f"{rel}: {p}" for p in _LOCAL_SCORING_CLAIMS if p in text]
    report.check(
        "no document claims the browser demo scores locally",
        not offenders,
        f"demo.html POSTs to the API, but: {sorted(set(offenders))}"
        if offenders
        else ("demo.html POSTs to the API and no document says otherwise" if posts else "n/a"),
    )


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
