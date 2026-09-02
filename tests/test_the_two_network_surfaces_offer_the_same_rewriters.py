"""`_FREE_REWRITERS` was written out twice, in the two surfaces that must not disagree.

FOUND by finishing the sweep Result 190 opened. Both comments it examined were about a duplicated
definition, so the mechanical version of that question is: which constants are declared with an
IDENTICAL literal in more than one module? Over the whole package, five:

    _FREE_REWRITERS   api_server.py, mcp_server.py     nine rewriter names
    _LATIN            languages.py, score.py           re.compile('[A-Za-z]')
    _NUM              llm_judge.py, local_judge.py     re.compile(r'\\d*\\.\\d+|\\d+')
    _WORD             tells.py, voice.py               re.compile("[A-Za-z0-9']+")
    _WORD_RE          humanness.py, structural.py      re.compile("[A-Za-z']+")

Four are two-character regexes whose drift would be visible immediately. The fifth is a VOCABULARY,
duplicated across the REST server and the MCP server — the two surfaces a caller reaches without
touching the CLI — and this repository has already shipped that exact failure once: the MCP docstring
carried six of the fourteen style names, so eight styles were invisible to every MCP caller.

MEASURED: the two sets were byte-identical, nine names each. No drift. The guard was for the next
rewriter added to one file and not the other, which would leave REST and MCP disagreeing about what
is free — silently, because each is internally consistent.

CONSOLIDATED 2026-09-01, and the objection this file used to record is worth keeping because it was
correct. It read: "Not consolidated into a shared import: CI installs the MCP path as `.[dev,mcp]`
with no FastAPI, so importing the REST module to reach its constant would put a web framework on the
MCP server's import path to save nine strings." That is true of `mcp_server` importing `api_server`,
and it is why the shared definition lives in neither of them. `untell/_rewriters.py` imports nothing
at all, so each surface reaches the constant without acquiring the other's dependencies — which is
also what let a test that checks nothing but a set of strings stop being a collection error on the
zero-dependency install.

So the drift these tests guard is now structurally impossible, and they check that instead: that
the literal is declared exactly once, and that both surfaces alias it rather than growing a copy.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SURFACES = ("untell/api_server.py", "untell/mcp_server.py")
SHARED = "untell/_rewriters.py"


def _assignment(rel: str, name: str) -> ast.expr:
    """The right-hand side of a module-level assignment, read from SOURCE rather than imported.

    Importing `api_server` needs FastAPI, which the MCP-only install does not have, and these tests
    are about what the files say — a question the text answers without either being importable.
    """
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return node.value
    raise AssertionError(f"{rel} has no module-level {name}")


def _literal_set(rel: str, name: str) -> set[str]:
    value = ast.unparse(_assignment(rel, name))
    return set(ast.literal_eval(value.replace("frozenset(", "", 1)[:-1]))


@pytest.fixture(scope="module")
def shared() -> set[str]:
    return _literal_set(SHARED, "FREE_REWRITERS")


def test_the_shared_module_declares_the_constant(shared) -> None:
    """The premise. A renamed constant would make everything below vacuous rather than failing."""
    assert shared, SHARED
    assert len(shared) >= 9, shared


def test_neither_surface_carries_its_own_copy(shared) -> None:
    """The drift guard, now structural: each surface must ALIAS the shared name, not restate it.

    A future edit pasting the literal back into either file would restore exactly the failure this
    file was written for — REST and MCP disagreeing about what is free, each internally consistent.
    """
    for rel in SURFACES:
        value = _assignment(rel, "_FREE_REWRITERS")
        assert isinstance(value, ast.Name), (
            f"{rel} declares its own _FREE_REWRITERS again instead of aliasing "
            f"{SHARED}: {ast.unparse(value)[:80]}"
        )
        assert value.id == "FREE_REWRITERS", ast.unparse(value)


def test_the_shared_module_needs_no_dependencies() -> None:
    """Why the constant lives in a third module rather than in either server.

    The objection this file recorded against consolidating — that reaching the REST module's
    constant would put FastAPI on the MCP server's import path — is answered only while the shared
    module imports nothing beyond `__future__`.
    """
    tree = ast.parse((ROOT / SHARED).read_text(encoding="utf-8"))
    imports = [ast.unparse(n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert imports == ["from __future__ import annotations"], imports


def test_every_offered_rewriter_is_one_the_cli_accepts(shared) -> None:
    """The deeper property. Two files can agree on a name that no rewriter answers to — the same
    shape as a style name with no profile, which every surface accepts and silently ignores."""
    import untell.scripts.run as run

    source = pathlib.Path(run.__file__).read_text(encoding="utf-8")
    accepted = set()
    for tree in (ast.parse(source),):
        for node in ast.walk(tree):
            if isinstance(node, ast.List) and all(
                isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts
            ):
                values = {e.value for e in node.elts}
                if "structural" in values and "composite" in values:
                    accepted |= values
    assert accepted, "could not find the --rewriter choices in run.py"
    unknown = shared - accepted
    assert not unknown, f"offered by the network surfaces but not a rewriter the CLI knows: {unknown}"
