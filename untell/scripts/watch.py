"""untell watch — humanize files the moment they change.

``untell watch ./drafts`` polls a directory tree and humanizes each ``.txt`` /
``.md`` file as soon as it appears or is edited, updating the humanized copy in
the output directory as the source keeps changing. It reuses the exact
per-file pipeline from ``untell batch`` (``untell.scripts.batch._process_one``)
for every changed file, so the closed loop, the binary/empty skips, and the
per-file failure isolation all behave identically to batch:

    untell watch ./drafts                      # poll ./drafts, write ./drafts_humanized/
    untell watch ./drafts --out ./clean        # choose the output directory
    untell watch ./notes --max-batches 1       # exit after the first humanized change

How it works:

* **Polling, not events.** The filesystem is re-scanned every ``--poll-interval``
  seconds and files whose ``(mtime, size)`` changed since the previous scan are
  queued. No third-party watcher dependency is required (the envelope forbids
  adding one), so this runs on the stdlib lite tier.
* **Debounced batches.** Edits that arrive close together are coalesced into a
  single processing batch once the tree has been quiet for ``--debounce``
  seconds. A burst of save-from-an-editor therefore costs one pass, not one per
  write.
* **Latest state wins, dropped on delete.** A file edited several times while a
  batch is pending is humanized once, from its newest content — the batch reads
  the file when it *processes*, not when it first saw the change (and the
  coalescer dedupes repeated edits into one path). A file that is deleted before
  its batch flushes is dropped entirely.
* **Existing files at startup are not humanized.** Watch is for *changes*: files
  already present when it starts are the baseline, not the workload. To clear a
  whole tree first, run ``untell batch``.

Exit behaviour: the process runs until interrupted (Ctrl-C exits 0), or until
``--max-batches`` batches have been processed — handy for automation and demos.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# Run-as-file support (zero-dep lite tier): when this file is executed directly
# rather than imported as part of the `untell` package, put the directory that
# *contains* the package on sys.path so `import untell` resolves from any cwd.
if __package__ in (None, ""):
    import sys as _sys

    for _p in Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            _sys.path.insert(0, str(_p))
            break

from untell.rewriter import get_rewriter  # noqa: E402
from untell.scripts import batch  # noqa: E402
from untell.scripts.batch import (  # noqa: E402
    _positive_int,
    _probability,
    _text_suffixes,
)
from untell.scripts.io_utils import configure_utf8_io  # noqa: E402
from untell.scripts.score import DEFAULT_THRESHOLD  # noqa: E402

logger = logging.getLogger(__name__)


def _nonneg_float(value: str) -> float:
    """argparse type for --poll-interval / --debounce: 0 or more."""
    try:
        num = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {value!r}") from None
    if num < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {value!r}")
    return num


def _rel_key(path: Path, root_res: Path) -> str:
    """Relative slash-normalised key used for both the snapshot and the batch."""
    return str(path.relative_to(root_res)).replace("\\", "/")


def _scan(root: Path, suffixes, exclude: Path | None = None) -> dict[str, tuple]:
    """Snapshot of every prose file under ``root``: {rel: (mtime_ns, size)}.

    The signature is ``(mtime_ns, size)`` so an edit that changes content but
    lands back on the same byte count still registers (mtime moves) and an edit
    that is byte-identical still registers the re-save. ``exclude`` prunes an
    output subtree that lives inside ``root`` so we never re-watch our own
    humanized output.
    """
    root_res = root.resolve()
    excl = exclude.resolve() if exclude is not None else None
    sigs: dict[str, tuple] = {}
    for dirpath, dirnames, filenames in os.walk(root_res):
        cur = Path(dirpath)
        dirnames[:] = [
            d for d in dirnames
            if not (excl is not None and (cur / d).resolve() == excl)
        ]
        for name in filenames:
            p = cur / name
            if p.suffix.lower() not in suffixes:
                continue
            try:
                st = p.stat()
            except OSError:
                continue  # vanished mid-walk; skip, next scan will reconcile
            sigs[_rel_key(p, root_res)] = (st.st_mtime_ns, st.st_size)
    return sigs


def _diff(prev: dict[str, tuple], cur: dict[str, tuple]) -> list[str]:
    """Sorted rel paths that are new or whose signature changed.

    Deletions are deliberately not reported: a file that disappears leaves
    nothing to humanize. (A path that changed and *then* disappeared is dropped
    at flush time by the loop's ``live`` filter.)
    """
    changed = [rel for rel, sig in cur.items() if prev.get(rel) != sig]
    changed.sort()
    return changed


class _Coalescer:
    """Accumulate changed rel paths, flush a debounced batch once quiet.

    A path that changes again before the batch flushes is updated in place
    (``latest state wins``) so an editor writing a file over several seconds
    yields one entry per path, not one per write.
    """

    __slots__ = ("quiet_for", "_pending", "_last_change")

    def __init__(self, quiet_for: float):
        self.quiet_for = quiet_for
        self._pending: set[str] = set()
        self._last_change: float | None = None

    def feed(self, changed: list[str], t: float) -> list[str] | None:
        """Register any new changes; return a batch to flush, or None."""
        if changed:
            self._pending.update(changed)
            self._last_change = t
        if self._last_change is None:
            # never seen a change yet (or just flushed) -> nothing to do
            return None
        if t - self._last_change >= self.quiet_for and self._pending:
            return self.flush()
        return None

    def flush(self) -> list[str]:
        """Return the pending batch (sorted) and reset."""
        batch = sorted(self._pending)
        self._pending.clear()
        self._last_change = None
        return batch


def _make_processor(root: Path, out_dir: Path, *, tier, threshold, rewriter,
                    max_iters, best_of, dry_run):
    """A ``process(paths) -> stats`` callable built on the batch pipeline.

    Reuses ``untell.scripts.batch._process_one`` for every changed file — the
    whole point of "drop into the batch pipeline" — with one rewriter instance
    resolved up front, exactly as ``untell batch`` does for a tree.
    """
    root_res = root.resolve()
    out_res = out_dir.resolve()

    def process(paths: list[str]) -> dict:
        entries = []
        for rel in paths:
            entry = batch._process_one(
                root_res / rel, root_res, out_res,
                rewriter=rewriter,
                tier=tier,
                threshold=threshold,
                max_iters=max_iters,
                best_of=best_of,
                dry_run=dry_run,
            )
            entries.append(entry)
        ok = sum(1 for e in entries if e["status"] == "ok")
        skipped = sum(1 for e in entries if e["status"] == "skipped")
        failed = sum(1 for e in entries if e["status"] == "failed")
        rewrote = sum(1 for e in entries if e["rewrote"])
        return {
            "entries": entries,
            "ok": ok,
            "skipped": skipped,
            "failed": failed,
            "rewrote": rewrote,
        }

    return process


def run(
    root: Path,
    out_dir: Path,
    *,
    tier: str,
    threshold: float,
    rewriter,
    max_iters: int,
    best_of: int,
    dry_run: bool = False,
    poll_interval: float = 1.0,
    debounce: float = 2.0,
    max_batches: int | None = None,
    timeout: float | None = None,
    suffixes=frozenset(_text_suffixes),
    scan=None,
    sleep=None,
    now=None,
    should_stop=None,
    process=None,
) -> list[dict]:
    """Poll ``root`` and humanize changes until stopped.

    Returns a stats dict (``ok``/``skipped``/``failed``/``rewrote``/``entries``)
    per processed batch. Injection points keep the loop deterministic and fast to
    test: ``scan`` yields snapshots, ``sleep``/``now``/``should_stop`` drive the
    polling and debounce clock, and ``process`` replaces the batch pipeline.
    """
    def _scan_default(_r: Path) -> dict:
        return _scan(_r, suffixes, exclude=out_dir)

    def _stop_never() -> bool:
        return False

    if scan is None:
        scan = _scan_default
    if sleep is None:
        sleep = time.sleep
    if now is None:
        now = time.monotonic
    if should_stop is None:
        should_stop = _stop_never
    if timeout is not None and should_stop is _stop_never:
        _start = now()
        def _timeout_stop() -> bool:
            return (now() - _start) >= timeout
        should_stop = _timeout_stop
    if process is None:
        process = _make_processor(
            root, out_dir, tier=tier, threshold=threshold, rewriter=rewriter,
            max_iters=max_iters, best_of=best_of, dry_run=dry_run,
        )

    prev = scan(root)
    coalescer = _Coalescer(debounce)
    batches: list[dict] = []
    while True:
        sleep(poll_interval)
        cur = scan(root)
        changed = _diff(prev, cur)
        prev = cur
        batch_paths = coalescer.feed(changed, now())
        if batch_paths:
            # Drop paths deleted before their batch flushed (latest snapshot wins).
            live = [p for p in batch_paths if p in prev]
            if live:
                batches.append(process(live))
            if max_batches is not None and len(batches) >= max_batches:
                break
        if should_stop():
            break

    # Final flush: a change still pending when we stop is still processed.
    final = [p for p in coalescer.flush() if p in prev]
    if final:
        batches.append(process(final))
    return batches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="untell-watch",
        description="Humanize .txt/.md files as they appear or change (debounced batches).",
    )
    parser.add_argument("directory", help="directory tree to watch (recursively)")
    parser.add_argument(
        "--out",
        default=None,
        help="output directory (default: <input>_humanized, as a sibling)",
    )
    parser.add_argument(
        "--tier",
        default="lite",
        choices=["lite", "full", "heavy", "commercial"],
        help="detector tier (default: lite — the zero-dependency stdlib path)",
    )
    parser.add_argument(
        "--threshold", "-t", type=_probability, default=DEFAULT_THRESHOLD,
        help=f"detector pass threshold (default: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--rewriter",
        default="composite",
        help="rewriter to use (default: composite — the free $0 path)",
    )
    parser.add_argument(
        "--max-iters", type=_positive_int, default=5,
        help="max rewrite iterations per file (default: 5)",
    )
    parser.add_argument(
        "--best-of", type=_positive_int, default=3,
        help="rewrite candidates per iteration (default: 3)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="report what would be humanized, but rewrite and write nothing",
    )
    parser.add_argument(
        "--poll-interval", type=_nonneg_float, default=1.0,
        help="seconds between filesystem rescans (default: 1.0)",
    )
    parser.add_argument(
        "--debounce", type=_nonneg_float, default=2.0,
        help="quiet seconds before a batch of changes is processed (default: 2.0)",
    )
    parser.add_argument(
        "--max-batches", type=_positive_int, default=None,
        help="exit after processing N batches (default: run until Ctrl-C)",
    )
    parser.add_argument(
        "--timeout", type=_nonneg_float, default=None,
        help="exit after N seconds even if no change was processed (default: run until Ctrl-C)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    configure_utf8_io()
    args = build_parser().parse_args(argv)

    root = Path(args.directory)
    if not root.exists():
        print(f"error: no such directory: {root}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    name = root.name or "untell"
    out_dir = Path(args.out) if args.out else root.parent / f"{name}_humanized"
    if out_dir.resolve() == root.resolve():
        print(
            f"error: output directory must differ from the input directory ({root})",
            file=sys.stderr,
        )
        return 2

    rewriter = get_rewriter(prefer=args.rewriter)
    if rewriter is None or not rewriter.available():
        print(
            f"error: --rewriter {args.rewriter} is unavailable — it needs its extra "
            "(pip install -e '.[full]'). Try --rewriter composite for the zero-dependency path.",
            file=sys.stderr,
        )
        return 1

    print(
        f"watch: watching {root} for changes "
        f"(poll {args.poll_interval:g}s, debounce {args.debounce:g}s) — Ctrl-C to stop",
        file=sys.stderr,
    )
    try:
        batches = run(
            root,
            out_dir,
            tier=args.tier,
            threshold=args.threshold,
            rewriter=rewriter,
            max_iters=args.max_iters,
            best_of=args.best_of,
            dry_run=args.dry_run,
            poll_interval=args.poll_interval,
            debounce=args.debounce,
            max_batches=args.max_batches,
            timeout=args.timeout,
        )
    except KeyboardInterrupt:
        # Fall through to the summary of whatever already flushed.
        return 0

    ok = sum(b["ok"] for b in batches)
    skipped = sum(b["skipped"] for b in batches)
    failed = sum(b["failed"] for b in batches)
    rewrote = sum(b["rewrote"] for b in batches)
    if args.dry_run:
        summary = (
            f"watch: {len(batches)} batch(es), {ok} file(s) would be humanized, "
            f"{skipped} skipped, {failed} failed (dry run — nothing written)"
        )
    else:
        summary = (
            f"watch: {len(batches)} batch(es), {ok} file(s) humanized "
            f"({rewrote} rewrote), {skipped} skipped, {failed} failed"
        )
    print(summary)
    for b in batches:
        for entry in b["entries"]:
            if entry["status"] == "failed":
                print(f"  failed  {entry['input']}: {entry['error']}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
