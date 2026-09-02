"""Which of the undefended constants actually reach a published number?

Round eighty-nine counted 49 constants with no stated reason and swept five of them — the five in
`lite_score`, chosen by hand because they were obviously load-bearing. That leaves 44 nobody has
looked at, and no way to tell which of them matter. "Undefended" is a property of the comments;
**"load-bearing" is a property of the code**, and only one of the two can be measured.

This measures it. For each constant: perturb it, re-score the corpus, and record what moved — the
share of documents whose score changed at all, the largest single change, and the change in the
AUROC that this repository publishes. The output is a risk register ordered by measured influence,
so the undefended constants that matter can be told from the undefended constants that do not.

⚠️ **A constant that shows no effect has not been shown to be inert.** Three things make a constant
unreachable by perturbation, and all three look identical to "harmless" in the results:

* it is captured as a **default argument**, bound when the `def` executed and unaffected by a later
  change to the module global;
* it is read at **import time** into another structure — a compiled regex, a frozen set, a dataclass
  default — which is not rebuilt;
* it only affects a path this corpus never takes.

The first two are detectable statically and are reported as `unreachable_by_perturbation` rather
than as zeros, because a zero that means "we could not test this" and a zero that means "this does
not matter" are the same number and opposite facts. The third is why the corpus is named in the
output.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import json
from contextlib import contextmanager
from pathlib import Path

from eval.constant_census import named_constants
from eval.constant_sensitivity import auroc, build_arms

REPO = Path(__file__).resolve().parent.parent


def default_argument_captures(root: Path = REPO) -> set[tuple[str, str]]:
    """(module path, constant name) pairs used as a function's default argument value.

    A default is evaluated once, when the `def` statement runs. Rebinding the module global
    afterwards does not reach it, so perturbing such a constant measures nothing and reports zero —
    which is indistinguishable from the constant being harmless unless it is flagged here.
    """
    found: set[tuple[str, str]] = set()
    for package in ("untell", "eval"):
        for path in sorted((root / package).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            relative = str(path.relative_to(root))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                defaults = list(node.args.defaults) + [
                    d for d in node.args.kw_defaults if d is not None]
                for default in defaults:
                    for inner in ast.walk(default):
                        if isinstance(inner, ast.Name):
                            found.add((relative, inner.id))
    return found


def import_time_uses(root: Path = REPO) -> set[tuple[str, str]]:
    """(module path, constant name) pairs read at module level after being defined.

    A constant folded into a compiled regex, a frozenset or a dataclass field at import time is
    baked in; the object built from it is never rebuilt, so perturbation cannot reach it either.
    """
    found: set[tuple[str, str]] = set()
    for package in ("untell", "eval"):
        for path in sorted((root / package).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            relative = str(path.relative_to(root))
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Name) and isinstance(inner.ctx, ast.Load) \
                            and inner.id.isupper():
                        found.add((relative, inner.id))
    return found


@contextmanager
def perturbed(module, name: str, value):
    """Rebind one module global, then put it back. Restores even if the scorer raises."""
    original = getattr(module, name)
    setattr(module, name, value)
    try:
        yield
    finally:
        setattr(module, name, original)


def variants(value: float | int) -> list[float | int]:
    """Two perturbations either side, sized to the kind of number.

    Multiplicative for a rate or weight, additive for a small count — halving a window of 2 is a
    different question from halving a threshold of 0.3, and using one rule for both would either
    barely move the counts or destroy the thresholds.
    """
    if isinstance(value, bool):
        return []
    if isinstance(value, int) and abs(value) > 3:
        return [max(1, int(value * 0.5)), int(value * 2)]
    if isinstance(value, int):
        return [value + 1] if value >= 0 else [value - 1]
    if value == 0:
        return [0.05, -0.05]
    return [round(value * 0.8, 6), round(value * 1.25, 6)]


def influence(arms, module_path: str, name: str, value, score) -> dict | None:
    """Re-score both arms with one constant moved, and report what changed."""
    machine, human = arms
    module_name = module_path[:-3].replace("/", ".")
    try:
        module = importlib.import_module(module_name)
    except Exception:  # noqa: BLE001 - an unimportable module is a result, not a crash
        return None
    if not hasattr(module, name):
        return None

    base_m = [score(t) for t in machine]
    base_h = [score(t) for t in human]
    base_auroc = auroc([s for s in base_m if s is not None], [s for s in base_h if s is not None])

    worst_moved = 0.0
    worst_delta = 0.0
    worst_auroc_gap = 0.0
    for variant in variants(value):
        with perturbed(module, name, variant):
            try:
                new_m = [score(t) for t in machine]
                new_h = [score(t) for t in human]
            except Exception:  # noqa: BLE001 - a constant that breaks scoring is maximally live
                return {"file": module_path, "name": name, "value": value,
                        "moved_share": 100.0, "max_score_delta": 1.0, "auroc_delta": 1.0,
                        "note": "perturbing this raised — it is reached, and nothing guards it"}
        pairs = [(a, b) for a, b in zip(base_m + base_h, new_m + new_h)
                 if a is not None and b is not None]
        if not pairs:
            continue
        moved = sum(1 for a, b in pairs if a != b)
        worst_moved = max(worst_moved, 100.0 * moved / len(pairs))
        worst_delta = max([worst_delta, *(abs(a - b) for a, b in pairs)])
        new_auroc = auroc([s for s in new_m if s is not None], [s for s in new_h if s is not None])
        worst_auroc_gap = max(worst_auroc_gap, abs(new_auroc - base_auroc))

    return {"file": module_path, "name": name, "value": value,
            "moved_share": round(worst_moved, 1),
            "max_score_delta": round(worst_delta, 4),
            "auroc_delta": round(worst_auroc_gap, 4),
            "base_auroc": round(base_auroc, 4)}


# A constant known to reach `lite_score`, used to prove the harness works before it reports that
# nothing else does. Justified in the source (so it never appears in the register itself), and
# swept in round eighty-nine, so its influence is already established by another route.
POSITIVE_CONTROL = ("untell/detectors/perplexity_burstiness.py", "_BURST_WEIGHT")


def self_check(arms) -> dict:
    """Can this harness detect a constant it is already known to reach?

    "0 of 35 constants move the score" and "the harness is broken" are the same output. Round
    eighty-eight spent twenty minutes producing `0 scored` from a wrong dictionary key and only
    caught it because zero was implausible; here zero is entirely plausible, so it cannot be the
    thing that raises suspicion. The control runs first and the register refuses to report without
    it.
    """
    from untell.detectors.perplexity_burstiness import _BURST_WEIGHT, lite_score

    result = influence(arms, POSITIVE_CONTROL[0], POSITIVE_CONTROL[1], _BURST_WEIGHT, lite_score)
    if result is None:
        return {"passed": False, "detail": "the control constant could not be imported"}
    passed = result["moved_share"] > 0 and result["max_score_delta"] > 0
    return {"passed": passed, "control": POSITIVE_CONTROL[1], **result}


def register(cache: Path, limit: int | None = None) -> dict:
    """Every undefended constant, ranked by how far it moves the published score.

    The target measurement is `lite_score` over the two arms behind this repository's headline
    AUROC. That is a deliberate narrowing: a constant in the API server's rate limiter is undefended
    and irrelevant to it, and a register that mixed the two would rank by nothing.
    """
    from untell.detectors.perplexity_burstiness import lite_score

    machine, human = build_arms(cache, limit=limit)
    arms = ([t for _, t in machine], [t for _, t in human])

    control = self_check(arms)
    if not control["passed"]:
        return {"self_check": control, "refused": True, "rows": [],
                "note": ("the harness could not detect a constant already known to reach the "
                         "target, so any zero it produced would be meaningless")}

    captures = default_argument_captures()
    import_uses = import_time_uses()
    undefended = [c for c in named_constants() if not c["justified"]]

    rows: list[dict] = []
    unreachable: list[dict] = []
    for entry in undefended:
        key = (entry["file"], entry["name"])
        reasons = []
        if key in captures:
            reasons.append("bound as a function default argument")
        if key in import_uses:
            reasons.append("read at import time into another object")
        if reasons:
            unreachable.append({**entry, "why": "; ".join(reasons)})
            continue
        result = influence(arms, entry["file"], entry["name"], entry["value"], lite_score)
        if result is not None:
            rows.append(result)

    rows.sort(key=lambda r: (-r["auroc_delta"], -r["moved_share"]))
    live = [r for r in rows if r["moved_share"] > 0]
    return {
        "self_check": control,
        "refused": False,
        "corpus": "pre-2022 ACL abstracts (human) against eval/data/generated_abstracts (machine)",
        "target": "untell.detectors.perplexity_burstiness.lite_score",
        "undefended_total": len(undefended),
        "tested": len(rows),
        "unreachable_by_perturbation": unreachable,
        "live": len(live),
        "no_observed_effect": len(rows) - len(live),
        "rows": rows,
    }


def render(report: dict) -> str:
    if report.get("refused"):
        return ("REFUSED: " + report["note"] + "\n"
                + f"control: {report['self_check']}")
    control = report["self_check"]
    lines = [
        f"harness self-check: perturbing {control['control']} moved "
        f"{control['moved_share']:.1f}% of documents (max Δ {control['max_score_delta']:.4f}) — "
        f"the harness can see a live constant.",
        "",
        f"target: {report['target']}",
        f"corpus: {report['corpus']}",
        "",
        f"{report['undefended_total']} undefended constants. "
        f"{len(report['unreachable_by_perturbation'])} cannot be reached by perturbation, "
        f"{report['tested']} were tested.",
        f"Of those tested: {report['live']} move the published score, "
        f"{report['no_observed_effect']} show no effect ON THIS CORPUS.",
        "",
        f"  {'constant':>34} {'value':>10} {'moved':>8} {'max Δ':>8} {'Δ AUROC':>9}",
    ]
    for row in report["rows"]:
        if row["moved_share"] == 0:
            continue
        lines.append(f"  {row['name']:>34} {row['value']:>10} {row['moved_share']:>7.1f}% "
                     f"{row['max_score_delta']:>8.4f} {row['auroc_delta']:>9.4f}")
    lines += [
        "",
        "Unreachable by perturbation — NOT shown to be harmless, only untestable this way:",
    ]
    for entry in report["unreachable_by_perturbation"][:20]:
        lines.append(f"  {entry['file']}:{entry['line']} {entry['name']} — {entry['why']}")
    if len(report["unreachable_by_perturbation"]) > 20:
        lines.append(f"  ... and {len(report['unreachable_by_perturbation']) - 20} more")
    lines += [
        "",
        "A zero in this table means 'no effect observed on this corpus with this target', which is",
        "not the same claim as 'this number does not matter'. The distinction is the whole reason",
        "the unreachable list is printed rather than folded into the zeros.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path(".anthology-cache"))
    parser.add_argument("--limit", type=int, help="cap the human arm for a fast run")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    report = register(args.cache, limit=args.limit)
    print(json.dumps(report, indent=2) if args.as_json else render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
