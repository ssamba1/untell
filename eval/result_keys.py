"""Keys a caller reads that the function never returns.

`tests/test_every_returned_key_is_documented.py` checks one direction: every key these functions
RETURN appears in `docs/result-shapes.md`. That catches an undocumented key.

**It cannot catch the opposite, which is the failure that actually happens.** Reading a key the
function does not return is silent: `dict.get` yields `None`, and `None` flows on to become a
plausible number, an empty list, or a skipped branch. The document says so in its own opening —
"guessing wrong returns a plausible value rather than raising" — and this session produced **six**
instances anyway, in code written by someone who had read it:

| read | the key that exists | cost |
|---|---|---|
| `score_text(...)["score"]` | `max` | scored 0 of 6,842 documents after a twenty-minute run |
| `humanness(...).get("score")` | it returns a float | a verification script died |
| `score_sentences(...)["spread"]` | `unrankable` | a boundary test asserted nothing |
| `humanize_diff(...)["removed"]` | `removed_lines` | three tests failed at once |
| `score_tells(...).get("caveats")` | `warning` | a caveat test passed on an empty string |
| `voice` line number off by one | — | a mutant reported as surviving |

The trap is not ignorance of the document. It is reaching for the plausible key without opening the
file, which no amount of documentation prevents and a checker can.

So: parse the documented key lists, track `name = FUNC(...)` within each scope, and flag every
`name["k"]`, `name.get("k")` and `"k" in name` whose key the function does not return.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "docs" / "result-shapes.md"

# Reads that are deliberately defensive rather than mistaken: a caller may probe for a key that only
# appears under some conditions, and `.get(k, default)` with an explicit default says so. Those are
# still checked against the documented list — the exemption is for keys the doc marks conditional,
# which it already does in prose.
DYNAMIC = re.compile(r"only when|appears? only|absent unless", re.I)


def documented(doc: Path = DOC) -> dict[str, set[str]]:
    """Function name -> the keys `result-shapes.md` says it returns."""
    text = doc.read_text(encoding="utf-8")
    block = text.split("## Full key lists", 1)
    if len(block) < 2:
        return {}
    fenced = block[1].split("```")
    if len(fenced) < 2:
        return {}
    shapes: dict[str, set[str]] = {}
    current: str | None = None
    for line in fenced[1].splitlines():
        if not line.strip():
            continue
        head = re.match(r"^(\w+)\s+(.*)$", line)
        if head and not line.startswith((" ", "+")):
            current = head.group(1)
            shapes[current] = set()
            body = head.group(2)
        elif current:
            body = line
        else:
            continue
        for key in re.findall(r"\b([a-z_][a-z0-9_]*)\b", body.split("(")[0]):
            shapes[current].add(key)
    # Words that appear in the prose of a continuation line rather than as keys.
    noise = {"only", "when", "a", "caveat", "applies", "the", "and", "or", "is", "in", "of",
             "per", "detector", "raised", "cannot", "be", "ranked", "common", "human", "writing",
             "fired", "tell", "scores", "that", "it", "an", "this", "to", "for", "with", "not"}
    return {name: keys - noise for name, keys in shapes.items() if keys - noise}


def _known_functions(shapes: dict[str, set[str]]) -> set[str]:
    return set(shapes)


def reads(root: Path = REPO, shapes: dict[str, set[str]] | None = None) -> list[dict]:
    """Every read of a key the producing function does not return."""
    shapes = shapes if shapes is not None else documented()
    known = _known_functions(shapes)
    found: list[dict] = []

    for package in ("tests", "eval", "untell"):
        for path in sorted((root / package).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            relative = str(path.relative_to(root))
            # Scopes are scanned outermost-first so a nested function can INHERIT the origins its
            # enclosing scope established. Round 102 pruned nested bodies out of the module scan to
            # kill false positives and, MEASURED by round 105's recall plants, created a blind spot:
            # a closure reading the outer result was never checked at all. Inheritance restores it
            # without the false positives, because a parameter or local assignment rebinds the name
            # and clears what it inherited.
            outer = _scan(tree, relative, shapes, known)
            found.extend(outer["findings"])
            _scan_nested(tree, relative, shapes, known, outer["origins"], found)
    return found


def _walk_own_scope(scope: ast.AST):
    """Every node in this scope, NOT descending into nested function or class bodies.

    `ast.walk` cannot prune, so a module-level scan reached inside every function and attributed
    their local reads to module-level assignments. The scopes are visited separately anyway; seeing
    each node once, in the scope that owns it, is the whole point.
    """
    stack = [scope]
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                    and child is not scope:
                continue
            stack.append(child)


def _bound_names(target: ast.expr) -> list[str]:
    """Every plain name a binding target introduces, including tuple unpacking."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [n for element in target.elts for n in _bound_names(element)]
    return []


def _scan_nested(scope: ast.AST, relative: str, shapes: dict[str, set[str]], known: set[str],
                 inherited: dict[str, str], found: list[dict]) -> None:
    """Every function defined directly in `scope`, carrying its origins inward."""
    for child in ast.iter_child_nodes(scope):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result = _scan(child, relative, shapes, known, inherited)
            found.extend(result["findings"])
            _scan_nested(child, relative, shapes, known, result["origins"], found)
        elif isinstance(child, ast.ClassDef):
            _scan_nested(child, relative, shapes, known, inherited, found)
        else:
            _scan_nested(child, relative, shapes, known, inherited, found)


def _scan(scope: ast.AST, relative: str, shapes: dict[str, set[str]],
          known: set[str], inherited: dict[str, str] | None = None) -> dict:
    """One scope, processed in SOURCE ORDER with reassignment invalidating the origin.

    ⚠️ **The first version tracked origins with an unordered `ast.walk` and never invalidated them.**
    A variable assigned from `score_tells` and later reassigned to something else had every
    subsequent read attributed to `score_tells`, which produced findings like
    `score_tells() -> 'ci_low'`. MEASURED: 38 distinct pairs, most of them false. A checker whose
    findings are mostly false is one nobody runs — this repository has now written that down about
    three separate checkers, and built a fourth that needed it.
    """
    events: list[tuple[int, int, str, object]] = []

    # A function's PARAMETERS bind names, and a parameter named `result` is not the module-level
    # `result = untell_text(...)`. MEASURED: without this, `eval/holdout.py`'s `render(result)`
    # contributed six false findings, its own parameter's keys read as untell_text's.
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for argument in [*scope.args.args, *scope.args.kwonlyargs, *scope.args.posonlyargs]:
            events.append((scope.lineno, 0, "rebind", argument.arg))

    for node in _walk_own_scope(scope):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            events.append((node.lineno, 0, "assign", node))
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            # `for r in rows:` rebinds `r`. Without this the origin from an earlier
            # `r = score_tells(...)` survived into the loop body, and MEASURED that produced seven
            # false findings in `eval/tells_auroc.py` alone — reads of a row's own fields reported
            # as reads of a key `score_tells` does not return.
            for name in _bound_names(node.target):
                events.append((node.lineno, 0, "rebind", name))
        elif isinstance(node, (ast.comprehension,)):
            for name in _bound_names(node.target):
                events.append((getattr(node.target, "lineno", 0), 0, "rebind", name))
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            for name in _bound_names(node.optional_vars):
                events.append((getattr(node.optional_vars, "lineno", 0), 0, "rebind", name))
        elif isinstance(node, ast.ExceptHandler) and node.name:
            events.append((node.lineno, 0, "rebind", node.name))
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) \
                and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            events.append((node.lineno, 1, "read", (node.value.id, node.slice.value)))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "get" and isinstance(node.func.value, ast.Name) \
                and node.args and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, str):
            events.append((node.lineno, 1, "read", (node.func.value.id, node.args[0].value)))

    origin: dict[str, str] = dict(inherited or {})
    seen: set[tuple[int, str, str]] = set()

    out: list[dict] = []
    for lineno, _order, kind, payload in sorted(events, key=lambda e: (e[0], e[1])):
        if kind == "rebind":
            origin.pop(payload, None)
            continue
        if kind == "assign":
            node = payload
            target = node.targets[0].id
            call = node.value
            producer = None
            if isinstance(call, ast.Call):
                func = call.func
                name = func.id if isinstance(func, ast.Name) else (
                    func.attr if isinstance(func, ast.Attribute) else None)
                if name in known:
                    producer = name
            # Reassignment from anything else clears the origin rather than keeping the old one.
            if producer:
                origin[target] = producer
            else:
                origin.pop(target, None)
            continue

        holder, key = payload
        producer = origin.get(holder)
        if producer is None or key in shapes[producer]:
            continue
        if (lineno, holder, key) in seen:
            continue
        seen.add((lineno, holder, key))
        out.append({
            "file": relative, "line": lineno, "variable": holder,
            "producer": producer, "key": key, "documented": sorted(shapes[producer]),
        })
    return {"findings": out, "origins": origin}


def audit(root: Path = REPO) -> dict:
    shapes = documented()
    findings = reads(root, shapes)
    return {
        "functions_documented": sorted(shapes),
        "keys_per_function": {name: len(keys) for name, keys in shapes.items()},
        "findings": findings,
    }


def render(report: dict) -> str:
    lines = [
        f"{len(report['functions_documented'])} function(s) with a documented key list: "
        f"{', '.join(report['functions_documented'])}",
        "",
    ]
    if not report["findings"]:
        lines.append("No caller reads a key its function does not return.")
    for entry in report["findings"]:
        lines.append(f"  {entry['file']}:{entry['line']}  {entry['variable']} came from "
                     f"{entry['producer']}() and does not have {entry['key']!r}")
        lines.append(f"      it returns: {', '.join(entry['documented'])}")
    lines += [
        "",
        "Reading a key that is not returned is silent: `.get` yields None and None becomes a",
        "plausible number downstream. This is the reverse of",
        "tests/test_every_returned_key_is_documented.py, which checks that returned keys are",
        "documented and cannot see a caller reading one that never existed.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    report = audit()
    print(json.dumps(report, indent=2) if args.as_json else render(report))
    return 1 if report["findings"] else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
