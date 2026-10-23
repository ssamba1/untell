from __future__ import annotations

import importlib.util
import sys

import pytest

from untell.rewriter.local_policy import LocalPolicyRewriter

# These isolate a missing `peft` with torch and transformers PRESENT. With them absent too, the
# reason correctly names all three packages and recommends untell[full,train] instead.
needs_model_stack = pytest.mark.skipif(
    not (
        importlib.util.find_spec("torch") is not None
        and importlib.util.find_spec("transformers") is not None
    ),
    reason="needs the [full] extra",
)


@needs_model_stack
def test_unavailable_reason_names_the_missing_extra_when_peft_is_absent(monkeypatch, tmp_path) -> None:
    """A missing optional dep must yield a clean reason naming the package + extra + command,
    never raise the raw ModuleNotFoundError the unguarded import used to leak (issue #34)."""
    (tmp_path / "adapter_config.json").write_text("{}")
    monkeypatch.setitem(sys.modules, "peft", None)
    rw = LocalPolicyRewriter(adapter_dir=str(tmp_path), use_adapter=True)
    reason = rw.unavailable_reason()
    assert reason is not None
    assert "peft" in reason
    assert "'untell[train]'" in reason


@needs_model_stack
def test_unavailable_reason_none_for_base_only_rewriter(monkeypatch) -> None:
    """base-only (use_adapter=False) needs no peft, so its reason is not about peft."""
    monkeypatch.setitem(sys.modules, "peft", None)
    rw = LocalPolicyRewriter(use_adapter=False)
    reason = rw.unavailable_reason()
    # torch/transformers are present in this env, so the only possible reason is None.
    assert reason is None, reason


def test_dep_hints_cover_the_load_path() -> None:
    from untell.rewriter.local_policy import _MISSING_DEP_HINTS

    for dep in ("torch", "transformers"):
        assert dep in _MISSING_DEP_HINTS
        assert "pip install 'untell[" in _MISSING_DEP_HINTS[dep]
