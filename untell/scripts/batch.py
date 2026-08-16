"""Batch directory humanization — ``untell batch <dir>``.

Walks a directory tree, humanizes every ``.txt`` / ``.md`` file with the same
closed loop as ``untell humanize``, mirrors the tree into an output directory
(preserving relative structure), and records a JSON manifest plus a one-line
summary:

    untell batch ./drafts                     # writes ./drafts_humanized/
    untell batch ./drafts --out ./clean       # choose the output directory
    untell batch ./drafts --dry-run           # report, write nothing
    untell batch ./drafts --limit 3           # trial on the first 3 files

Per-file behaviour:

* **Binary files are skipped, not failed.** A NUL byte in the first KB (or
  anywhere in the decoded text) marks the file as binary — real text has no
  NULs — and the entry is recorded as ``skipped`` with reason ``binary`` while
  the rest of the tree keeps processing.
* **Empty files are skipped** (reason ``empty``): there is nothing to
  humanize, and the single-file CLI refuses empty input for the same reason.
* **A failing file never aborts the run.** A read error or a rewriter error is
  recorded as ``failed`` with its message, the remaining files still process,
  and the exit code is 1 if any file failed.
* **Output mirrors input.** ``<out>/<relative path>`` is written for every
  file that humanized; skipped/failed files produce no output file but still
  appear in the manifest.
* **Deterministic order.** The walk is sorted, so ``--limit`` and the manifest
  are reproducible between runs.

The manifest (``<out>/manifest.json``) records every input file: its relative
path, status (``ok``/``skipped``/``failed``), pre/post detector scores
(``max``/``mean``/``flagged``/``tier``), the ``rewrote`` flag, iteration count,
and any error message. The summary line is printed to stdout (or stderr under
``--json``, so stdout stays pure JSON, matching the other commands).

The loop itself is ``untell.scripts.run.untell_text`` — the exact code
``untell humanize`` runs — with one rewriter instance shared across the whole
tree (resolved once, not once per file).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
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
from untell.scripts.io_utils import configure_utf8_io, read_file  # noqa: E402
from untell.scripts.run import untell_text  # noqa: E402
from untell.scripts.score import DEFAULT_THRESHOLD  # noqa: E402

logger = logging.getLogger(__name__)

# Which files count as prose for the batch walk. Deliberately just .txt/.md —
# the two formats the README leads with — and case-insensitive.
_text_suffixes = frozenset({".txt", ".md"})

# NUL sniff window: real text contains no NUL at all, so a NUL in the first KB
# is binary with high confidence, and a NUL later is caught by io_utils'
# `_reject_if_binary` when the full file is decoded. BOMs are checked first so
# a UTF-16 file (whose text is full of NUL bytes) is not misclassified.
_head_bytes = 1024

_known_boms = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
    (b"\xff\xfe\x00\x00", "utf-32"),
    (b"\x00\x00\xfe\xff", "utf-32"),
)


def _probability(value: str) -> float:
    """argparse type for a probability: reject outside [0, 1] with a message."""
    try:
        num = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {value!r}") from None
    if not 0.0 <= num <= 1.0:
        raise argparse.ArgumentTypeError(f"must be between 0 and 1, got {value!r}")
    return num


def _positive_int(value: str) -> int:
    """argparse type for --limit / --max-iters: at least 1."""
    try:
        num = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {value!r}") from None
    if num < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {value!r}")
    return num


def _looks_binary(path: Path) -> bool:
    """True when the file's head smells binary (NUL byte, no BOM).

    The check is deliberately cheap: it reads only the first KB, which is what
    makes it a *batch* heuristic rather than per-file overhead.
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(_head_bytes)
    except OSError:
        return False  # let the read step report the real error
    if not head:
        return False
    if any(head.startswith(bom) for bom, _ in _known_boms):
        return False
    return b"\x00" in head


def _walk_inputs(root: Path, out_dir: Path) -> list[Path]:
    """Every .txt/.md under ``root``, sorted, excluding the output tree.

    ``out_dir`` is excluded when it sits inside ``root`` so a re-run never
    processes its own previous output (the mirrored files are valid .md/.txt
    and would otherwise be humanized a second time).
    """
    root_res = root.resolve()
    out_res = out_dir.resolve()
    results: list[Path] = []
    # os.walk rather than Path.walk(): the latter is 3.12-only and pyproject
    # declares requires-python = ">=3.9". Walking the RESOLVED root keeps
    # every dirpath absolute, so `relative_to` below works for relative
    # invocations like `untell batch .` too.
    for dirpath, dirnames, filenames in os.walk(root_res):
        cur = Path(dirpath)
        # Prune output subtrees at the directory level.
        dirnames[:] = [
            d for d in dirnames
            if (cur / d).resolve() != out_res
        ]
        for name in sorted(filenames):
            p = cur / name
            if p.suffix.lower() in _text_suffixes:
                results.append(p)
    results.sort(key=lambda p: str(p.relative_to(root_res)))
    return results


def _score_summary(score: dict) -> dict:
    """The manifest-facing slice of a score dict: verdict numbers, not the
    per-detector map."""
    return {
        "max": score.get("max"),
        "mean": score.get("mean"),
        "flagged": score.get("flagged"),
        "tier": score.get("tier"),
    }


def _process_one(
    path: Path,
    root: Path,
    out_dir: Path,
    *,
    rewriter,
    tier: str,
    threshold: float,
    max_iters: int,
    best_of: int,
    dry_run: bool,
) -> dict:
    """Humanize one file; return its manifest entry. Never raises — every
    failure becomes a ``failed`` entry so the run continues."""
    rel = path.relative_to(root.resolve())
    entry: dict = {
        "input": str(rel).replace("\\", "/"),
        "output": str(rel).replace("\\", "/"),
        "status": "ok",
        "reason": None,
        "error": None,
        "rewrote": False,
        "pre": None,
        "post": None,
        "iterations": None,
    }

    # Binary sniff before decoding: a NUL in the first KB is binary with high
    # confidence, and skipping it here avoids decoding a large binary file as
    # latin-1 mojibake only to reject it later.
    if _looks_binary(path):
        entry["status"] = "skipped"
        entry["reason"] = "binary"
        return entry

    try:
        text = read_file(str(path))
    except ValueError as exc:
        # io_utils raises ValueError for binary content (NULs in the decoded
        # text) and for the "no such file" / "is a directory" guards.
        message = str(exc)
        if "NUL" in message or "binary" in message.lower():
            entry["status"] = "skipped"
            entry["reason"] = "binary"
        else:
            entry["status"] = "failed"
            entry["error"] = message
        return entry
    except OSError as exc:
        entry["status"] = "failed"
        entry["error"] = f"cannot read: {exc.strerror or exc}"
        return entry

    if not text.strip():
        entry["status"] = "skipped"
        entry["reason"] = "empty"
        return entry

    if dry_run:
        return entry  # status "ok", nothing written, nothing rewritten

    result = untell_text(
        text,
        tier=tier,
        threshold=threshold,
        rewriter=rewriter,
        max_iters=max_iters,
        best_of=best_of,
        progress=False,
    )
    if "error" in result:
        entry["status"] = "failed"
        entry["error"] = result["error"]
        return entry

    entry["rewrote"] = bool(result.get("changed", False))
    entry["pre"] = _score_summary(result.get("pre") or {})
    entry["post"] = _score_summary(result.get("post") or {})
    entry["iterations"] = result.get("iterations", 0)

    if not dry_run:
        final = result.get("final")
        if isinstance(final, str):
            out_path = out_dir / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(final, encoding="utf-8")
    return entry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="untell-batch",
        description="Humanize every .txt/.md file in a directory tree (manifest + summary).",
    )
    parser.add_argument("directory", help="directory tree to process (recursively)")
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
        help="walk and classify every file, but write nothing and rewrite nothing",
    )
    parser.add_argument(
        "--limit", type=_positive_int, default=None,
        help="humanize at most N files (skipped binary/empty files do not count)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="print the manifest to stdout as JSON (summary line goes to stderr)",
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

    # Resolve the rewriter ONCE for the whole tree. `composite` is always
    # available with no key and no torch; anything else may not be, and the
    # error is a configuration problem, not a per-file one — say so up front.
    rewriter = get_rewriter(prefer=args.rewriter)
    if rewriter is None or not rewriter.available():
        print(
            f"error: --rewriter {args.rewriter} is unavailable — it needs its extra "
            "(pip install -e '.[full]'). Try --rewriter composite for the zero-dependency path.",
            file=sys.stderr,
        )
        return 1

    files = _walk_inputs(root, out_dir)
    entries: list[dict] = []
    humanized = 0
    for path in files:
        if args.limit is not None and humanized >= args.limit:
            break
        entry = _process_one(
            path, root, out_dir,
            rewriter=rewriter,
            tier=args.tier,
            threshold=args.threshold,
            max_iters=args.max_iters,
            best_of=args.best_of,
            dry_run=args.dry_run,
        )
        entries.append(entry)
        if entry["status"] == "ok":
            humanized += 1

    ok = sum(1 for e in entries if e["status"] == "ok")
    skipped = sum(1 for e in entries if e["status"] == "skipped")
    failed = sum(1 for e in entries if e["status"] == "failed")
    rewrote = sum(1 for e in entries if e["rewrote"])

    manifest = {
        "tool": "untell-batch",
        "input_dir": str(root),
        "output_dir": str(out_dir),
        "tier": args.tier,
        "threshold": args.threshold,
        "rewriter": args.rewriter,
        "dry_run": args.dry_run,
        "limit": args.limit,
        "files": entries,
        "summary": {
            "total": len(entries),
            "ok": ok,
            "skipped": skipped,
            "failed": failed,
            "rewrote": rewrote,
        },
    }

    if args.dry_run:
        summary = (
            f"batch: {len(entries)} files, {ok} would be humanized, "
            f"{skipped} skipped, {failed} failed (dry run — nothing written)"
        )
    else:
        manifest_path = out_dir / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        summary = (
            f"batch: {len(entries)} files, {ok} humanized ({rewrote} rewrote), "
            f"{skipped} skipped, {failed} failed — manifest: {manifest_path}"
        )

    if args.json:
        # stdout stays pure JSON; the human summary moves to stderr.
        print(json.dumps(manifest, indent=2, ensure_ascii=True))
        print(summary, file=sys.stderr)
    else:
        print(summary)
        for entry in entries:
            if entry["status"] == "failed":
                print(f"  failed  {entry['input']}: {entry['error']}", file=sys.stderr)

    # Exit code reflects any failure: 1 if a file failed, 2 was already used
    # for usage/config errors above. Skipped files are not failures.
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
