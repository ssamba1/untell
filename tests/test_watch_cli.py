"""Tests for `untell watch <dir>` — humanize files as they change.

The unit tests use a *fake watcher*: ``run``'s ``scan`` / ``sleep`` / ``now`` /
``process`` injection points are replaced so the orchestration — snapshot diff,
debounce coalescing, latest-state reuse, deleted-path drop, batch reuse, exit
conditions — is asserted deterministically in milliseconds. One test runs the
real batch pipeline through the real filesystem (lite tier) to prove the wiring
end to end.
"""

from __future__ import annotations

from pathlib import Path

from untell.scripts import watch as watch_mod
from untell.scripts.watch import _Coalescer, _diff, _scan, main, run


def _sig(mtime=1, size=10):
    return (mtime, size)


class FakeScanner:
    """A scripted filesystem: returns the next snapshot from ``seq`` on each call."""

    def __init__(self, seq):
        self.seq = list(seq)
        self.calls = 0

    def __call__(self, root):
        idx = min(self.calls, len(self.seq) - 1)
        self.calls += 1
        return self.seq[idx]


class FakeClock:
    """A monotonic clock that advances a fixed step per read."""

    def __init__(self, step=10.0):
        self.t = 0.0
        self.step = step

    def __call__(self):
        self.t += self.step
        return self.t


def _run_with_fake(root, out_dir, scanner, process, *, debounce=5.0,
                   max_batches=1, **kw):
    return run(
        root, out_dir, tier="lite", threshold=0.3, rewriter=object(),
        max_iters=5, best_of=3, poll_interval=1.0, debounce=debounce,
        max_batches=max_batches, scan=scanner, sleep=lambda _s: None,
        now=FakeClock(), process=process, **kw,
    )


def _record_process(processed):
    def process(paths):
        processed.append(list(paths))
        return {"entries": [], "ok": len(paths), "skipped": 0, "failed": 0,
                "rewrote": 0}
    return process


# --------------------------------------------------------------------------- #
# Pure pieces: scan / diff / coalescer
# --------------------------------------------------------------------------- #

def test_scan_collects_prose_files_recursively(tmp_path):
    (tmp_path / "a.md").write_text("hi", encoding="utf-8")
    (tmp_path / "b.txt").write_text("hi", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.md").write_text("hi", encoding="utf-8")
    (tmp_path / "pic.png").write_bytes(b"\x00\x01")
    sigs = _scan(tmp_path, watch_mod._text_suffixes)
    keys = sorted(sigs)
    assert "pic.png" not in keys
    assert keys == ["a.md", "b.txt", "sub/c.md"]
    # signature is (mtime_ns, size)
    assert len(sigs["a.md"]) == 2


def test_scan_excludes_output_subtree(tmp_path):
    root = tmp_path / "src"
    root.mkdir()
    out = tmp_path / "out"
    (root / "a.md").write_text("hi", encoding="utf-8")
    (out / "sub").mkdir(parents=True)
    (out / "sub" / "old.md").write_text("already done", encoding="utf-8")
    sigs = _scan(root, watch_mod._text_suffixes, exclude=out)
    assert "a.md" in sigs
    assert "sub/old.md" not in sigs


def test_diff_reports_new_and_modified_only():
    prev = {"a.md": _sig(1, 10), "b.md": _sig(5, 40)}
    cur = {"a.md": _sig(2, 10), "b.md": _sig(5, 40), "c.md": _sig(9, 1)}
    assert _diff(prev, cur) == ["a.md", "c.md"]


def test_diff_ignores_unchanged_and_deletions():
    prev = {"a.md": _sig(1, 10), "gone.md": _sig(3, 8)}
    cur = {"a.md": _sig(1, 10)}  # gone.md deleted -> not a change
    assert _diff(prev, cur) == []


def test_coalescer_burst_flushes_as_one_batch():
    c = _Coalescer(quiet_for=5.0)
    assert c.feed(["a.md", "b.md"], 1.0) is None     # just changed; not quiet yet
    assert c.feed([], 6.0) == ["a.md", "b.md"]       # quiet past window -> flush
    assert c.feed([], 7.0) is None                   # flushed; pending empty


def test_coalescer_dedupes_repeated_edit_of_same_file():
    c = _Coalescer(quiet_for=5.0)
    assert c.feed(["a.md"], 1.0) is None
    assert c.feed(["a.md"], 3.0) is None             # edited again -> still one slot
    assert c.feed([], 10.0) == ["a.md"]              # single entry, not two


# --------------------------------------------------------------------------- #
# Loop behaviour with a fake watcher
# --------------------------------------------------------------------------- #

def test_loop_processes_a_new_file_once(tmp_path):
    scanner = FakeScanner([{}, {"note.md": _sig(1, 10)}])
    processed = []
    batches = _run_with_fake(Path("dummy"), Path("out"), scanner,
                             _record_process(processed))
    assert [b["ok"] for b in batches] == [1]
    assert processed == [["note.md"]]


def test_loop_batches_burst_into_one_processing_call(tmp_path):
    # Several files appear in the same quiet window -> one batch, one process().
    scanner = FakeScanner([{}, {"a.md": _sig(1, 10), "b.md": _sig(1, 12)}])
    processed = []
    batches = _run_with_fake(Path("dummy"), Path("out"), scanner,
                             _record_process(processed))
    assert len(batches) == 1
    assert processed == [["a.md", "b.md"]]


def test_loop_reuses_latest_state_for_repeated_edit(tmp_path):
    # a.md changes twice inside the debounce window -> processed ONCE (latest).
    scanner = FakeScanner([
        {},                          # baseline
        {"a.md": _sig(1, 10)},       # v1
        {"a.md": _sig(2, 10)},       # v2 (edit before flush)
        {"a.md": _sig(2, 10)},       # quiet -> flush
    ])
    processed = []
    _run_with_fake(Path("dummy"), Path("out"), scanner, _record_process(processed))
    assert processed == [["a.md"]]


def test_loop_drops_deleted_path_before_flush(tmp_path):
    # a.md appears then is deleted before the batch flushes -> never processed.
    scanner = FakeScanner([{}, {"a.md": _sig(1, 10)}, {}])
    processed = []

    def should_stop():
        return scanner.calls >= len(scanner.seq)

    batches = run(
        Path("dummy"), Path("out"), tier="lite", threshold=0.3,
        rewriter=object(), max_iters=5, best_of=3, poll_interval=1.0,
        debounce=5.0, scan=scanner, sleep=lambda _s: None, now=FakeClock(),
        should_stop=should_stop, process=_record_process(processed),
    )
    assert processed == []
    assert batches == []


def test_loop_max_batches_stops_after_n(tmp_path):
    # debounce=0 flushes on the change poll itself; max_batches=2 exits after two.
    batch_snaps = [{"a.md": _sig(i, 10 + i)} for i in range(1, 6)]
    scanner = FakeScanner([{}, *batch_snaps])
    processed = []
    batches = _run_with_fake(
        Path("dummy"), Path("out"), scanner, _record_process(processed),
        debounce=0.0, max_batches=2,
    )
    assert len(batches) == 2
    assert len(processed) == 2


def test_loop_continues_watching_across_batches(tmp_path):
    # Two separate quiet windows each flush their own batch: the coalescer resets
    # after the first flush and a later, unrelated change is its own batch.
    scanner = FakeScanner([
        {},                                # baseline
        {"a.md": _sig(1, 10)},             # change 1
        {"a.md": _sig(1, 10)},             # quiet -> flush [a.md]
        {"a.md": _sig(1, 10), "b.md": _sig(2, 20)},   # change 2
        {"a.md": _sig(1, 10), "b.md": _sig(2, 20)},   # quiet -> flush [b.md]
    ])
    processed = []
    batches = _run_with_fake(Path("dummy"), Path("out"), scanner,
                             _record_process(processed), debounce=5.0,
                             max_batches=2)
    assert len(batches) == 2
    assert processed == [["a.md"], ["b.md"]]  # two batches, not one


def test_loop_timeout_returns_when_idle(tmp_path):
    # With no changes ever arriving, --timeout bounds the loop and returns cleanly
    # with zero batches (the documented bounded-run contract).
    scanner = FakeScanner([{}, {}, {}, {}])
    processed = []
    batches = run(
        Path("dummy"), Path("out"), tier="lite", threshold=0.3,
        rewriter=object(), max_iters=5, best_of=3, poll_interval=1.0,
        debounce=5.0, timeout=1.0, scan=scanner, sleep=lambda _s: None,
        now=FakeClock(), process=_record_process(processed),
    )
    assert batches == []
    assert processed == []


# --------------------------------------------------------------------------- #
# Real wiring: the actual batch pipeline on the real filesystem
# --------------------------------------------------------------------------- #

def test_real_watch_reuses_batch_pipeline_and_writes_output(tmp_path, monkeypatch, capsys):
    """A change lands on disk, the real loop sees it via the real scanner, and
    the real batch pipeline writes the humanized file to the out dir."""
    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    monkeypatch.setenv("UNTELL_DISABLE_NLI", "1")
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out"
    ai_text = (
        "Furthermore, artificial intelligence has fundamentally transformed "
        "numerous industries. Moreover, organizations increasingly leverage "
        "these technologies."
    )
    n = {"writes": 0}

    def scan(root):
        if n["writes"] == 1:
            (src / "a.md").write_text(ai_text, encoding="utf-8")
        n["writes"] += 1
        return _scan(root, watch_mod._text_suffixes)

    from untell.rewriter import get_rewriter
    rewriter = get_rewriter(prefer="composite")
    batches = run(
        src, out, tier="lite", threshold=0.3, rewriter=rewriter,
        max_iters=1, best_of=1, poll_interval=0.0, debounce=0.0,
        max_batches=1, scan=scan, sleep=lambda _s: None, now=FakeClock(),
    )
    assert len(batches) == 1
    assert batches[0]["ok"] == 1
    written = (out / "a.md").read_text(encoding="utf-8")
    assert written != ai_text  # the closed loop actually rewrote it
    # The rewriter instance was shared across the batch (reuse, not re-resolved).


# --------------------------------------------------------------------------- #
# CLI: main orchestration + registration
# --------------------------------------------------------------------------- #

def test_missing_directory_exits_two(tmp_path):
    assert main([str(tmp_path / "no" / "such" / "dir")]) == 2


def test_output_dir_may_not_equal_input(tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    assert main([str(src), "--out", str(src)]) == 2


def test_main_summary_reflects_processed_batches(capsys, monkeypatch, tmp_path):
    src = tmp_path / "src"
    src.mkdir()

    class _FakeRW:
        def available(self):
            return True

    monkeypatch.setattr(watch_mod, "get_rewriter", lambda prefer=None: _FakeRW())
    monkeypatch.setattr(watch_mod, "run", lambda *a, **k: [
        {"entries": [], "ok": 2, "skipped": 1, "failed": 0, "rewrote": 1},
    ])
    rc = main([str(src), "--dry-run"])
    assert rc == 0
    out_text = capsys.readouterr().out
    assert "1 batch(es), 2 file(s) would be humanized" in out_text
    assert "dry run" in out_text


def test_watch_subcommand_registered_in_cli():
    from untell.scripts.cli import _COMMANDS, _ONE_LINER

    assert _COMMANDS["watch"] == "untell.scripts.watch:main"
    assert "watch" in _ONE_LINER


def test_watch_dispatch_via_cli_routes_to_watch_main(monkeypatch, tmp_path):
    from untell.scripts import cli

    seen = {}

    def spy(argv=None):
        seen["argv"] = argv
        return 0

    monkeypatch.setattr(watch_mod, "main", spy)
    rc = cli.main(["watch", str(tmp_path), "--max-batches", "1"])
    assert rc == 0
    assert seen["argv"] == [str(tmp_path), "--max-batches", "1"]
