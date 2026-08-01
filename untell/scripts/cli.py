"""Unified ``untell`` command — one discoverable entry point for every tool.

Instead of remembering ``untell-*`` scripts, run ``untell <subcommand> ...``:

    untell humanize "Your AI text"     # the closed loop (alias: loop)
    untell "Your AI text"              # shortcut — same as above with --rewriter composite
    untell score "text" --tier full    # detector ensemble score
    untell tells "text"                # count the AI writing tells (naturalness)
    untell verify --file draft.txt     # honest pass/fail per detector
    untell compare                     # head-to-head vs free-humanizer techniques
    untell ceiling --rewriter surgical # measure free evasion ceiling
    untell sentences "text"            # which sentences read as AI
    untell prove "text"                # verify -> loop -> re-verify (commercial tier)
    untell --check                     # verify installation and available components
    untell --demo                      # run a guided demo on built-in samples

Each subcommand is the exact same code as its ``untell-<name>`` console script; this is just a friendly
front door. ``untell`` with no subcommand runs the guided demo. Heavy deps load only when the
chosen subcommand actually runs (the dispatcher itself is import-cheap).
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse

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
    "detector-audit": "eval.detector_audit:main",
    "humanness": "untell.humanness:main",
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
    "detector-audit": "check every detector for dead/inverted output (integrity gate)",
    "humanness": "score text 0-100: how human does it read (combines tells + detectors)",
}


def _usage() -> str:
    lines = [
        "untell: humanize AI text via a detector-feedback loop.",
        "",
        "Usage:",
        "  untell <command> [options]     run a specific command",
        "  untell \"your text\"            shortcut — score + tells + humanize in one step",
        "  untell --demo                  run the guided demo",
        "  untell --check                 verify installation",
        "",
        "Commands:",
    ]
    for name, desc in _ONE_LINER.items():
        lines.append(f"  {name:11} {desc}")
    lines += [
        "",
        "Run 'untell <command> --help' for that command's options.",
        "No key needed: 'untell humanize \"text\" --rewriter composite' runs the loop for $0.",
        "In Claude Code, just use the /untell skill (Claude is the rewriter).",
    ]
    return "\n".join(lines)


def _resolve(target: str):
    module_name, func_name = target.split(":")
    import importlib

    return getattr(importlib.import_module(module_name), func_name)


def _run_demo(text: str | None = None) -> int:
    """Run a guided demo: score → tells on built-in text. Instant (<1s)."""
    from untell.scripts.io_utils import configure_utf8_io
    configure_utf8_io()

    sample = (
        "Furthermore, artificial intelligence has fundamentally transformed numerous industries. "
        "Moreover, organizations increasingly leverage these technologies to optimize operational "
        "efficiency and drive innovation. Overall, the transformative impact continues to expand "
        "across various sectors."
    )
    sample_text = text or sample

    # Step 1: Score (instant on lite tier)
    print("\n[1/3] Scoring with local detector ensemble...\n")
    from untell.scripts.score import score_text
    pre = score_text(sample_text, tier="lite")
    try:
        from untell.humanness import classification, humanness
        from untell.rich_output import print_humanness
        h = humanness(sample_text, tier="lite")
        print_humanness(h, classification(h))
    except Exception:
        print(f"  AI Probability: {pre['max']:.2f}  (threshold: {pre['threshold']})")
        print(f"  Tier: {pre['tier']}")
    print()

    # Step 2: Tells (instant)
    print("[2/3] Counting AI writing tells...\n")
    from untell.scripts.tells import score_tells
    tells = score_tells(sample_text)
    try:
        from untell.rich_output import print_tells_result
        print_tells_result(tells)
    except Exception:
        print(f"  Tells: {tells['tells']} ({tells['tells_per_100w']}/100w)")
        if tells.get("by_category"):
            for cat, count in sorted(tells["by_category"].items(), key=lambda kv: -kv[1]):
                print(f"    {cat}: {count}")
    print()

    # Step 3: Instructions (instant — no loop)
    print(
        "[3/3] Ready to humanize!\n"
        f"\n"
        f"  untell humanize \"{sample_text[:60]}...\" --rewriter composite\n"
        f"\n"
        f"The closed loop will:\n"
        f"  1. Score your text against 15 detectors\n"
        f"  2. Rewrite flagged sentences using composite rewriter\n"
        f"  3. Re-score and repeat until the hardest detector passes\n"
        f"\n"
        f"Try it with different voice styles:\n"
        f"  untell humanize \"your text\" --style casual\n"
        f"  untell humanize \"your text\" --style academic\n"
        f"  untell humanize \"your text\" --style blunt\n"
        f"\n"
        f"Quick score without humanizing:\n"
        f"  untell score \"your text\" --tier full\n"
        f"  untell tells \"your text\"\n"
    )

    return 0


def _run_check() -> int:
    """Verify installation: show versions, available detectors, rewriters."""
    from untell.scripts.io_utils import configure_utf8_io
    configure_utf8_io()

    import untell
    print(f"\nuntell v{untell.__version__}\n")

    # Detectors
    from untell.detectors.base import all_detectors
    dets = all_detectors()
    available = [d for d in dets if d.available()]
    print(f"Detectors: {len(dets)} registered, {len(available)} available")
    for d in dets:
        status = "✓" if d.available() else "✗"
        print(f"  {status} {d.name:24} tier={d.tier}")

    # Rewriters
    from untell.rewriter import get_rewriter
    print("\nRewriters:")
    for name in ["composite", "structural", "surgical", "anthropic", "openai"]:
        rw = get_rewriter(prefer=name)
        status = "✓" if rw and rw.available() else "✗"
        print(f"  {status} {name}")

    # API server
    try:
        from untell.api_server import app
        print(f"\nAPI Server: ✓ (v{app.version})")
    except Exception:
        print("\nAPI Server: ✗ (install: pip install untell[server])")

    # Rich output
    try:
        print("Rich output: ✓")
    except Exception:
        print("Rich output: ✗ (install: pip install untell[rich])")

    print(f"\nEnvironment: Python {sys.version.split()[0]} on {sys.platform}")
    print("\n✓ All systems nominal" if available else "\n! No detectors available — install: pip install untell[full]")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Unified ``untell`` command — one discoverable entry point for every tool."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    try:
        from untell.scripts.io_utils import configure_utf8_io

        configure_utf8_io()
    except Exception:
        pass

    # Enable argcomplete tab completion when available.
    try:
        import argcomplete
    except ImportError:
        pass
    else:
        argcomplete.autocomplete(_build_parser())

    argv = list(sys.argv[1:] if argv is None else argv)

    # No args → run the demo
    if not argv:
        return _run_demo()

    # --check / --demo flags
    if argv[0] in ("--check", "--status"):
        return _run_check()
    if argv[0] in ("--demo", "-d"):
        return _run_demo()

    # -h / --help
    if argv[0] in ("-h", "--help", "help"):
        print(_usage())
        return 0

    # First arg is a known subcommand → dispatch
    cmd = argv[0]
    target = _COMMANDS.get(cmd)
    if target is not None:
        return _resolve(target)(argv[1:])

    # First arg is NOT a known command → treat as humanize shortcut
    from untell.scripts.run import main as humanize_main

    return humanize_main(argv)


def _build_parser() -> argparse.ArgumentParser:
    """Build a top-level argument parser for tab completion."""
    import argparse

    parser = argparse.ArgumentParser(prog="untell", add_help=False, description="AI-text humanizer")
    parser.add_argument("subcommand", nargs="?", choices=list(_COMMANDS) + ["--check", "--demo"],
                        help="subcommand to run")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
