"""`_FREE_REWRITERS` is written out twice, in the two surfaces that must not disagree.

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

MEASURED: the two sets are byte-identical today, nine names each. No drift. The guard is for the next
rewriter added to one file and not the other, which would leave REST and MCP disagreeing about what
is free — silently, because each is internally consistent.

Not consolidated into a shared import: CI installs the MCP path as `.[dev,mcp]` with no FastAPI, so
importing the REST module to reach its constant would put a web framework on the MCP server's import
path to save nine strings.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SURFACES = ("untell/api_server.py", "untell/mcp_server.py")


def _literal_set(rel: str, name: str) -> set[str]:
    """Read the constant out of the SOURCE rather than importing it.

    Importing `api_server` needs FastAPI, which the MCP-only install does not have, and this test is
    about two files agreeing — a question the text answers without either module being importable.
    """
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return set(ast.literal_eval(ast.unparse(node.value).replace("frozenset(", "", 1)[:-1]))
    raise AssertionError(f"{rel} has no module-level {name}")


@pytest.fixture(scope="module")
def sets() -> dict[str, set[str]]:
    return {rel: _literal_set(rel, "_FREE_REWRITERS") for rel in SURFACES}


def test_both_surfaces_declare_the_constant(sets) -> None:
    """The premise. A renamed constant would make the comparison below vacuous rather than failing,
    and `_literal_set` raises instead — this states it as its own assertion."""
    for rel, names in sets.items():
        assert names, rel


def test_the_two_surfaces_offer_the_same_rewriters(sets) -> None:
    rest, mcp = sets["untell/api_server.py"], sets["untell/mcp_server.py"]
    assert rest == mcp, {"only in REST": sorted(rest - mcp), "only in MCP": sorted(mcp - rest)}


def test_every_offered_rewriter_is_one_the_cli_accepts(sets) -> None:
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
    unknown = sets["untell/mcp_server.py"] - accepted
    assert not unknown, f"offered by the network surfaces but not a rewriter the CLI knows: {unknown}"
