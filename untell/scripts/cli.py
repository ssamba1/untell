"""Unified ``untell`` command — one discoverable entry point for every tool.

Instead of remembering eight ``untell-*`` scripts, you can run ``untell <subcommand> ...``:

    untell humanize "Your AI text"     # the closed loop (alias: loop)
    untell humanize "text" --rewriter surgical   # no key, $0
    untell score "text" --tier full    # detector ensemble score
    untell tells "text"                # count the AI writing tells (naturalness)
    untell verify --file draft.txt     # honest pass/fail per detector
    untell compare                     # head-to-head vs the humanizer technique classes
    untell ceiling --rewriter surgical # measure free evasion of the local ensemble
    untell sentences "text"            # which sentences read as AI
    untell prove "text"                # verify -> loop -> re-verify (commercial tier)

Each subcommand is the exact same code as its ``untell-<name>`` console script; this is just a friendly
front door. ``untell`` with no subcommand (or ``-h``) prints this list. Heavy deps load only when the
chosen subcommand actually runs (the dispatcher itself is import-cheap).
"""

from __future__ import annotations

import sys

if __package__ in (None, ""):
    from pathlib import Path as _Path

    for _p in _Path(__file__).resolve().parents:
        if (_p / "untell" / "__init__.py").exists():
            sys.path.insert(0, str(_p))
            break

# subcommand -> "module:function". Lazy so importing this module stays cheap and offline.
_COMMANDS: dict[str, str] = {
    "humanize": "untell.scripts.run:main",
    "loop": "untell.scripts.run:main",  # alias
    "score": "untell.scripts.score:main",
    "tells": "untell.scripts.tells:main",
    "verify": "untell.scripts.verify:main",
    "prove": "eval.prove:main",
    "sentences": "untell.scripts.sentences:main",
    "compare": "eval.compare_humanizers:main",
    "ceiling": "eval.ceiling:main",
}

_ONE_LINER = {
    "humanize": "run the closed detector-feedback loop (alias: loop)",
    "score": "score text with the local AI-detector ensemble",
    "tells": "count the AI writing tells in text (naturalness; lower = more human)",
    "verify": "honest pass/fail per detector (exit 0 only if all pass)",
    "prove": "verify -> loop -> re-verify, one before/after table",
    "sentences": "flag which sentences read as AI",
    "compare": "head-to-head vs the free-humanizer technique classes",
    "ceiling": "measure the loop's free evasion of the local ensemble",
}


def _usage() -> str:
    lines = ["untell: humanize AI text via a detector-feedback loop.", "", "Usage: untell <command> [options]", "", "Commands:"]
    for name, desc in _ONE_LINER.items():
        lines.append(f"  {name:11} {desc}")
    lines += [
        "",
        "Run 'untell <command> --help' for that command's options.",
        "No key needed: 'untell humanize \"text\" --rewriter surgical' runs the loop for $0.",
        "In Claude Code, just use the /untell skill (Claude is the rewriter).",
    ]
    return "\n".join(lines)


def _resolve(target: str):
    module_name, func_name = target.split(":")
    import importlib

    return getattr(importlib.import_module(module_name), func_name)


def main(argv: list[str] | None = None) -> int:
    try:
        from untell.scripts.io_utils import configure_utf8_io

        configure_utf8_io()  # UTF-8 stdout so the banner/help never mojibakes on Windows cp1252
    except Exception:
        pass
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(_usage())
        return 0
    cmd, rest = argv[0], argv[1:]
    target = _COMMANDS.get(cmd)
    if target is None:
        sys.stderr.write(f"untell: unknown command '{cmd}'\n\n{_usage()}\n")
        return 2
    return _resolve(target)(rest)


if __name__ == "__main__":
    raise SystemExit(main())
