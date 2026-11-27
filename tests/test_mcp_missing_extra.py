"""`untell-mcp` without the optional `mcp` package says what to install, in one line.

It used to die with a ModuleNotFoundError traceback from inside `_server()` (seen in the full-tier
CI job, which does not install the extra), which reads as a broken install.
"""

from __future__ import annotations

import builtins

from untell import mcp_server


def test_missing_mcp_extra_is_an_install_hint_not_a_traceback(monkeypatch, capsys) -> None:
    real_import = builtins.__import__

    def no_mcp(name, *args, **kwargs):
        if name == "mcp" or name.startswith("mcp."):
            raise ImportError("No module named 'mcp'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_mcp)
    assert mcp_server.main([]) == 2
    err = capsys.readouterr().err
    assert 'pip install "untell[mcp]"' in err
    assert len(err.strip().splitlines()) == 1


def test_list_tools_still_works_without_the_extra(monkeypatch, capsys) -> None:
    real_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", lambda n, *a, **k: (
        (_ for _ in ()).throw(ImportError(n)) if n == "mcp" else real_import(n, *a, **k)))
    assert mcp_server.main(["--list-tools"]) == 0
    assert "brief" in capsys.readouterr().out
