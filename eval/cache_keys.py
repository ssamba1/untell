"""A cache key that omits something the value depends on returns a plausible wrong answer.

Round ninety-five lost a measurement to this. CPython caches bytecode on `(mtime, size)`; every
mutation the harness makes is a single-character swap, so size is unchanged, and a write inside the
same mtime second left the stale `.pyc` valid. The key was incomplete, the lookup hit, and the
answer was wrong in a way nothing could see — the mutant was scored a survivor and the mutation
score came out low.

That is not a Python quirk, it is the general failure of caching: **the key must name everything the
value depends on.** So this checks every cached function in the repository for it.

The rule is mechanical. A function wrapped in `functools.lru_cache` or `functools.cache` returns the
same value for the same arguments, forever. If its body reads anything that is *not* an argument —
an environment variable, a file, a mutable module global — then two calls with identical arguments
can legitimately deserve different answers, and the cache will not give them.

Three things this does not flag, because each is a deliberate and sound use:

* reading an immutable module constant (a compiled regex, a frozen tuple) — it cannot change;
* a function whose file read is the thing being cached on purpose, where the file is a committed
  artefact that changes only with the code that reads it;
* a cache the code invalidates itself, via `cache_clear()`.

The first is separated by name (upper-case constants are treated as immutable, which this repository
enforces elsewhere); the other two need a human, so they are recorded in an explicit allow-list with
a reason rather than pattern-matched. That is the same shape as round ninety-two's citation triage,
and for the same reason: a finding read once should stay read.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Names whose appearance in a cached function's body means it reads state outside its arguments.
_ENVIRONMENT = {"getenv", "environ"}
_FILESYSTEM = {"read_text", "read_bytes", "open", "load", "loads", "exists", "glob", "iterdir",
               "stat", "listdir"}
_CLOCK = {"time", "now", "today", "monotonic", "utcnow"}
_RANDOM = {"random", "choice", "shuffle", "randrange", "randint", "sample"}

CATEGORIES = (
    ("environment", _ENVIRONMENT),
    ("filesystem", _FILESYSTEM),
    ("clock", _CLOCK),
    ("randomness", _RANDOM),
)


def _is_cache_decorator(node: ast.expr) -> bool:
    """`@lru_cache`, `@lru_cache(...)`, `@cache`, and their `functools.`-qualified forms."""
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Attribute):
        return target.attr in {"lru_cache", "cache"}
    return isinstance(target, ast.Name) and target.id in {"lru_cache", "cache"}


def _reads_outside_arguments(func: ast.FunctionDef, callables: frozenset[str] = frozenset(),
                             ) -> list[dict]:
    """Every read in the body that is not of an argument or an immutable constant."""
    parameters = {a.arg for a in func.args.args} | {a.arg for a in func.args.kwonlyargs}
    if func.args.vararg:
        parameters.add(func.args.vararg.arg)
    if func.args.kwarg:
        parameters.add(func.args.kwarg.arg)

    assigned: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            assigned.add(node.id)

    found: list[dict] = []
    for node in ast.walk(func):
        name = None
        if isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
        if name is None:
            continue
        for category, members in CATEGORIES:
            if name in members:
                found.append({"category": category, "reads": name, "line": node.lineno})
                break

    # A mutable module global the function reads but never assigns. Lower-case only — this
    # repository writes constants in upper case and a constant cannot change under a cache — and
    # NOT a callable: the first version flagged every private helper a cached function calls, which
    # is 5 of 6 findings and all of them false. Calling `_load()` is not reading mutable state; what
    # matters is whether `_load` itself reaches outside, which `_transitive` below follows.
    for node in ast.walk(func):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) \
                and node.id not in parameters and node.id not in assigned \
                and node.id not in callables \
                and node.id.islower() and node.id.startswith("_") \
                and not node.id.startswith("__"):
            found.append({"category": "module state", "reads": node.id, "line": node.lineno})
    return found


def _names_read(func: ast.FunctionDef) -> set[str]:
    """Every bare name this function loads that it did not define — what a test could patch."""
    parameters = {a.arg for a in func.args.args} | {a.arg for a in func.args.kwonlyargs}
    assigned = {n.id for n in ast.walk(func)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    return {n.id for n in ast.walk(func)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
            and n.id not in parameters and n.id not in assigned}


def _calls_in(func: ast.FunctionDef) -> set[str]:
    """Names this function calls directly."""
    return {n.func.id for n in ast.walk(func)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


def cached_functions(root: Path = REPO) -> list[dict]:
    """Every `lru_cache`/`cache`-wrapped function, and what its body reads beyond its arguments."""
    out: list[dict] = []
    for package in ("untell", "eval"):
        for path in sorted((root / package).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            helpers = {n.name: n for n in ast.walk(tree)
                       if isinstance(n, ast.FunctionDef)}
            callables = frozenset(helpers)
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not any(_is_cache_decorator(d) for d in node.decorator_list):
                    continue
                reads = _reads_outside_arguments(node, callables)
                references = _names_read(node)
                # One level of indirection. `_pair_probs` reads nothing itself and calls `_load`,
                # which reads a model off disk — the cache key is then incomplete through a helper
                # rather than directly, and stopping at the first level would call it pure.
                for called in sorted(_calls_in(node) & set(helpers)):
                    for entry in _reads_outside_arguments(helpers[called], callables):
                        reads.append({**entry, "via": called})
                    references |= _names_read(helpers[called]) | {called}
                out.append({
                    "file": str(path.relative_to(root)),
                    "line": node.lineno,
                    "function": node.name,
                    "arguments": [a.arg for a in node.args.args],
                    "reads_outside_arguments": reads,
                    "references": sorted(references),
                    "clears_itself": f"{node.name}.cache_clear" in path.read_text(encoding="utf-8"),
                })
    return out


# Cached functions whose incomplete key has been read and is deliberate. Recorded with a reason
# rather than pattern-matched, on round ninety-two's principle: a finding read once should stay read,
# and a baseline with no reason per entry is a silencing mechanism.
ACCEPTED: dict[str, str] = {
    "untell/scripts/entailment.py:_pair_probs": (
        "`_load` returns the NLI model, which is loaded once per process and immutable "
        "thereafter. The cached value depends on (premise, hypothesis) and on which model is "
        "loaded, and the latter cannot change within a process."
    ),
    "untell/scripts/roles.py:_conditional_pair": (
        "`_load` returns the spaCy pipeline, immutable once loaded; `_stem` is a pure function."
    ),
    "untell/scripts/roles.py:_analyse": (
        "Same pipeline, plus `_connectives` and `_triples`, which are pure over their arguments."
    ),
    "untell/scripts/preserve.py:_spacy_entity_spans_cached": (
        "Delegates to `_spacy_entity_spans_impl`; the `_torch_gated` argument exists precisely so "
        "the torch mode is part of the key, which is the completeness this module checks for."
    ),
    "untell/calibrate.py:_coverage_spread_cached": (
        "`_beta_cdf` and `_beta_quantile` are pure functions of their arguments."
    ),
    "untell/scripts/tells.py:human_base_rates": (
        "The genuine incomplete key, and it is accepted rather than fixed. It takes no arguments "
        "and reads `eval/data/tell_base_rates.json`, a COMMITTED artefact that changes only when "
        "the code reading it changes — so within a process there is nothing for a key to "
        "distinguish. What makes that safe is not the reasoning but the guard: "
        "`tests_that_patch_behind_a_cache` fails if any test patches `_BASE_RATES_PATH` without "
        "calling `human_base_rates.cache_clear()`, which is exactly how the one existing test "
        "already handles it."
    ),
}


def tests_that_patch_behind_a_cache(root: Path = REPO) -> list[dict]:
    """Tests that monkeypatch a module holding a cached function without clearing its cache.

    This is the failure mode the audit above cannot prevent. `human_base_rates` has an empty key and
    reads a committed file; the one test that varies that file calls `cache_clear()` on both sides,
    so it works. **Nothing makes the next one do that.** A test that patches the path and forgets
    gets the previous value, silently, and — because an `lru_cache` outlives the test — poisons
    every later test in the process.

    That is not hypothetical in this repository. `untell/scripts/score.py` carries a comment about
    the same shape: a score cached under one torch mode was read by an env-pinned test under
    another, and **56 assertions failed in one full-suite run** before the mode was added to the key.

    ✗ **The first version flagged any patch of the module and was wrong on its only finding.**
    `tests/test_detectors.py` patches `untell.scripts.tells.score_tells`, which `human_base_rates`
    does not read. I had justified the coarse rule on the grounds that a false alarm costs one added
    line — but the line it would prompt is a `cache_clear()` that clears nothing, which is cargo
    cult, and this repository's own note is that false alarms are how a checker gets ignored.

    Flagged now: a test patches a name the cached function actually references, directly or through
    a helper in the same module, and the test never mentions `cache_clear`.
    """
    # module -> {patchable dotted name -> the cached functions that read it}
    owners: dict[str, dict[str, list[str]]] = {}
    for row in cached_functions(root):
        module = row["file"][:-3].replace("/", ".")
        for name in row["references"]:
            owners.setdefault(module, {}).setdefault(name, []).append(row["function"])

    findings: list[dict] = []
    for path in sorted((root / "tests").glob("test_*.py")):
        try:
            body = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "cache_clear" in body:
            continue
        try:
            tree = ast.parse(body)
        except SyntaxError:
            continue
        patched: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"setattr", "delattr", "setenv", "delenv"}:
                continue
            for argument in node.args:
                if not (isinstance(argument, ast.Constant)
                        and isinstance(argument.value, str)):
                    continue
                for module, names in owners.items():
                    prefix = module + "."
                    if not argument.value.startswith(prefix):
                        continue
                    attribute = argument.value[len(prefix):]
                    if attribute in names:
                        patched.add((module, attribute))
        for module, attribute in sorted(patched):
            findings.append({"test": f"tests/{path.name}", "module": module,
                             "patched": attribute, "cached": owners[module][attribute]})
    return findings


def audit(root: Path = REPO) -> dict:
    """Cached functions whose key may be incomplete, minus the ones already read and accepted."""
    rows = cached_functions(root)
    findings = []
    for row in rows:
        if not row["reads_outside_arguments"]:
            continue
        key = f"{row['file']}:{row['function']}"
        if key in ACCEPTED:
            continue
        findings.append({**row, "key": key})
    return {
        "cached_functions": len(rows),
        "accepted": len(ACCEPTED),
        "findings": findings,
        "patched_without_clearing": tests_that_patch_behind_a_cache(root),
    }


def render(report: dict) -> str:
    lines = [
        f"{report['cached_functions']} cached function(s); {report['accepted']} with an "
        f"incomplete key already read and accepted.",
        "",
    ]
    if not report["findings"]:
        lines.append("No cached function reads state its key does not name.")
    for entry in report["findings"]:
        categories = sorted({r["category"] for r in entry["reads_outside_arguments"]})
        lines.append(f"  {entry['key']}  args={entry['arguments']}  reads {', '.join(categories)}")
        for read in entry["reads_outside_arguments"]:
            where = read.get("via", "directly")
            lines.append(f"      {read['category']:<14} {read['reads']}  ({where})")
    for entry in report.get("patched_without_clearing", []):
        lines.append(f"  {entry['test']} patches {entry['module']}.{entry['patched']} and never "
                     f"clears {', '.join(entry['cached'])} — a stale value outlives the test")
    lines += [
        "",
        "A cache returns the same value for the same arguments forever. If the body reads anything",
        "that is not an argument, two calls deserving different answers will not get them. Either",
        "put it in the key, or record why it cannot change, in ACCEPTED with a reason.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    report = audit()
    print(json.dumps(report, indent=2) if args.as_json else render(report))
    return 1 if report["findings"] or report["patched_without_clearing"] else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
