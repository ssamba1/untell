"""`requires-python = ">=3.9"` and the CI matrix runs 3.9, so PEP 604 has rules here.

Two distinct ways a `X | None` annotation breaks on 3.9, both of which aborted collection for a
combined sixteen test modules on the 3.9 CI job while every other job was green:

1. **A pydantic model field.** `untell/api_server.py` has `from __future__ import annotations`, so
   annotations are strings — and pydantic evaluates them when it builds the model:

       TypeError: Unable to evaluate type annotation '_Style | None'

   Thirteen modules died on this one. The future import does NOT save a field that something
   later calls `get_type_hints` on.

2. **A signature in a module with no future import.** `training/reward.py` had none, so
   `list[str] | None` was evaluated at def time:

       TypeError: unsupported operand type(s) for |: 'types.GenericAlias' and 'NoneType'

These tests run on any version, because both are properties of the SOURCE. A version-gated test
would have been useless here: the whole failure is that the tree is developed on 3.11+, where both
constructs are perfectly legal.
"""

from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _is_pep604(node: ast.expr | None) -> bool:
    return isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr)


def test_no_pydantic_model_field_uses_a_pep604_union():
    """Model fields must be `Optional[X]`; pydantic cannot evaluate the string form on 3.9."""
    tree = ast.parse((ROOT / "untell" / "api_server.py").read_text(encoding="utf-8"))
    offenders = [
        f"{cls.name}.{getattr(stmt.target, 'id', '?')}"
        for cls in ast.walk(tree)
        if isinstance(cls, ast.ClassDef)
        for stmt in cls.body
        if isinstance(stmt, ast.AnnAssign) and _is_pep604(stmt.annotation)
    ]
    assert not offenders, (
        "a pydantic model field uses `X | None`. Python 3.9 cannot evaluate that from a string "
        "annotation, which aborts collection for every module importing api_server. Use "
        "`Optional[X]` with a `noqa: UP045`:\n  " + "\n  ".join(offenders)
    )


def test_every_module_using_pep604_in_a_signature_has_the_future_import():
    """Without `from __future__ import annotations`, `list[str] | None` is evaluated at def time."""
    offenders = []
    for path in sorted((ROOT / "untell").rglob("*.py")) + sorted((ROOT / "training").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        has_future = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
            and any(alias.name == "annotations" for alias in node.names)
            for node in tree.body
        )
        if has_future:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            annotations = [a.annotation for a in node.args.args + node.args.kwonlyargs]
            annotations.append(node.returns)
            if any(_is_pep604(a) for a in annotations):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.name}")
                break
    assert not offenders, (
        "a signature uses `X | None` in a module without `from __future__ import annotations`, so "
        "it is evaluated at def time and raises TypeError on Python 3.9:\n  "
        + "\n  ".join(offenders)
    )


def test_the_checks_can_actually_fail():
    """A sweep matching nothing looks identical to a sweep finding nothing wrong."""
    assert _is_pep604(ast.parse("x: int | None", mode="exec").body[0].annotation)
    assert not _is_pep604(ast.parse("x: Optional[int]", mode="exec").body[0].annotation)
