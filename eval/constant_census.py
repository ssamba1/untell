"""How many numbers in this repository did anybody actually choose?

Rounds eighty-six and eighty-seven each found one unchosen parameter under a published claim, swept
it, and reported what moved. Two instances is an anecdote. This counts them.

MEASURED across `untell/` and `eval/`: **104 module-level numeric constants, and 52 of them — half —
carry no stated reason for their value.** Among the undefended are `_NLL_MID`, `_NLL_SCALE`,
`_SPREAD_MID`, `_SPREAD_SCALE` and `_PPL_WEIGHT`: the calibration of the detector every headline
figure in this repository comes from.

⚠️ **And the census's own blind spot is the sharpest finding it produces.** The five numbers that
actually decide the stdlib score are not constants at all — they are literals written into an
expression:

    common_signal = clamp01((common - 0.30) / 0.30)
    burst_signal  = clamp01((0.55 - burst) / 0.55)
    return clamp01(max(rep, 0.6 * burst_signal + 0.4 * common_signal))

A scan of assignments cannot see any of them. So this module looks for both: named constants without
a justification, and bare numeric literals inside the functions that compute a published score. The
second list is short and it is the one that matters.

A "justification" here is deliberately cheap to satisfy — a nearby comment mentioning a measurement,
a round, a paper, a standard, or a reason. The bar is *that someone wrote down why*, not that the
reason is good. A check that demanded more would be argued with; this one can only be answered by
writing the sentence.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Cheap on purpose — see the module docstring. The failure this catches is a number with no stated
# reason anywhere near it, which is the state half this repository's constants were in.
JUSTIFIED = re.compile(
    r"MEASURED|measured|round \w+|because|why |chosen|literature|paper|arXiv|doi|\bn\s*=\s*\d"
    r"|benchmark|calibrat|standard|convention|RFC|spec|protocol|HTTP|default in|upstream"
    r"|fitted|fit\b|held out|held-out|AUROC",
    re.I,
)

# Numbers that are not parameters: array indices, the identity, percentages of a whole, and the
# small integers that appear in every program. Sweeping `2` in `len(x) < 2` is not a research
# question, and a census that flagged it would be ignored within a week.
UNINTERESTING = frozenset({0, 1, 2, -1, 0.5, 10, 100, 1000, 1024})

# Functions whose numeric literals decide a published score. Kept explicit rather than inferred:
# an inline literal is only interesting when the value it feeds is one this repository publishes,
# and a heuristic for "computes a score" would flag every loop bound in the codebase.
SCORING_FUNCTIONS: tuple[tuple[str, str], ...] = (
    ("untell/detectors/perplexity_burstiness.py", "lite_score"),
    ("untell/detectors/perplexity_burstiness.py", "_single_sentence_signal"),
    ("untell/humanness.py", "humanness"),
)


def _comment_context(lines: list[str], lineno: int) -> str:
    """The comment block immediately above a line, plus the line and what follows it."""
    index = lineno - 1
    above: list[str] = []
    cursor = index - 1
    while cursor >= 0 and (lines[cursor].strip().startswith("#") or not lines[cursor].strip()):
        if lines[cursor].strip().startswith("#"):
            above.append(lines[cursor])
        elif above:
            break
        cursor -= 1
    return "\n".join(above) + "\n" + "\n".join(lines[index:index + 4])


def _number(node: ast.expr) -> float | int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) \
            and isinstance(node.operand, ast.Constant) \
            and isinstance(node.operand.value, (int, float)):
        return -node.operand.value
    return None


def named_constants(root: Path = REPO) -> list[dict]:
    """Every module-level numeric constant, and whether anything says why it has that value."""
    out: list[dict] = []
    for package in ("untell", "eval"):
        for path in sorted((root / package).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, ast.AnnAssign):
                    targets = [node.target]
                else:
                    continue
                value = _number(node.value) if node.value is not None else None
                if value is None:
                    continue
                for target in targets:
                    if not isinstance(target, ast.Name) or not target.id.isupper():
                        continue
                    context = _comment_context(lines, node.lineno)
                    out.append({
                        "file": str(path.relative_to(root)),
                        "line": node.lineno,
                        "name": target.id,
                        "value": value,
                        "justified": bool(JUSTIFIED.search(context)),
                    })
    return out


def inline_literals(root: Path = REPO) -> list[dict]:
    """Bare numbers inside the functions that compute a published score.

    These are the ones a census of assignments cannot see, and on the evidence of round eighty-nine
    they are also the ones that decide the answer.
    """
    out: list[dict] = []
    for relative, function in SCORING_FUNCTIONS:
        path = root / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name != function:
                continue
            for inner in ast.walk(node):
                # No structural exemption here beyond UNINTERESTING. An earlier version skipped
                # `ast.Compare` nodes meaning to exclude length guards, and it excluded nothing at
                # all: `ast.walk` yields the Constant inside a comparison as its own node. The
                # branch was dead and the comment said otherwise, which is worse than either.
                value = _number(inner) if isinstance(inner, (ast.Constant, ast.UnaryOp)) else None
                if value is None or value in UNINTERESTING:
                    continue
                # The same justification test the named constants get. The bar is "somebody wrote
                # down why", and where the number is written should not change what is asked of it —
                # an inline sentinel with a reason beside it is no worse than a named one.
                if JUSTIFIED.search(_comment_context(lines, inner.lineno)):
                    continue
                out.append({
                    "file": relative,
                    "function": function,
                    "line": inner.lineno,
                    "value": value,
                })
    return out


def census(root: Path = REPO) -> dict:
    named = named_constants(root)
    inline = inline_literals(root)
    undefended = [c for c in named if not c["justified"]]
    return {
        "named_constants": len(named),
        "named_undefended": len(undefended),
        "undefended_share": round(100.0 * len(undefended) / len(named), 1) if named else 0.0,
        "inline_literals_in_scoring_functions": len(inline),
        "undefended": undefended,
        "inline": inline,
    }


def render(report: dict) -> str:
    lines = [
        f"{report['named_constants']} module-level numeric constants in untell/ and eval/.",
        f"{report['named_undefended']} ({report['undefended_share']}%) carry no stated reason "
        f"for their value.",
        "",
    ]
    for entry in report["undefended"]:
        lines.append(f"  {entry['file']}:{entry['line']}  {entry['name']} = {entry['value']}")
    lines += [
        "",
        f"{report['inline_literals_in_scoring_functions']} bare numeric literal(s) inside the "
        f"functions that compute a published score.",
        "These are invisible to the scan above, and they are the ones that decide the answer:",
        "",
    ]
    for entry in report["inline"]:
        lines.append(f"  {entry['file']}:{entry['line']}  in {entry['function']}()  {entry['value']}")
    lines += [
        "",
        "A justification here is cheap: a nearby comment naming a measurement, a round, a paper, a",
        "standard, or a reason. The bar is that somebody wrote down why — not that the reason is",
        "good. `python -m eval.constant_sensitivity` sweeps the ones under the headline finding.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    report = census()
    print(json.dumps(report, indent=2) if args.as_json else render(report))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
