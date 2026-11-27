from __future__ import annotations

import sys
import types

import pytest

from untell.rewriter.local_policy import LocalPolicyRewriter


def _deps(monkeypatch, **present: bool) -> None:
    """Pin which of torch/transformers/peft import, whatever this environment has installed.

    ``unavailable_reason`` only probes the imports, so a stand-in module counts as installed and
    ``None`` in ``sys.modules`` makes ``import`` raise — the message is then the same on the lite
    tier (none of the three installed) and the full one.
    """
    for name, ok in present.items():
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name) if ok else None)


def test_unavailable_reason_names_the_missing_extra_when_peft_is_absent(monkeypatch, tmp_path) -> None:
    """A missing optional dep must yield a clean reason naming the package + extra + command,
    never raise the raw ModuleNotFoundError the unguarded import used to leak (issue #34)."""
    (tmp_path / "adapter_config.json").write_text("{}")
    _deps(monkeypatch, torch=True, transformers=True, peft=False)
    rw = LocalPolicyRewriter(adapter_dir=str(tmp_path), use_adapter=True)
    reason = rw.unavailable_reason()
    assert reason is not None
    assert "needs the 'peft' package" in reason
    assert "'untell[train]'" in reason


def test_unavailable_reason_none_for_base_only_rewriter(monkeypatch) -> None:
    """base-only (use_adapter=False) needs no peft, so its reason is not about peft."""
    _deps(monkeypatch, torch=True, transformers=True, peft=False)
    rw = LocalPolicyRewriter(use_adapter=False)
    assert rw.unavailable_reason() is None


@pytest.mark.parametrize(
    "use_adapter,expected",
    [
        # base-only needs no peft, so the hint must not drag in the `train` extra.
        (False, "'torch', 'transformers' packages, none of which are installed: "
                "pip install 'untell[full]'"),
        (True, "'torch', 'transformers', 'peft' packages, none of which are installed: "
               "pip install 'untell[full,train]'"),
    ],
)
def test_unavailable_reason_names_every_missing_package_and_only_their_extras(
    monkeypatch, tmp_path, use_adapter, expected
) -> None:
    """The lite-tier case: several deps missing at once."""
    (tmp_path / "adapter_config.json").write_text("{}")
    _deps(monkeypatch, torch=False, transformers=False, peft=False)
    rw = LocalPolicyRewriter(adapter_dir=str(tmp_path), use_adapter=use_adapter)
    assert expected in rw.unavailable_reason()


def test_dep_hints_cover_the_load_path() -> None:
    from untell.rewriter.local_policy import _MISSING_DEP_HINTS

    for dep in ("torch", "transformers"):
        assert dep in _MISSING_DEP_HINTS
        assert "pip install 'untell[" in _MISSING_DEP_HINTS[dep]
