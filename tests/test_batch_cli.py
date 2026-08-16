"""Tests for `untell batch <dir>` — directory-tree humanization.

The heavy per-file loop (`untell.scripts.run.untell_text`) is stubbed in the
unit tests so the orchestration — walk, binary/empty skip, structure mirror,
manifest, summary, exit codes — is asserted in milliseconds instead of seconds.
One integration test runs the real loop on the lite tier to prove the wiring
end to end.
"""

from __future__ import annotations

import json

import pytest

from untell.scripts import batch as batch_mod
from untell.scripts.batch import main

# The real loop, captured before the autouse fixture stubs it — the integration
# test at the bottom restores it to prove the wiring end to end.
_REAL_UNT_ELL_TEXT = batch_mod.untell_text


def _fake_result(text: str = "", final: str = "humanized output",
                 changed: bool = True, pre_max: float = 0.7,
                 post_max: float = 0.2, iterations: int = 2, **kwargs) -> dict:
    """A canned `untell_text` result with the keys batch reads.

    The first positional argument is the input text (the loop receives it
    first); everything else comes by keyword. ``**kwargs`` absorbs the rest of
    the loop's real call signature so the stub is drop-in.
    """
    return {
        "final": final,
        "changed": changed,
        "iterations": iterations,
        "pre": {"max": pre_max, "mean": pre_max, "flagged": True, "tier": "lite"},
        "post": {"max": post_max, "mean": post_max, "flagged": False, "tier": "lite"},
    }


@pytest.fixture
def tree(tmp_path):
    """A small tree: one md, one txt in a subdir, a binary .txt, an empty .md."""
    (tmp_path / "a.md").write_text(
        "Furthermore, artificial intelligence has fundamentally transformed "
        "numerous industries. Moreover, organizations increasingly leverage "
        "these technologies.",
        encoding="utf-8",
    )
    (tmp_path / "b.txt").write_text(
        "This is a plain note with simple words about ordinary things.",
        encoding="utf-8",
    )
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.md").write_text(
        "In addition, it is important to note that the proposed methodology "
        "offers a robust and comprehensive framework.",
        encoding="utf-8",
    )
    (tmp_path / "pic.png.txt").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    (tmp_path / "empty.md").write_text("", encoding="utf-8")
    return tmp_path


@pytest.fixture(autouse=True)
def _fast_rewriter(monkeypatch):
    """Stub the loop for unit tests; integration test opts out explicitly."""
    monkeypatch.setattr(batch_mod, "untell_text", _fake_result)


def test_walk_finds_txt_and_md_recursively_sorted(tree):
    root = tree
    files = batch_mod._walk_inputs(root, root.parent / "out")
    rels = [str(p.relative_to(root.resolve())).replace("\\", "/") for p in files]
    assert rels == ["a.md", "b.txt", "empty.md", "pic.png.txt", "sub/c.md"]


def test_walk_excludes_output_dir_inside_input(tree):
    out = tree / "out"
    files = batch_mod._walk_inputs(tree, out)
    rels = [str(p.relative_to(tree.resolve())).replace("\\", "/") for p in files]
    assert rels == ["a.md", "b.txt", "empty.md", "pic.png.txt", "sub/c.md"]
    # put a .md inside the future output dir; it must not be picked up
    (out / "sub").mkdir(parents=True)
    (out / "sub" / "old.md").write_text("previously humanized", encoding="utf-8")
    files = batch_mod._walk_inputs(tree, out)
    rels = [str(p.relative_to(tree.resolve())).replace("\\", "/") for p in files]
    assert "out/sub/old.md" not in rels


def test_looks_binary_detects_nul_and_accepts_utf16_bom(tmp_path):
    nul = tmp_path / "nul.bin"
    nul.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\r")
    assert batch_mod._looks_binary(nul) is True
    # A UTF-16 file is full of NUL bytes but is TEXT; the BOM must save it.
    utf16 = tmp_path / "u16.md"
    utf16.write_bytes("\ufeffcafé".encode("utf-16"))
    assert batch_mod._looks_binary(utf16) is False


def test_process_one_ok_entry(tree):
    entry = batch_mod._process_one(
        tree / "a.md", tree, tree.parent / "out",
        rewriter=object(), tier="lite", threshold=0.3,
        max_iters=5, best_of=3, dry_run=False,
    )
    assert entry["status"] == "ok"
    assert entry["input"] == "a.md"
    assert entry["rewrote"] is True
    assert entry["pre"]["max"] == 0.7
    assert entry["post"]["max"] == 0.2
    assert entry["iterations"] == 2


def test_process_one_binary_skipped_without_reading(tree):
    entry = batch_mod._process_one(
        tree / "pic.png.txt", tree, tree.parent / "out",
        rewriter=object(), tier="lite", threshold=0.3,
        max_iters=5, best_of=3, dry_run=False,
    )
    assert entry["status"] == "skipped"
    assert entry["reason"] == "binary"
    assert entry["pre"] is None


def test_process_one_empty_skipped(tree):
    entry = batch_mod._process_one(
        tree / "empty.md", tree, tree.parent / "out",
        rewriter=object(), tier="lite", threshold=0.3,
        max_iters=5, best_of=3, dry_run=False,
    )
    assert entry["status"] == "skipped"
    assert entry["reason"] == "empty"


def test_process_one_read_failure_becomes_failed_not_raised(tree, monkeypatch):
    def boom(path, *a, **k):
        raise OSError("Permission denied")

    monkeypatch.setattr(batch_mod, "read_file", boom)
    entry = batch_mod._process_one(
        tree / "a.md", tree, tree.parent / "out",
        rewriter=object(), tier="lite", threshold=0.3,
        max_iters=5, best_of=3, dry_run=False,
    )
    assert entry["status"] == "failed"
    assert "Permission denied" in entry["error"]


def test_process_one_rewriter_error_is_failed(tree, monkeypatch):
    def err(*a, **k):
        return {"error": "no rewriter configured", "final": "x"}

    monkeypatch.setattr(batch_mod, "untell_text", err)
    entry = batch_mod._process_one(
        tree / "a.md", tree, tree.parent / "out",
        rewriter=object(), tier="lite", threshold=0.3,
        max_iters=5, best_of=3, dry_run=False,
    )
    assert entry["status"] == "failed"
    assert "no rewriter configured" in entry["error"]


def test_batch_mirrors_structure_and_writes_manifest(tree, capsys):
    out = tree / "out"
    rc = main([str(tree), "--out", str(out)])
    assert rc == 0
    assert (out / "a.md").read_text(encoding="utf-8") == "humanized output"
    assert (out / "sub" / "c.md").read_text(encoding="utf-8") == "humanized output"
    # skipped files produce no output file
    assert not (out / "pic.png.txt").exists()
    assert not (out / "empty.md").exists()
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["summary"]["total"] == 5
    assert manifest["summary"]["ok"] == 3
    assert manifest["summary"]["skipped"] == 2
    assert manifest["summary"]["failed"] == 0
    by_input = {f["input"]: f for f in manifest["files"]}
    assert by_input["pic.png.txt"]["status"] == "skipped"
    assert by_input["pic.png.txt"]["reason"] == "binary"
    assert by_input["empty.md"]["status"] == "skipped"
    assert by_input["empty.md"]["reason"] == "empty"
    assert by_input["a.md"]["pre"]["max"] == 0.7
    assert by_input["a.md"]["rewrote"] is True
    out_text = capsys.readouterr().out
    assert "3 humanized (3 rewrote)" in out_text
    assert "2 skipped, 0 failed" in out_text


def test_dry_run_writes_nothing(tree, capsys):
    out = tree / "out"
    rc = main([str(tree), "--out", str(out), "--dry-run"])
    assert rc == 0
    assert not out.exists(), "dry run must not create the output directory"
    out_text = capsys.readouterr().out
    assert "would be humanized" in out_text
    assert "nothing written" in out_text


def test_limit_caps_humanized_files(tree, capsys):
    out = tree / "out"
    rc = main([str(tree), "--out", str(out), "--limit", "2"])
    assert rc == 0
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["summary"]["total"] == 2
    assert manifest["summary"]["ok"] == 2
    # the third humanizable file (sub/c.md) was not processed
    assert not (out / "sub").exists()


def test_json_prints_manifest_to_stdout(tree, capsys):
    out = tree / "out"
    rc = main([str(tree), "--out", str(out), "--json"])
    assert rc == 0
    captured = capsys.readouterr()
    manifest = json.loads(captured.out)  # stdout is pure JSON
    assert manifest["summary"]["ok"] == 3
    assert "manifest:" in captured.err  # summary line moved to stderr


def test_exit_code_reflects_failure(tree, monkeypatch, capsys):
    def boom(path, *a, **k):
        raise OSError("Permission denied")

    monkeypatch.setattr(batch_mod, "read_file", boom)
    rc = main([str(tree), "--out", str(tree / "out")])
    assert rc == 1
    err = capsys.readouterr().err
    assert "failed" in err
    assert "Permission denied" in err


def test_missing_directory_exits_two(tmp_path):
    assert main([str(tmp_path / "no" / "such" / "dir")]) == 2


def test_output_dir_may_not_equal_input(tree, capsys):
    assert main([str(tree), "--out", str(tree)]) == 2


def test_unavailable_rewriter_exits_one(tree, capsys, monkeypatch):
    monkeypatch.setattr(batch_mod, "get_rewriter", lambda prefer=None: None)
    assert main([str(tree), "--rewriter", "neural"]) == 1
    assert "unavailable" in capsys.readouterr().err


def test_batch_subcommand_registered_in_cli():
    from untell.scripts.cli import _COMMANDS, _ONE_LINER

    assert _COMMANDS["batch"] == "untell.scripts.batch:main"
    assert "batch" in _ONE_LINER


def test_batch_dispatch_via_cli_routes_to_batch_main(monkeypatch, tmp_path):
    """`untell batch <dir>` must reach this module's main(), forwarding argv."""
    from untell.scripts import cli

    seen = {}

    def spy(argv=None):
        seen["argv"] = argv
        return 0

    monkeypatch.setattr(batch_mod, "main", spy)
    rc = cli.main(["batch", str(tmp_path), "--dry-run"])
    assert rc == 0
    assert seen["argv"] == [str(tmp_path), "--dry-run"]


def test_real_lite_run_humanizes_and_writes(tree, monkeypatch, capsys):
    """One true end-to-end run: real loop, lite tier, NLI off for speed."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    monkeypatch.setenv("UNTELL_DISABLE_NLI", "1")
    monkeypatch.setattr(batch_mod, "untell_text", _REAL_UNT_ELL_TEXT)
    out = tree / "out"
    rc = main([str(tree), "--out", str(out), "--limit", "1", "--max-iters", "1"])
    assert rc == 0
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["summary"]["ok"] == 1
    entry = manifest["files"][0]
    assert entry["status"] == "ok"
    assert entry["input"] == "a.md"
    assert entry["pre"] is not None and entry["post"] is not None
