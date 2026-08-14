"""Strip hidden watermark characters from text.

Exists because SKILL.md could not reach this. The scrub is documented in the README as a step of
the pipeline and exposed by the MCP server as a tool, but it lives in ``untell.attacks
.unicode_tricks`` with no command-line entry point — and the skill drives every step through
``python scripts/<name>.py``. So the flagship path, where Claude is the rewriter, never scrubbed.

That gap matters more than it looks. Zero-width and tag characters survive paraphrasing: they
carry no meaning, so a rewrite has no reason to drop them, and the skill's own preserve-lock
restores locked spans byte-for-byte — including any hidden characters sitting inside a quote or
citation. Text can therefore come out the far end of the whole loop reading perfectly human and
still carrying an intact watermark that identifies its origin exactly.

Usage:
    python scripts/scrub.py "text"          # scrubbed text on stdout
    python scripts/scrub.py --file in.txt   # from a file
    cat in.txt | python scripts/scrub.py    # from stdin
    python scripts/scrub.py --json "text"   # {"hidden_before", "hidden_after", "changed", "text"}
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

if __package__ in (None, ""):
    for _p in Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            sys.path.insert(0, str(_p))
            break

from untell.attacks.unicode_tricks import count_hidden, scrub_hidden  # noqa: E402

logger = logging.getLogger(__name__)


def _read_input(args: argparse.Namespace) -> str | None:
    if args.file:
        # A missing or unreadable path is a usage problem, not a crash — an uncaught
        # FileNotFoundError traceback tells a script caller nothing it can act on.
        try:
            # read_file(): BOM-aware, sniffs UTF-16/cp1252, rejects binaries. Reading a
            # UTF-16 file with a naive utf-8 open produced mojibake and scrubbed THAT.
            from untell.scripts.io_utils import read_file

            return read_file(args.file)
        # ValueError as well as OSError: read_file now raises it for the three ordinary path
        # mistakes (missing, a directory, unreadable) with a message written for a person, and
        # catching only OSError would let those escape as tracebacks — the exact failure this
        # handler exists to prevent. `main()` returns an exit code here rather than raising
        # SystemExit, which is the contract the tests in this repo assert.
        except (OSError, ValueError) as exc:
            logger.error("cannot read %s: %s", args.file, exc)
            return None
    if args.text is None:
        return args.text
    if not sys.stdin.isatty():
        try:
            return sys.stdin.read()
        except UnicodeDecodeError:
            # Binary/undecodable stdin — same guard as read_stdin_or_none: clean "no input"
            # path instead of a traceback. MEASURED: b'\xff\xfe' piped here leaked before.
            return None
    return None


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    try:
        from untell.scripts.io_utils import configure_utf8_io

        configure_utf8_io()
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        prog="scrub.py",
        description="Remove hidden watermark characters (zero-width, tag, control, bidi, "
        "variation selectors) while leaving visible text byte-identical.",
    )
    parser.add_argument("text", nargs="?", help="Text to scrub (or use --file / stdin).")
    parser.add_argument("--file", "-f", help="Read text from this file.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON with the before/after hidden-character counts instead of bare text.",
    )
    args = parser.parse_args(argv)

    text = _read_input(args)
    if text is None:
        # `--json` has to hold on the ERROR path too. Every other JSON-emitting command answers
        # `{"error": "no input: ..."}` here; this one logged to stderr and left stdout EMPTY, so a
        # caller doing `json.loads(subprocess.check_output(...))` got a JSONDecodeError instead of
        # the message that would have told them what to fix. MEASURED, no input, `--json`:
        #
        #     humanize   {"error": "no input: pass text, --file PATH, or pipe to stdin"}   exit 2
        #     sentences  {"error": "no input: ..."}                                        exit 2
        #     tells      {"error": "no input: ..."}                                        exit 2
        #     scrub      (nothing on stdout)                                               exit 2
        message = 'no input: pass text, --file PATH, or pipe to stdin'
        if args.json:
            print(json.dumps({"error": message}))
        else:
            logger.error(message)
        return 2

    before = count_hidden(text)
    cleaned = scrub_hidden(text)
    after = count_hidden(cleaned)

    if args.json:
        print(
            json.dumps(
                {
                    "hidden_before": before,
                    "hidden_after": after,
                    "changed": cleaned != text,
                    "text": cleaned,
                },
                ensure_ascii=True,  # portable: never crash on a non-UTF-8 stdout
            )
        )
    else:
        # Bare text so this composes in a pipe. The count goes to stderr, which keeps stdout clean
        # for the next stage while still telling a human something was actually removed.
        print(cleaned, end="" if text.endswith("\n") else "\n")
        if before:
            print(f"[scrub] removed {before} hidden character(s)", file=sys.stderr)

    # Exit 0 even when nothing was found: "no watermark present" is a successful scrub, and a
    # non-zero code would break `scrub && next-step` chains on ordinary clean text.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
