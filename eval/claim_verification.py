"""Attribution says somebody named a source. This asks whether the source contains the number.

`untell-audit` enforces that every bolded figure in these documents carries a stated provenance —
a `MEASURED` marker, a reproduction command, an `n = `. MEASURED at round ninety-one: **1,045 claims
pass that check.** It is a real guard and it has caught real defects, and it is strictly weaker than
it sounds, because *naming* a source and *agreeing with* it are different properties.

Round eighty-four is the proof. A published AUROC of 0.3538 carried a reproduction command that
printed 0.3529. The claim was attributed, the attribution named the right tool, and the number was
still not the one the tool produced. That was found by reading, one figure at a time.

This finds them mechanically. Nine artefacts are now committed under `eval/data/` — the survey
counts, both filter sweeps, the register-conformity rows and report, the constant census, the
calibration sweep, the influence register, the tell base rates. Together they hold the numbers this
repository argues from in machine-readable form. So: take each bolded figure in a document, work out
which artefact its surrounding prose points at, and check whether that artefact contains it.

✗ **The obvious design does not work, and the failure is structural rather than fixable.** The first
version linked a figure to an artefact by proximity — if the prose near a number names a tool, the
number should be in that tool's output — and it reported 15 contradictions of which **every one was
false**. Two rounds of narrowing the scope (900 characters, then the paragraph, then the table row)
changed nothing, because the premise is simply untrue: a sentence may legitimately name a tool and
quote a figure from somewhere else, and `ROADMAP.md` row 33 does exactly that. **No amount of
tightening rescues a rule that is false.** It is recorded here rather than deleted because the next
person to have this idea should find it already tried.

What works is the opposite direction. Rather than guessing which artefact a number came from, an
explicit registry names the artefact key behind each headline figure and checks that the documents
still agree with it. The mapping is curated, so there are no false positives at all; the cost is
that it covers the figures somebody listed rather than every figure in the repository. That is the
correct trade for a check meant to gate a commit — this repository's own comment on the matter is
that "false alarms are how a checker gets ignored".

This is the round-eighty-four defect made mechanical: a published AUROC of 0.3538 whose own
reproduction command printed 0.3529. Attributed, correctly attributed, and still not the number the
tool produced.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "eval" / "data"

# Which artefact a mention points at. Keys are what a document actually writes — a module path, a
# CLI flag, or the artefact's own filename — because the prose was written for readers, not for this.

@dataclass(frozen=True)
class Claim:
    """One published figure, and the artefact key it must keep agreeing with.

    `path` walks the decoded artefact. `render` is how the documents write it — the check is a
    string search, because a number that has drifted usually drifts in the prose while the artefact
    stays right, and comparing renderings is what catches that.
    """

    artefact: str
    path: tuple
    render: str
    documents: tuple[str, ...]
    note: str = ""


# The figures this repository leads with. Adding a row here is how a new headline becomes checkable;
# the check fails loudly if the artefact moves and the prose does not, which is the whole point.
CLAIMS: tuple[Claim, ...] = (
    Claim("detection_power.json", ("auroc",), "0.3529", ("docs/index.md",),
          "the inversion, and the figure round 84 corrected from 0.3538"),
    Claim("detection_power.json", ("matched", "machine", "rate"), "10.7%", ("docs/index.md",)),
    Claim("detection_power.json", ("matched", "human", "rate"), "30.4%", ("docs/index.md",)),
    Claim("detection_power.json", ("matched", "human", "n"), "634", ()),
    Claim("survey_counts.json", ("abstracts",), "46,905", ("docs/index.md",)),
    Claim("survey_counts.json", ("detection_papers",), "612", ()),
    Claim("survey_counts.json", ("volumes",), "186", ("docs/index.md",)),
    Claim("survey_counts.json", ("topics", "robustness/paraphrase"), "157", ("docs/index.md",)),
    Claim("survey_counts.json", ("topics", "false positives/accusation"), "13",
          ("docs/index.md",)),
    Claim("window_sweep.json", ("largest_share_move",), "4.3", ("docs/index.md", "ROADMAP.md")),
    Claim("window_sweep.json", ("saturates", "false positives/accusation", "papers_entering_after"),
          "192", ("docs/index.md", "ROADMAP.md")),
    Claim("topic_sweep.json", ("ratio_min",), "7.5", ("docs/index.md", "ROADMAP.md")),
    Claim("topic_sweep.json", ("ratio_max",), "14.2", ("docs/index.md", "ROADMAP.md")),
    Claim("register_conformity.json", ("rho_prototypicality_score",), "0.0586",
          ("docs/index.md", "ROADMAP.md")),
    Claim("register_conformity.json", ("scored",), "6,841", ("docs/index.md", "ROADMAP.md")),
    Claim("constant_census.json", ("named_constants",), "111", ("docs/index.md", "ROADMAP.md")),
    Claim("constant_census.json", ("named_undefended",), "41", ("docs/index.md", "ROADMAP.md")),
    Claim("constant_influence.json", ("self_check", "moved_share"), "99.6%",
          ("docs/index.md", "ROADMAP.md")),
    Claim("constant_influence.json", ("tested",), "35", ("docs/index.md", "ROADMAP.md")),
)


def _at(obj, path: tuple):
    for step in path:
        obj = obj[step]
    return obj


def _renders_as(value, render: str) -> bool:
    """Does `value` write as `render`, allowing for percentages and thousands separators?"""
    target = render.replace(",", "").rstrip("%x")
    try:
        wanted = float(target)
    except ValueError:
        return False
    decimals = len(target.split(".")[1]) if "." in target else 0
    candidates = [float(value)]
    if render.endswith("%"):
        candidates.append(float(value) * 100.0)
    return any(round(c, decimals) == round(wanted, decimals) for c in candidates)


def check(root: Path = REPO) -> dict:
    """Every registered headline figure, against its artefact and against the documents."""
    verified: list[dict] = []
    drifted: list[dict] = []
    missing: list[dict] = []

    for claim in CLAIMS:
        path = DATA / claim.artefact
        if not path.exists():
            missing.append({"artefact": claim.artefact, "why": "artefact not committed"})
            continue
        try:
            value = _at(json.loads(path.read_text()), claim.path)
        except (KeyError, IndexError, TypeError):
            missing.append({"artefact": claim.artefact, "path": list(claim.path),
                            "why": "key not present in the artefact"})
            continue

        entry = {"artefact": claim.artefact, "path": list(claim.path),
                 "render": claim.render, "value": value, "note": claim.note}
        if not _renders_as(value, claim.render):
            drifted.append({**entry, "why": "the artefact no longer produces this figure"})
            continue

        absent = [
            document for document in claim.documents
            if claim.render not in (root / document).read_text(encoding="utf-8")
        ]
        if absent:
            drifted.append({**entry, "why": f"not stated in {', '.join(absent)}"})
        else:
            verified.append(entry)

    return {
        "registered": len(CLAIMS),
        "verified": len(verified),
        "drifted": len(drifted),
        "unverifiable": len(missing),
        "drift": drifted,
        "unverifiable_detail": missing,
    }


def render(report: dict) -> str:
    lines = [
        f"{report['registered']} registered headline figure(s).",
        f"  verified     {report['verified']}",
        f"  DRIFTED      {report['drifted']}",
        f"  unverifiable {report['unverifiable']}",
        "",
    ]
    for entry in report["drift"]:
        lines.append(f"  {entry['artefact']}{list(entry['path'])}: documents say "
                     f"{entry['render']}, artefact holds {entry['value']} — {entry['why']}")
    for entry in report["unverifiable_detail"]:
        lines.append(f"  {entry['artefact']}: {entry['why']}")
    if not report["drift"] and not report["unverifiable_detail"]:
        lines.append("Every registered figure matches its artefact and is stated where it should be.")
    lines += [
        "",
        "Coverage is what somebody registered, not every figure in the repository. That is",
        "deliberate: the proximity-based version covered everything and was wrong 15 times out of",
        "15. See this module's docstring.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    report = check()
    print(json.dumps(report, indent=2) if args.as_json else render(report))
    return 1 if report["drift"] or report["unverifiable_detail"] else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
