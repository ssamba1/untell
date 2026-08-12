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
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

# Documents that describe the CURRENT build. Dated artefacts are excluded on purpose: a changelog
# entry or a measurement log records what was true when it was written, and "fixing" those to match
# today's code would destroy the record rather than repair anything.
LIVE_DOCS = (
    "README.md",
    "ROADMAP.md",
    "docs/why-best-open-repo.md",
    "docs/index.md",
    "docs/what-would-make-this-the-top-repo.md",
)


# Environment variables the code reads, for the "every variable is documented" check below.
#
# BOTH PREFIXES. `HUMANIZE_*` is the pre-rename spelling and two switches still honour it, so a
# user setting one of those is using a supported knob the check could not see — and being
# undiscoverable is the exact defect this check exists to prevent.
#
# The leading `\b` is load-bearing: without it the pattern matches inside ordinary identifiers such
# as `_HUMANIZE_RESPONSES` in api_server.py, and the check would demand a README row for a Python
# variable. Module-level so the test can assert against THIS pattern instead of a copy of it — the
# test used to re-implement the regex, which meant a regression in the real one changed nothing.
ENV_VAR_RE = re.compile(r"\b((?:UNTELL|HUMANIZE)_[A-Z0-9_]+)\b")


def audited_doc(report: Report, rel: str) -> str | None:
    """Read a document the audit makes claims about, or record that it could not.

    This file had two incompatible answers for "the document is not there". Some checks did
    ``if not doc.exists(): continue`` and lost their findings without a word; others called
    ``read_text`` bare and died. MEASURED by deleting each `LIVE_DOCS` entry from a copy of the
    repository: `README.md` produced a `FileNotFoundError` traceback, and the checks that skip
    dropped their findings with the run still reporting success.

    Neither is acceptable for a command whose contract is to report what it could NOT check. The
    audit exists because "a correctness argument decays the moment a number in a document stops
    matching the code", and deleting the document is the largest drift there is. So absence is a
    named failure, and the run continues so the remaining checks still report.
    """
    path = REPO / rel
    if not path.exists():
        report.check(
            f"{rel}: present to be audited",
            False,
            "the document is missing, so every claim it carries went unchecked",
        )
        return None
    return path.read_text(encoding="utf-8")


def _optional_doc(rel: str) -> str | None:
    """A document that is not part of `LIVE_DOCS`, so its absence is not a claim going unchecked.

    Only the census page today. It is generated rather than written, and a repository without one
    has nothing to be stale.
    """
    path = REPO / rel
    return path.read_text(encoding="utf-8") if path.exists() else None

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


# Pages that make comparative claims about this repo against others. `LIVE_DOCS` is the set that
# describes the current build; this is that set plus the census, which is not a build description
# but does publish counts about us — "1868 tests against 136 repos" sat there stale precisely
# because every check scanned LIVE_DOCS and the census page was in neither list.
COMPARATIVE_DOCS = LIVE_DOCS + ("docs/humanizer-census.md",)


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
        body = audited_doc(report, rel)
        if body is None:
            continue
        for pattern, expected, kind in (
            (r"(\d+)\s+local\b", local, "local"),
            (r"(\d+)\s+commercial\b", commercial, "commercial"),
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
    readme = audited_doc(report, "README.md")
    if readme is None:
        return
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
            read_vars |= set(ENV_VAR_RE.findall(path.read_text(encoding="utf-8")))
    undocumented = sorted(v for v in read_vars if v not in readme)
    report.check(
        "every UNTELL_*/HUMANIZE_* variable the code reads is documented",
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
    check_dynamic_env_vars(report)
    check_skill_commands(report)
    check_version_consistency(report)
    check_optional_extras(report)
    check_no_control_characters(report)
    check_census_counts(report)
    check_named_repo_stars(report)
    check_largest_repo_claims(report)
    check_test_inventory(report)
    check_test_count_claims(report)
    check_unreleased_changelog_is_current(report)
    check_no_dead_functions(report)
    check_no_shadowed_definitions(report)
    check_selection_does_not_read_a_bare_max(report)

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


def check_no_control_characters(report: Report) -> None:
    r"""No tracked text file may contain a control character other than tab and newline.

    Written after a lone carriage return was spliced into a ROADMAP row: the edit script built the
    text in a non-raw Python string, so ``\ref`` became CR + ``ef``. Python warns about ``\c`` and
    stays silent about ``\r``, because ``\r`` is a perfectly valid escape — which is exactly why
    this one landed. On the page it rendered as ``ef``, and in a diff the CR is invisible.

    That is the fifth time an escape has been mangled by a shell or a string literal in this repo,
    and the first four were caught by reading the output rather than by any check. This is the
    mechanical version.

    CRLF is not the target: it is the normal Windows line ending and git converts it on the way in.
    Only a CR that is not part of a line ending, and other C0 controls, are reported.
    """
    tracked = sorted(_tracked_text_files())
    if not tracked:
        # `_tracked_text_files` returns [] when git is unavailable or the directory is not a
        # checkout, and this check then scanned nothing and reported "clean". MEASURED by copying
        # the repository without its `.git` and adding a BEL byte to `docs/index.md`: PASS, detail
        # "clean". Zero files inspected is not a clean repository, it is an unperformed check, and
        # this audit's whole contract is to say which claims it could not verify.
        report.check(
            "no tracked text file carries a stray control character",
            False,
            "git listed no tracked files, so nothing was scanned",
        )
        return
    offenders: list[str] = []
    for rel in tracked:
        path = REPO / rel
        try:
            text = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        stripped = text.replace("\r\n", "\n")
        for index, char in enumerate(stripped):
            if char in "\t\n":
                continue
            if ord(char) < 0x20 or ord(char) == 0x7F:
                line = stripped.count("\n", 0, index) + 1
                offenders.append(f"{rel}:{line} U+{ord(char):04X}")
                break

    report.check(
        "no tracked text file carries a stray control character",
        not offenders,
        f"found: {offenders[:5]}" if offenders else "clean",
    )


def _tracked_text_files() -> list[str]:
    """Everything git tracks that is plausibly text, by extension.

    Extension-based rather than content-sniffing: a binary misread as text would be reported as
    hundreds of control characters, and the point is to catch prose and source, not to classify
    files.
    """
    result = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        return []
    suffixes = {".md", ".py", ".toml", ".yml", ".yaml", ".json", ".txt", ".cfg", ".ini", ".tex"}
    return [
        line
        for line in result.stdout.splitlines()
        if line and Path(line).suffix in suffixes
    ]


# Rules for reading the census's free-text verdict fields. They are prose, not booleans, so every
# count published from them depends on a rule — and a count whose rule is not written down cannot
# be reproduced or corrected. These are the rules the published numbers now mean.
_CENSUS_NO = ("none", "no ", "not ", "nothing")

# A loop that only runs while a model is being trained is not an inference-time loop, whatever the
# field's first word says. Each of these entries states so in its own prose; they are matched by
# phrase rather than named, so a corrected entry changes the count instead of silently disagreeing
# with a hard-coded list.
_TRAINING_ONLY = re.compile(
    r"not (at )?inference|only during training|during training only|offline not real|"
    r"training[- ]time only|only in training|no re-?scoring at inference|"
    r"only during the training",
    re.I,
)


def _census_records() -> list[dict]:
    path = REPO / "docs" / "humanizer-census.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _census_says_yes(value: str | None) -> bool:
    text = re.sub(r"\s+", " ", value or "").strip().lower()
    return bool(text) and not text.startswith(_CENSUS_NO) and text not in ("-", "n/a")


def check_census_counts(report: Report) -> None:
    """Every count the census pages publish must fall out of the census data.

    These are the numbers the competitive claims rest on, and they were written by reading 435
    free-text entries. Re-deriving them found one that no rule reproduces: the pages said 43 repos
    run a detector at inference time, and the data says 44 — 49 answer "yes" to a detector in the
    loop, five of which state that the loop is training-time or offline only. One repo out by one
    is not much; a number nobody can re-derive is, because there is no way to tell a typo from a
    judgement call.

    "139 target another language" is deliberately not checked: the census JSON carries no language
    field, so that count lives only in the prose that made it and this check would have to invent
    a rule to confirm it.
    """
    records = _census_records()
    if not records:
        report.check("census data is readable", False, "docs/humanizer-census.json missing")
        return

    # `detector_in_loop` is answered with a verdict word — yes / no / partial / unclear — so it
    # reads by prefix. The other two fields are descriptive prose with no verdict word, so they
    # read by "does it start by denying one". Using the descriptive rule on this field counts the
    # 28 `unclear` entries as yes and reports 112.
    in_loop = [
        r for r in records
        if re.sub(r"\s+", " ", r.get("detector_in_loop") or "").strip().lower().startswith("yes")
    ]
    at_inference = [r for r in in_loop if not _TRAINING_ONLY.search(r.get("detector_in_loop") or "")]
    counts = {
        "detector-in-loop": len(in_loop),
        "at inference time": len(at_inference),
        "meaning verification": sum(1 for r in records if _census_says_yes(r.get("meaning_verification"))),
        "fact preservation": sum(1 for r in records if _census_says_yes(r.get("fact_preservation"))),
    }
    # Each published sentence, and the count it must agree with.
    claims = [
        ("docs/humanizer-census.md", r"\*\*(\d+)\*\* detector-in-loop", "detector-in-loop"),
        ("docs/humanizer-census.md", r"detector-in-loop \((\d+) at inference time\)", "at inference time"),
        ("docs/humanizer-census.md", r"(\d+) of 435 put a detector in the loop", "detector-in-loop"),
        ("docs/humanizer-census.md", r"put a detector in the loop; (\d+) at inference", "at inference time"),
        ("docs/why-best-open-repo.md", r"(\d+) of 435 profiled repos put a detector", "detector-in-loop"),
        ("docs/why-best-open-repo.md", r"(\d+) of them at inference time", "at inference time"),
        ("docs/why-best-open-repo.md", r"(\d+) of 435 verify meaning", "meaning verification"),
        ("docs/why-best-open-repo.md", r"(\d+) do some[\s>]+form of fact preservation", "fact preservation"),
        ("docs/humanizer-census.md", r"\*\*(\d+) repos do some fact preservation\*\*", "fact preservation"),
    ]
    wrong: list[str] = []
    checked = 0
    for rel, pattern, key in claims:
        path = REPO / rel
        if not path.exists():
            continue
        match = re.search(pattern, path.read_text(encoding="utf-8"))
        if not match:
            wrong.append(f"{rel}: no sentence matches /{pattern}/")
            continue
        checked += 1
        if int(match.group(1)) != counts[key]:
            wrong.append(f"{rel}: says {match.group(1)} {key}, data says {counts[key]}")

    report.check(
        "every census count the docs publish is re-derivable from the census data",
        not wrong,
        "; ".join(wrong) if wrong else f"{checked} published counts agree ({counts})",
    )


def _census_keys(record: dict) -> set[str]:
    """The names a document might reasonably use for one census record.

    Substring matching is not usable here: `Humanizer-zh` is a substring of 56 record names,
    including `Humanizer-zh-TW`, so a naive `in` test either matches everything or silently picks
    the wrong repo. Each record contributes its full name, each slash-separated part, and anything
    in parentheses — so `gzh-rewrite-skill (gongzhonghao-rewrite)` answers to both spellings, and
    `Humanizer-zh` matches only the repo actually called that.
    """
    name = record["name"]
    keys = {name.lower(), re.sub(r"\s*\([^)]*\)", "", name).strip().lower()}
    for part in re.split(r"[/()]", name):
        part = part.strip().lower()
        if part:
            keys.add(part)
    return {k for k in keys if k}


# `[^)]*` before the closing paren: a star count is often followed by a clause explaining the
# repo — `(298.8k★, its validator checklist is quoted in Chinese)`. Requiring the paren to close
# straight after the star silently skipped every exhibit that carried an explanation, which is
# most of the interesting ones, and left an ambiguous repo name unchecked.
# `\s*` alone is not enough: these pages wrap inside blockquotes, so a name and its star count
# are routinely separated by a newline and a `> ` continuation marker. The first version of this
# matched one exhibit out of six and reported PASS on the rest.
_STAR_CLAIM = re.compile(r"`([\w.\-/]+)`[\s>]*\((\d+(?:\.\d+)?)k?★[^)]*\)")


def check_named_repo_stars(report: Report) -> None:
    """A star count quoted next to a repo name must match the census, at the precision quoted.

    These numbers carry the comparative argument — "three of the eight largest" is only worth
    printing if the sizes behind it are right — and they are the easiest thing in any document to
    copy once and never revisit. Star counts also only move in one direction, so a stale one
    understates a competitor, which is the direction that flatters us.

    Rounding is respected rather than fought: `68.5k★` is checked against 68545 by comparing at one
    decimal place, so the doc is not forced to print 68,545 to pass.

    This is what remains checkable after the language count turned out not to be. That count is a
    per-record reading — the JSON has no language field, and three defensible keyword rules give
    130, 135 and 138 against a published 139 — so the pages now say so, and the check covers the
    part that has data underneath it.
    """
    records = _census_records()
    if not records:
        return
    wrong: list[str] = []
    checked = 0
    for rel in ("docs/why-best-open-repo.md", "docs/humanizer-census.md", "ROADMAP.md", "README.md"):
        text = audited_doc(report, rel) if rel in LIVE_DOCS else _optional_doc(rel)
        if text is None:
            continue
        for name, value in _STAR_CLAIM.findall(text):
            matches = [r for r in records if name.lower() in _census_keys(r)]
            if len(matches) != 1:
                wrong.append(f"{rel}: `{name}` matches {len(matches)} census records")
                continue
            checked += 1
            actual = matches[0]["stars"]
            claimed = float(value)
            # A bare integer means literal stars; a decimal means thousands.
            shown = round(actual / 1000, 1) if "." in value else actual
            if abs(claimed - shown) > 0.05:
                wrong.append(f"{rel}: `{name}` says {value}k★, census has {actual}")

    report.check(
        "every star count quoted beside a repo name matches the census",
        not wrong,
        "; ".join(wrong) if wrong else f"{checked} star counts agree",
    )


def check_largest_repo_claims(report: Report) -> None:
    """A repo named as one of the N largest must actually be in the top N by stars.

    Written because a page claimed "four of the eight largest repos in the field" and named two
    that rank 9th and 12th. The count was right — four of the top eight are non-English — but two
    of the four exhibits were the wrong repos, which is the failure mode a reader cannot catch
    without the table in front of them.
    """
    records = _census_records()
    if not records:
        return
    ranked = sorted(records, key=lambda r: -r["stars"])
    wrong: list[str] = []
    checked = 0
    for rel in ("docs/why-best-open-repo.md", "docs/humanizer-census.md"):
        text = audited_doc(report, rel) if rel in LIVE_DOCS else _optional_doc(rel)
        if text is None:
            continue
        for match in re.finditer(r"of the (\w+) largest", text):
            word = match.group(1).lower()
            size = {"three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
                    "nine": 9, "ten": 10}.get(word)
            if size is None:
                continue
            top = {r["name"].lower() for r in ranked[:size]}
            # Exhibits are the repos named in the clause the claim opens, which ends at the first
            # semicolon or full stop. The convention these pages follow is exhibits first, caveats
            # after — and the caveats deliberately name repos that are NOT in the top N, together
            # with their real rank, so reading past the clause boundary reports the disclaimer as
            # the very error it exists to record.
            rest = text[match.end():match.end() + 700]
            stop = min((i for i in (rest.find(";"), rest.find(". ")) if i != -1), default=len(rest))
            window = rest[:stop]
            for name, _value in _STAR_CLAIM.findall(window):
                hit = [r for r in ranked if name.lower() in _census_keys(r)]
                if len(hit) != 1:
                    continue
                checked += 1
                if hit[0]["name"].lower() not in top:
                    rank = ranked.index(hit[0]) + 1
                    wrong.append(f"{rel}: `{name}` named among the {word} largest but ranks {rank}")

    report.check(
        "every repo named among the N largest is in the top N",
        not wrong,
        "; ".join(wrong) if wrong else f"{checked} exhibits are within their claimed rank",
    )


_MODULE_DRIFT = 5


def check_test_inventory(report: Report) -> None:
    """A "N tests, M modules" claim must match what is on disk.

    The module count is exact and free to compute, so it is enforced. The collected-test count is
    not: collection depends on which optional dependencies are installed, so a hard equality would
    fail on a machine with a different extras set — it is treated as a measured claim instead, and
    the attribution rule makes the page state how to reproduce it.

    Both numbers in this table were stale — 2473 tests and 75 modules against 2543 and 80 — and
    both had slipped past the attribution check, because a bolded bare number like `**2473**` was
    exempted as "not a claim". It is the most common way this repo writes a claim.
    """
    modules = sorted((REPO / "tests").glob("test_*.py"))
    wrong: list[str] = []
    checked = 0
    for rel in COMPARATIVE_DOCS:
        path = REPO / rel
        if not path.exists():
            continue
        for found in re.findall(r"(\d+)\s+(?:test\s+)?modules\b", path.read_text(encoding="utf-8")):
            checked += 1
            claimed = int(found)
            # Asymmetric, matching the contract test_why_best_test_count_is_not_stale uses
            # for the test count. Overstating is always a defect: it claims coverage that
            # does not exist. Understating by a little is what happens whenever a module
            # lands between one session reading the count and writing it — MEASURED, this
            # check fired ten times in one session, every time one behind, and not once on a
            # genuinely stale document.
            #
            # The window is small on purpose. The failure this exists for is a doc abandoned
            # at 75 while the suite grows past 100, and five modules does not hide that.
            if claimed > len(modules):
                wrong.append(
                    f"{rel}: claims {claimed} test modules, tests/ has only {len(modules)}"
                )
            elif len(modules) - claimed > _MODULE_DRIFT:
                wrong.append(
                    f"{rel}: says {claimed} test modules, tests/ has {len(modules)} — stale "
                    f"by more than {_MODULE_DRIFT}"
                )

    report.check(
        "every 'N test modules' claim matches tests/",
        not wrong,
        "; ".join(wrong) if wrong else f"{checked} claim(s) agree, tests/ has {len(modules)} modules",
    )


def _collected_test_count() -> int | None:
    """How many tests pytest actually collects, or None if it cannot be asked.

    Collection is not free (about ten seconds) and not constant: it depends on which optional
    extras are installed, because some modules skip at import. So this is used for a drift band,
    never for equality.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:randomly"],
            cwd=REPO, capture_output=True, text=True, timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"(\d+)\s+tests? collected", result.stdout)
    return int(match.group(1)) if match else None


def check_test_count_claims(report: Report) -> None:
    """A "N tests" claim about our own suite must be in the same neighbourhood as reality.

    Deliberately a band, not an equality. Collection varies with the installed extras, so an exact
    check would fail on a correct machine — and a check that fails on correct machines gets
    disabled, which is worse than not having it.

    Ten percent is wide enough to absorb that and narrow enough to catch what actually happens
    here, which is not drift but abandonment: the docs said 1868 and 2473 while the suite was at
    2543. Both had sat through many additions without anyone revisiting them.
    """
    actual = _collected_test_count()
    if actual is None:
        report.check(
            "every 'N tests' claim is close to what pytest collects",
            True,
            "skipped: pytest could not be run to collect",
        )
        return

    wrong: list[str] = []
    checked = 0
    for rel in COMPARATIVE_DOCS:
        path = REPO / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        # Only claims about OUR suite. "1868 tests against 136 repos" is ours; a sentence about
        # another project's tests is not, and none of the live docs currently phrase one that way.
        for found in re.findall(r"\*{0,2}(\d{3,5})\*{0,2}\s+tests\b", text):
            claimed = int(found)
            checked += 1
            if abs(claimed - actual) > 0.10 * actual:
                wrong.append(f"{rel}: claims {claimed} tests, pytest collects {actual}")

    report.check(
        "every 'N tests' claim is close to what pytest collects",
        not wrong,
        "; ".join(wrong) if wrong else f"{checked} claim(s) within 10% of {actual} collected",
    )


# Names that are reached without being written anywhere: an argparse subcommand, a console-script
# entry point, a framework hook. `main`/`run`/`build_parser` are the entry-point trio this repo
# uses; a decorated function is registered by its decorator, which is why the FastAPI routes and
# middleware do not appear by name in any caller.
_REACHED_WITHOUT_A_CALLER = {"main", "run", "build_parser"}


def check_no_shadowed_definitions(report: Report) -> None:
    """No module may define the same top-level name twice.

    Python keeps the last definition, silently, and every caller of the first one gets the second.
    MEASURED, this happened here: `structural` had a `_content_words` returning a set of words, a
    second `_content_words` returning an int was added 280 lines later, and `_drop_restatements` —
    which had not been touched — began raising

        TypeError: object of type 'int' has no len()

    No test caught it. The suite exercises `_drop_restatements` through the rewriter, and the
    rewriter crashed only on the corpus sweep that happened to run first. In a 2500-line module two
    functions wanting the same name is ordinary, and the cost of noticing is one AST pass.

    Scans `untell/`, `eval/` and `tests/` at module level only. A method redefined inside a class is
    the same defect, but nested scopes also carry legitimate redefinition — a `try`/`except
    ImportError` pair defining a fallback is the common one here — and this check is not worth a
    false positive.
    """
    dupes: list[str] = []
    scanned = 0
    for path in sorted(
        [*(REPO / "untell").rglob("*.py"), *(REPO / "eval").glob("*.py"),
         *(REPO / "tests").glob("*.py")]
    ):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        seen: dict[str, int] = {}
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            scanned += 1
            if node.name in seen:
                dupes.append(
                    f"{path.relative_to(REPO).as_posix()}: {node.name} redefined at line "
                    f"{node.lineno}, shadowing line {seen[node.name]}"
                )
            seen[node.name] = node.lineno
    report.check(
        "no module defines the same top-level name twice",
        not dupes,
        "; ".join(dupes) if dupes else f"{scanned} definitions, none shadowed",
    )


SELECTION_ON_BARE_MAX_ALLOWED = {
    # module::function -> why comparing the bare max is right here
    "untell/scripts/run.py::_passed": "acceptance against the shipped threshold, not a choice "
    "between candidates",
    "untell/scripts/run.py::_untell_text": "candidate selection, but with the measured tells "
    "tie-break inside _TELLS_EPS — a documented secondary objective, not a blind max",
    "untell/scripts/verify.py::verify": "reports the verdict a caller asked for",
    "untell/rich_output.py::print_humanize_result": "tests whether the max is PINNED so the report "
    "can say the delta beside it means nothing — the opposite of trusting it to choose",
    "untell/attacks/word_importance.py::surgical_substitute": "the prefer_tells branch ranks on "
    "(tells, max); the score-only branch is the caller's explicit opt-out",
}


def check_selection_does_not_read_a_bare_max(report: Report) -> None:
    """Comparing detector ``max`` values to pick a candidate needs the shared selector.

    `max` is one detector's number, and a saturating member pins it. MEASURED over 80 corpus texts:
    the ensemble max reaches >=0.999 on 100% of HC3 AI text and 30% of RAID's, against 0% of human
    text; `hc3_roberta` returns >=0.99 on 58 of 60 HC3 sentences (`roberta_openai` on 2 of them, mean
    0.7405 — the pinning was attributed to it in five places before anyone measured). Five seeded
    candidates per
    text gave ONE distinct max on 4 of 6 documents and one distinct mean on 1 of 6 — so a selector
    reading `max` alone is choosing among candidates it cannot tell apart.

    This has now been found twice. `composite._selection_key` was written for it, with its own
    measurement. `targeted` still compared bare floats and was discarding 15 of 19 real per-sentence
    improvements, every one of them a strict win on mean under a tied max. The fix is the same
    `(max, mean)` selector, which is why it lives in `untell/rewriter/base.py`.

    Not every `max` comparison is a selection. Acceptance against a threshold, a reported verdict and
    a selector with a different measured secondary objective are all legitimate, so each is listed in
    ``SELECTION_ON_BARE_MAX_ALLOWED`` with its reason rather than pattern-matched around. A NEW site
    fails this check, which is the point: the ad-hoc grep that found the second instance becomes a
    thing the repository does every run.
    """

    def _is_max_read(node: ast.expr) -> bool:
        while (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "float"
            and node.args
        ):
            node = node.args[0]
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == "max"
        ):
            return True
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and bool(node.args)
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "max"
        )

    ordering = (ast.Lt, ast.Gt, ast.LtE, ast.GtE)
    found: set[str] = set()
    for path in sorted((REPO / "untell").rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = path.relative_to(REPO).as_posix()
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(fn):
                if not isinstance(node, ast.Compare):
                    continue
                if not any(isinstance(op, ordering) for op in node.ops):
                    continue
                if any(_is_max_read(side) for side in [node.left, *node.comparators]):
                    found.add(f"{rel}::{fn.name}")
    unlisted = sorted(found - set(SELECTION_ON_BARE_MAX_ALLOWED))
    stale = sorted(set(SELECTION_ON_BARE_MAX_ALLOWED) - found)
    problems = [f"unlisted: {s}" for s in unlisted] + [f"no longer present: {s}" for s in stale]
    report.check(
        "every bare-max comparison is a listed non-selection",
        not problems,
        "; ".join(problems)
        if problems
        else f"{len(found)} sites, all accounted for",
    )


def check_no_dead_functions(report: Report) -> None:
    """No function in untell/ or eval/ may be unreferenced everywhere.

    A function nobody calls is either a bug (something stopped calling it) or clutter, and both
    read the same in a diff. This is a textual reference count rather than a call graph, which is
    the right trade for a codebase that dispatches rewriters and detectors by string name — a call
    graph would report every registry entry as dead.

    Decorated functions are exempt because their decorator is the registration: `@app.post` and
    `@app.middleware` were the only two hits when this was first run over 343 functions, and both
    are live routes.
    """
    defined: dict[str, list[str]] = {}
    decorated: set[str] = set()
    sources = [*(REPO / "untell").rglob("*.py"), *(REPO / "eval").rglob("*.py")]
    for path in sources:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                rel = path.relative_to(REPO).as_posix()
                defined.setdefault(node.name, []).append(f"{rel}:{node.lineno}")
                if node.decorator_list:
                    decorated.add(node.name)

    searched = [*sources, *(REPO / "tests").rglob("*.py"),
                *REPO.glob("*.toml"), *(REPO / "docs").glob("*.md"), *REPO.glob("*.md")]
    corpus = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in searched)

    dead: list[str] = []
    for name, locations in sorted(defined.items()):
        if name.startswith("__") or name in _REACHED_WITHOUT_A_CALLER or name in decorated:
            continue
        # More occurrences than definitions means something other than the `def` line mentions it.
        if len(re.findall(rf"\b{re.escape(name)}\b", corpus)) <= len(locations):
            dead.append(f"{name} ({locations[0]})")

    report.check(
        "no function in untell/ or eval/ is unreferenced",
        not dead,
        f"unreferenced: {dead[:6]}" if dead else f"{len(defined)} functions, all referenced",
    )


def check_unreleased_changelog_is_current(report: Report) -> None:
    """Numbers in `[Unreleased]` describe what will ship, so they are held to the live standard.

    The rest of the changelog is deliberately exempt: a released entry records what was true when
    it was written, and "correcting" it would destroy the record rather than repair anything. That
    exemption does not extend upward. An `[Unreleased]` entry has not been published yet — it is a
    draft of the next release notes, and shipping a superseded number in it is shipping a wrong
    claim, not preserving a historical one.

    Found by re-deriving the tell-rate corpus means: the caveat in the code said 0.551/7.335, the
    re-measurement said 0.642/7.320, and the `[Unreleased]` entry describing that very change still
    carried the old pair.

    Checks the narrow, mechanical thing: any number the entry attributes to a constant or string in
    the code must still match it. Prose claims are not checked here — `check_attribution` already
    requires them to name a source.
    """
    path = REPO / "CHANGELOG.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if "## [Unreleased]" not in text:
        report.check("the changelog has an Unreleased section", True, "none; nothing to check")
        return
    start = text.index("## [Unreleased]")
    end = text.find("\n## [", start + 1)
    unreleased = text[start : end if end != -1 else len(text)]

    from untell.scripts.tells import _MIN_WORDS_FOR_A_RATE, score_tells

    wrong: list[str] = []
    # The corpus means the tells caveat quotes, taken from the caveat itself rather than hard-coded
    # here — two copies of a number is how they drift apart in the first place.
    caveat = score_tells("Moreover.").get("warning") or ""
    for value in re.findall(r"\b\d\.\d{3}\b", caveat):
        if value not in unreleased and "corpus means" in unreleased:
            wrong.append(f"caveat quotes {value}, Unreleased does not")
    if f"{_MIN_WORDS_FOR_A_RATE} words" not in unreleased and "corpus means" in unreleased:
        wrong.append(f"the rate bar is {_MIN_WORDS_FOR_A_RATE} words; Unreleased says otherwise")

    report.check(
        "numbers in the Unreleased changelog match the code they describe",
        not wrong,
        "; ".join(wrong) if wrong else "corpus means and rate bar agree with the shipped caveat",
    )


def check_optional_extras(report: Report) -> None:
    """Every ``untell[extra]`` a document tells a user to install must exist.

    A renamed or removed extra fails only at install time, on someone else's machine, with pip's
    own unhelpful "does not provide the extra" — and the person hitting it is following our own
    README. Cheap to check statically, and the audit already owns this class of drift.

    The pattern requires an install context (``pip install`` on the same line, or the
    ``untell[...]`` spelling) rather than any bracketed word, because a bare ``[...]`` scan matches
    regex character classes: the first version of this reported ``Mm`` as an undeclared extra,
    having found ``[Mm]`` inside a pattern in ``preserve.py``.
    """
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    if "[project.optional-dependencies]" not in pyproject:
        report.check("pyproject declares optional dependencies", False, "section missing")
        return
    block = pyproject.split("[project.optional-dependencies]", 1)[1].split("\n[", 1)[0]
    declared = set(re.findall(r"^(\w+)\s*=\s*\[", block, re.M))

    sources: list[Path] = [
        *REPO.glob("*.md"),
        *(REPO / "docs").glob("*.md"),
        *(REPO / ".github" / "workflows").glob("*.yml"),
    ]
    unknown: dict[str, str] = {}
    for path in sources:
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r'untell\[([\w,\s]+)\]|pip install[^\n]*?\.\[([\w,\s]+)\]', text):
            for name in (match.group(1) or match.group(2)).replace(" ", "").split(","):
                if name and name not in declared:
                    unknown.setdefault(name, path.relative_to(REPO).as_posix())

    report.check(
        "every extra the docs tell a user to install exists",
        not unknown,
        f"undeclared: {unknown}" if unknown
        else f"{len(declared)} extras declared, all references resolve",
    )


def check_version_consistency(report: Report) -> None:
    """Every file that states the version must state the same one.

    ``CITATION.cff`` said 0.1.0 while ``pyproject.toml`` and ``untell.__version__`` said 0.3.0 —
    two minor releases stale. That file is not decoration in a repository aimed at the academic
    niche: it is what a citation manager reads, so anyone citing this work would have cited a
    version that stopped being current in June.

    Derivable from the tree, so it belongs in the audit rather than on a release checklist that
    someone has to remember to follow.
    """
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    declared = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M)
    if not declared:
        report.check("pyproject declares a version", False, "no version field found")
        return
    version = declared.group(1)

    stated: dict[str, str | None] = {}
    try:
        import untell

        stated["untell.__version__"] = getattr(untell, "__version__", None)
    except Exception:  # noqa: BLE001
        stated["untell.__version__"] = None

    citation = REPO / "CITATION.cff"
    if citation.exists():
        found = re.search(
            r'^version:\s*"?([^"\n]+)"?', citation.read_text(encoding="utf-8"), re.M
        )
        stated["CITATION.cff"] = found.group(1).strip().strip('"') if found else None

    disagreeing = {k: v for k, v in stated.items() if v is not None and v != version}
    unreadable = [k for k, v in stated.items() if v is None]
    report.check(
        "every file that states the version agrees with pyproject",
        not disagreeing and not unreadable,
        f"pyproject={version}"
        + (f"; disagreeing: {disagreeing}" if disagreeing else "")
        + (f"; unreadable: {unreadable}" if unreadable else "")
        + (f"; {len(stated)} sources checked" if not disagreeing and not unreadable else ""),
    )


def check_skill_commands(report: Report) -> None:
    """Every command SKILL.md tells Claude to run must exist and accept the flags it is given.

    ``untell/SKILL.md`` is the primary interface for Claude Code users — it is the procedure the
    model follows — and it was not in ``LIVE_DOCS``, so nothing checked it. A renamed script or a
    dropped flag there does not produce a failing test; it produces a skill that errors on a user's
    first invocation, with the model improvising around a command that no longer works.

    Commands are split on the pipe before flags are attributed. A naive scan blamed
    ``preserve.py`` for ``--threshold``, because the line reads::

        python scripts/preserve.py --restore --mapping '...' | python scripts/score.py --threshold 0.30

    and reported a defect that does not exist. A flag belongs to the segment it appears in.
    """
    import subprocess

    skill = REPO / "untell" / "SKILL.md"
    if not skill.exists():
        report.check("SKILL.md exists", False, "missing")
        return
    text = skill.read_text(encoding="utf-8", errors="replace")

    # Script paths first: a renamed module is the likelier breakage and needs no subprocess.
    referenced = sorted(set(re.findall(r"scripts[/\\](\w+)\.py", text)))
    absent = [s for s in referenced if not (REPO / "untell" / "scripts" / f"{s}.py").exists()]
    report.check(
        "every script SKILL.md invokes exists",
        not absent,
        f"missing: {absent}" if absent else f"{len(referenced)} scripts",
    )

    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    segment_re = re.compile(r"(\w+\.py|untell-[\w-]+)((?:\s+[^|\n`]*)?)")
    flag_re = re.compile(r"(--[a-z][\w-]+)")
    wanted: dict[str, set[str]] = {}
    for line in text.splitlines():
        for segment in line.split("|"):
            for match in segment_re.finditer(segment):
                flags = set(flag_re.findall(match.group(2) or ""))
                if flags:
                    wanted.setdefault(match.group(1), set()).update(flags)

    unaccepted: list[str] = []
    for target, flags in sorted(wanted.items()):
        if target.endswith(".py"):
            module = f"untell.scripts.{target[:-3]}"
        else:
            found = re.search(rf"^{re.escape(target)}\s*=\s*\"([\w.]+):", pyproject, re.M)
            module = found.group(1) if found else None
        if not module:
            unaccepted.append(f"{target}: not a declared console script")
            continue
        try:
            result = subprocess.run(
                [sys.executable, "-m", module, "--help"],
                capture_output=True, text=True, timeout=120,
            )
        except Exception as exc:  # noqa: BLE001
            unaccepted.append(f"{target}: --help failed ({type(exc).__name__})")
            continue
        help_text = result.stdout + result.stderr
        unaccepted += [f"{target} {f}" for f in sorted(flags) if f not in help_text]

    report.check(
        "every flag SKILL.md passes is accepted by the script it passes it to",
        not unaccepted,
        f"rejected: {unaccepted}" if unaccepted
        else f"{sum(len(v) for v in wanted.values())} flags across {len(wanted)} commands",
    )


def check_dynamic_env_vars(report: Report) -> None:
    """Env vars whose names the code BUILDS rather than writes out.

    The scanner above greps for the literal ``UNTELL_...``. `untell/config.py` reads its settings
    as ``f"UNTELL_{key.upper()}"``, so five real, user-settable variables were invisible to it —
    UNTELL_TIER, UNTELL_THRESHOLD, UNTELL_REWRITER, UNTELL_STYLE and UNTELL_BEST_OF were all
    undocumented and the check reported PASS. Only UNTELL_THRESHOLD ever surfaced, and only because
    an unrelated comment happened to spell it out.

    A checker with a blind spot in the shape of its own implementation is the failure this file
    exists to prevent, so the constructed family is enumerated from the source of truth — the
    config-key table the CLI actually reads — rather than from another list of literals.
    """
    try:
        from untell.scripts.run import _CLI_DEFAULTS
    except Exception as exc:  # noqa: BLE001
        report.check("the config key table is importable", False, f"{type(exc).__name__}: {exc}")
        return

    readme = audited_doc(report, "README.md")
    if readme is None:
        return
    undocumented = [
        f"UNTELL_{key.upper()}" for key in _CLI_DEFAULTS
        if f"UNTELL_{key.upper()}" not in readme
    ]
    report.check(
        "every config key's UNTELL_* form is documented",
        not undocumented,
        f"undocumented: {undocumented}" if undocumented
        else f"{len(_CLI_DEFAULTS)} config keys, all documented",
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
                if "](" in claim or "http" in claim:
                    continue
                # A bolded BARE number used to be exempted here as "not a claim", on the reasoning
                # that a version string is not a measurement. But `**2473**` tests and `**139**`
                # non-English are bare numbers, and they are exactly the claims most worth
                # attributing — the exemption covered 26 numbers in the live docs, one of which had
                # drifted (2473 tests against 2543) with nothing to catch it. Versions and dates
                # are still skipped below, by patterns that describe versions and dates.
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
    p.add_argument(
        "--fix-counts",
        action="store_true",
        help="rewrite the 'N tests, M modules' claims in the comparative docs to what is on disk",
    )
    return p


def fix_counts() -> list[str]:
    """Rewrite the test/module counts in the comparative docs to the measured values.

    These two numbers went stale four times in a single session — not because anyone abandoned the
    document, but because two agents were adding test modules faster than a hand-maintained figure
    in a comparison table can track. The check catches it every time and the repair was four
    identical manual edits.

    Only the counts are touched, and only in `COMPARATIVE_DOCS`. The module count is exact. The test
    count is taken from a LITE collection — `UNTELL_LITE_NO_TORCH=1` — because that is the smaller
    of the two and the number `test_why_best_test_count_is_not_stale` compares against; a figure
    from a full-tier run is correct there and fails here, which is how this last broke.

    Returns a description of each edit, empty when nothing needed changing.
    """
    modules = len(sorted((REPO / "tests").glob("test_*.py")))
    collected = _collected_test_count()
    edits: list[str] = []
    for rel in COMPARATIVE_DOCS:
        path = REPO / rel
        if not path.exists():
            continue
        before = path.read_text(encoding="utf-8")
        after = re.sub(r"(\d+)(\s+(?:test\s+)?modules\b)", rf"{modules}\2", before)
        if collected is not None:
            after = re.sub(r"\*\*(\d+)\*\*(\s+tests\b)", rf"**{collected}**\2", after)
        if after != before:
            path.write_text(after, encoding="utf-8")
            edits.append(f"{rel}: counts set to {collected} tests, {modules} modules")
    return edits


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.fix_counts:
        edits = fix_counts()
        print("\n".join(edits) if edits else "counts already match what is on disk")
    report = run()
    print(_render(report, args.json))
    return 0 if (not report.failures and not report.unattributed) else 1


if __name__ == "__main__":
    sys.exit(main())
