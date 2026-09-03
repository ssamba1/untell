"""How reliable is each checker here, and how do we know?

Round one hundred and two ended with a pattern that has four instances and no owner: **the first
version of a static rule is always too loose.** The claim-verification proximity rule reported 15
contradictions, all false. The citation cross-check reported 35, of which 10 were the checker's own
fault. The cache-patch rule had one finding and it was false. The result-key checker reported 38
distinct pairs against 8 real ones.

Each was fixed by reading every finding while the list was still short enough to read, and each fix
was recorded in the round that made it. **Nothing records it afterwards.** A reader looking at
`eval/` today sees eight checkers and no way to tell which have had their findings verified, which
gate a commit, and which report a number nobody has ever checked.

So this is a register of the checkers themselves. For each: what it reports, whether it can fail a
commit, and its **measured precision** — the share of its findings that were real when somebody last
read them all.

⚠️ **Precision is recorded where it was measured and marked absent where it was not.** That is round
ninety's rule applied to this register: a checker with no precision figure is not a precise one, it
is an unmeasured one, and folding the two together is how a register stops being worth reading.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Checker:
    """One checker, and what is known about how far to trust it."""

    command: str
    checks: str
    gates: bool
    """Whether a non-empty finding list exits non-zero, and so can fail a commit."""
    findings_now: str
    precision: str | None
    """Share of findings that were real when somebody last read all of them. None = never measured."""
    how_precision_was_measured: str | None
    first_version_defect: str | None
    recall: str | None = None
    """Share of PLANTED defects the checker catches. None = never measured.

    Precision is about the findings; recall is about the defects. A checker reporting one finding
    and being right is 100% precise and may be missing forty.
    """


REGISTER: tuple[Checker, ...] = (
    Checker(
        command="python -m eval.claim_verification",
        checks="each registered headline figure still matches the artefact key that produces it",
        gates=True,
        findings_now="0 drifted of 19 registered",
        precision="100%",
        how_precision_was_measured=(
            "100% because no inference is involved: the mapping from figure to artefact key is "
            "written out by hand, so a "
            "false positive is not expressible. The cost is that coverage is what somebody "
            "registered."
        ),
        first_version_defect=(
            "linked figures to artefacts by PROXIMITY and reported 15 contradictions, every one "
            "false. Three narrowings of scope moved the count by zero, because the premise — that a "
            "number near a tool's name came from that tool — is simply untrue."
        ),
    ),
    Checker(
        command="python -m eval.litreview --untriaged",
        checks="figures attributed to a cited paper that the paper's abstract does not contain",
        gates=True,
        findings_now="0 untriaged of 33 findings",
        precision="0%",
        how_precision_was_measured=(
            "0% real: all 33 read against the cached abstracts and recorded in "
            "eval/data/citation_triage.json with a reason each; none is a misattribution"
        ),
        first_version_defect=(
            "matched titles rather than abstracts and treated a markdown table as one attribution "
            "unit, so a single citation captured every row's figures: 35 findings, 10 of them the "
            "checker's own fault"
        ),
    ),
    Checker(
        command="python -m eval.cache_keys",
        checks="cached functions reading state their key does not name, and tests that patch "
               "behind a cache without clearing it",
        gates=True,
        findings_now="0 unaccepted of 6 cached functions",
        precision="1 of 6",
        how_precision_was_measured=(
            "all 6 read; 5 are pure once one level of indirection is followed, and the 6th — "
            "`human_base_rates` — has a "
            "genuinely empty key over a committed file"
        ),
        first_version_defect=(
            "flagged any patch of a MODULE owning a cached function; its one finding was false, and "
            "the coarse rule had been written down as deliberate"
        ),
        recall="6/6",
    ),
    Checker(
        command="python -m eval.result_keys",
        checks="a caller reading a key its function never returns",
        gates=True,
        findings_now="0",
        precision="89%",
        how_precision_was_measured=(
            "all 9 findings of the final version read against the source: 8 were real undocumented "
            "conditional keys and the 9th was a tautology, `assert X or True`"
        ),
        first_version_defect=(
            "unordered origin tracking with no invalidation: 38 distinct pairs against 8 real. "
            "Three fixes — source order, rebinding forms, scope pruning — took it to 9."
        ),
        recall="8/8",
    ),
    Checker(
        command="python -m eval.constant_influence",
        checks="whether any undefended constant reaches the published score",
        # NOT gating: it always exits 0. Registered as gating in the first draft of this register,
        # and the register's own test caught it — a false assurance is worse than an absent one,
        # because somebody relies on it.
        gates=False,
        findings_now="0 live of 35 tested, 6 unreachable by perturbation",
        precision="n/a",
        how_precision_was_measured=(
            "a positive control instead: perturbing a constant known to reach the target moves "
            "99.6% of documents, and the register refuses to report at all if it does not"
        ),
        first_version_defect=None,
    ),
    Checker(
        command="python -m eval.boundaries",
        checks="comparisons against a named threshold whose off-by-one no test catches",
        gates=False,
        findings_now="26 unprotected of 48, 1 unmeasurable",
        precision="90%",
        how_precision_was_measured=(
            "all 30 re-run against EVERY test importing their module, uncapped: 27 genuine gaps "
            "and 3 artefacts of the sweep's capped test selection"
        ),
        first_version_defect=(
            "read a sweep taken before the tests it should have credited, so all seven boundaries "
            "fixed two rounds earlier came back unprotected — wrong in the alarming direction"
        ),
        recall="8/8",
    ),
    Checker(
        command="python -m eval.constant_census",
        checks="numeric constants with no stated reason for their value",
        gates=False,
        findings_now="41 undefended of 111",
        precision="11 of 12",
        how_precision_was_measured=(
            "a seeded sample of 12 of the 41 read against the source. 11 genuinely have no stated "
            "reason for their VALUE; 1 (`_MANIFEST_VERSION`) is a schema version rather than a "
            "threshold and should not have been in scope. ⚠️ The sample also exposed an ambiguity "
            "in the check's own definition: for 5 of the 11, a comment explains why the MECHANISM "
            "exists without saying why the number is that number — `_MAX_NAMED_SIGNALS = 5` is "
            "capped so 'the prompt stays proportionate to the actual worst offenders', which is a "
            "reason for capping and not for five. Reading those as justified gives 6 of 12 instead. "
            "Both readings are recorded because the check cannot tell them apart and neither can a "
            "single number."
        ),
        first_version_defect=(
            "stopped its upward walk at the first non-comment line, so a block comment heading a "
            "GROUP of constants justified only the first: 49 reported against 41 real"
        ),
        recall="6/6",
    ),
    Checker(
        command="python -m eval.mutation --all",
        checks="single-token edits to shipped code that no test notices",
        gates=False,
        findings_now="survivor lists per operator; 26.0% of boundary mutants killed",
        precision="87.5%",
        how_precision_was_measured=(
            "a stratified sample of 24 survivors, 3 per operator kind, each re-run against EVERY "
            "test importing its module rather than the capped selection the sweep uses: 21 "
            "genuinely uncaught, 3 killed by a test the sweep never ran. Wilson 95% interval "
            "[69.0%, 95.7%]. ⚠️ The per-kind cells are 3 samples each and are NOT a ranking — a "
            "2-of-3 cell has an interval of [20.8%, 93.9%], which is the whole plausible range."
        ),
        first_version_defect=(
            "two harness defects, both producing FALSE SURVIVORS: stale bytecode masking same-size "
            "mutations, and a test selection that ranked boundary tests last and dropped them"
        ),
    ),
)


def report() -> dict:
    rows = [asdict(c) for c in REGISTER]
    return {
        "checkers": len(rows),
        "gating": sum(1 for c in REGISTER if c.gates),
        "precision_measured": sum(1 for c in REGISTER if c.precision is not None),
        "first_version_was_too_loose": sum(
            1 for c in REGISTER if c.first_version_defect is not None),
        "recall_measured": sum(1 for c in REGISTER if c.recall is not None),
        "rows": rows,
    }


def render(data: dict) -> str:
    lines = [
        f"{data['checkers']} checkers. {data['gating']} can fail a commit. "
        f"{data['precision_measured']} have had their findings read and counted.",
        f"{data['first_version_was_too_loose']} shipped a first version that was too loose. "
        f"{data['recall_measured']} have had their recall measured by planting defects.",
        "",
        f"  {'command':<44} {'gates':>5} {'precision':>10} {'recall':>7}  findings now",
    ]
    for row in data["rows"]:
        precision = row["precision"] or "UNMEASURED"
        lines.append(f"  {row['command']:<44} {'yes' if row['gates'] else 'no':>5} "
                     f"{precision[:10]:>10} {(row['recall'] or '—'):>7}  {row['findings_now']}")
    lines += [
        "",
        "A checker with no precision figure is not a precise one, it is an unmeasured one.",
        f"The first version was too loose {data['first_version_was_too_loose']} times out of "
        f"{data['checkers']}; the only thing that found it each time was reading every finding",
        "while the list was still short enough to read.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    data = report()
    print(json.dumps(data, indent=2) if args.as_json else render(data))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
