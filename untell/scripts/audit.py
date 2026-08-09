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
import subprocess
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
    check_dynamic_env_vars(report)
    check_skill_commands(report)
    check_version_consistency(report)
    check_optional_extras(report)
    check_no_control_characters(report)
    check_census_counts(report)

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
    offenders: list[str] = []
    for rel in sorted(_tracked_text_files()):
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

    readme = (REPO / "README.md").read_text(encoding="utf-8", errors="replace")
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
