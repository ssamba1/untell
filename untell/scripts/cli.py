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
    untell batch ./drafts             # humanize every .txt/.md in a directory tree
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
    "scrub": "untell.scripts.scrub:main",
    "numbers": "untell.scripts.numerals:main",
    "hedges": "untell.scripts.hedges:main",
    "explain": "untell.scripts.explain:main",
    "batch": "untell.scripts.batch:main",
}

# Console scripts this project ships that are NOT subcommands of `untell`. Typing one of these
# means the user read the documentation, so treating it as prose to humanize is never what they
# wanted — see the note in `main`. Derived by hand rather than from pyproject because the point is
# the user-facing name, and a missing entry only costs the old behaviour rather than breaking one.
_STANDALONE_ONLY = frozenset({
    "voice", "latex", "audit", "mcp", "server", "distill", "surrogate", "eval-policy",
})

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
    "scrub": "strip hidden watermark chars (zero-width, tag, bidi, homoglyph)",
    "numbers": "check every number in the original survives a rewrite",
    "hedges": "check a rewrite does not state more firmly than the original",
    "explain": "show why the preserve lock freezes each span (rule + rationale)",
    "batch": "humanize every .txt/.md file in a directory tree (manifest + summary)",
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
    """Run a guided demo: score → tells on built-in text.

    NOT instant, despite what this docstring used to claim. The lite tier is stdlib-only *until*
    torch is importable, at which point it silently upgrades to GPT-2 perplexity — better math, but
    measured at **28.6s** end to end for this demo on a machine with `.[full]` installed. Since
    `untell` with no arguments runs this, that wait is the first thing a new user meets, so it is
    announced the same way `untell-score` and `untell-verify` announce theirs.
    """
    import os
    import sys as _s

    from untell.scripts.io_utils import configure_utf8_io
    configure_utf8_io()

    if os.environ.get("UNTELL_LITE_NO_TORCH") != "1":
        try:
            import importlib.util

            if importlib.util.find_spec("torch") is not None:
                print(
                    "[untell] the lite tier upgrades to GPT-2 perplexity when torch is installed — "
                    "~20s on first run while models load and cache. Set UNTELL_LITE_NO_TORCH=1 for "
                    "the genuinely instant stdlib path.",
                    file=_s.stderr,
                )
        except Exception:
            pass

    sample = (
        "Furthermore, artificial intelligence has fundamentally transformed numerous industries. "
        "Moreover, organizations increasingly leverage these technologies to optimize operational "
        "efficiency and drive innovation. Overall, the transformative impact continues to expand "
        "across various sectors."
    )
    sample_text = text or sample

    # Score on the strongest tier whose stack is actually installed. This used to be hardcoded to
    # "lite", and the result was a demo that called its OWN deliberately-AI sample human. MEASURED
    # on the sample above:
    #     tier=lite   detector max 0.364   humanness 56.4  "mostly human"
    #     tier=full   detector max 1.000   humanness 24.6  "likely AI"
    # The first thing a new user runs is `untell` with no arguments, and it was answering "mostly
    # human" about text written to be obviously machine-generated. The lite heuristic is documented
    # as a weak proxy; leading with it here undersold the tool and misinformed the reader.
    # UNTELL_LITE_NO_TORCH=1 is the documented way to force the stdlib path, so it wins here too —
    # a user who asked for the dependency-free path should not be handed a model-backed score.
    demo_tier = "lite"
    if os.environ.get("UNTELL_LITE_NO_TORCH") != "1":
        try:
            import importlib.util

            if importlib.util.find_spec("torch") is not None:
                demo_tier = "full"
        except Exception:
            pass

    print("\n[1/3] Scoring with local detector ensemble...\n")
    from untell.scripts.score import score_text
    pre = score_text(sample_text, tier=demo_tier)
    try:
        from untell.humanness import classification, humanness
        from untell.rich_output import print_humanness
        h = humanness(sample_text, tier=demo_tier)
        print_humanness(h, classification(h))
    except Exception:
        print(f"  AI Probability: {pre['max']:.2f}  (threshold: {pre['threshold']})")
    # Name the tier that actually ran. "mostly human" from the weak heuristic and "likely AI" from
    # the real ensemble are different claims, and the reader cannot tell them apart otherwise.
    print(f"  (tier: {pre.get('tier', demo_tier)})")
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
    #
    # The count below used to be the constant 15 — the size of the detector REGISTRY, not of what
    # runs. `all_detectors()` does return 15 classes, but `load_detectors` gives 5 at full tier and
    # 1 at lite, so a reader on a clean stdlib install was told fifteen detectors had judged their
    # text when one had. Two ways to get the honest number were rejected before this one:
    # `available()` reports 5 even under UNTELL_LITE_NO_TORCH=1 (it tests whether torch imports,
    # not whether this run will use it) and costs ~9s on the path whose whole selling point is
    # being instant. `pre["detectors"]` is the set that literally just answered in step 1 — free,
    # and it cannot disagree with the score printed two screens up.
    #
    # `--tier` is pinned in the suggested command for the same reason: `untell humanize` defaults
    # to full, so without it the demo would measure one tier and hand over a command that runs
    # another, and the count would be wrong again for anyone who pasted it.
    ran = len(pre.get("detectors", {})) or 1
    print(
        "[3/3] Ready to humanize!\n"
        f"\n"
        f"  untell humanize \"{sample_text[:60]}...\" --rewriter composite --tier {demo_tier}\n"
        f"\n"
        f"The closed loop will:\n"
        f"  1. Score your text against the {ran} detector{'' if ran == 1 else 's'} this install "
        f"loads at tier {demo_tier} (untell knows 15; the rest need heavier deps or API keys)\n"
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
    for name in ["composite", "structural", "surgical", "targeted", "neural", "ensemble",
                 "t5_paraphrase", "mt_pivot", "anthropic", "openai"]:
        rw = get_rewriter(prefer=name)
        status = "✓" if rw and rw.available() else "✗"
        print(f"  {status} {name}")
    # The trained local-policy rewriter gets its own line because its unavailability needs the
    # REASON, not just a check mark: the adapter dir may be set while peft/torch/transformers are
    # missing, and the reason names the extra that installs them (issue #34).
    from untell.rewriter.local_policy import LocalPolicyRewriter
    _lp = LocalPolicyRewriter()
    _lp_reason = _lp.unavailable_reason()
    print(f"  {'✓' if _lp_reason is None else '✗'} local (trained policy)"
          + ("" if _lp_reason is None else f" — {_lp_reason}"))

    # API server
    try:
        from untell.api_server import app
        print(f"\nAPI Server: ✓ (v{app.version})")
    except Exception:
        print("\nAPI Server: ✗ (install: pip install untell[server])")

    # Rich output. The try body used to be a bare print(), which cannot fail — so this always
    # reported the extra as installed regardless of whether it was. Actually import it.
    try:
        import rich  # noqa: F401

        print("Rich output: ✓")
    except Exception:
        print("Rich output: ✗ (install: pip install untell[rich])")

    print(f"\nEnvironment: Python {sys.version.split()[0]} on {sys.platform}")
    if available:
        print("\n✓ All systems nominal")
        return 0
    # Exit non-zero so `untell check` can gate a CI job or an install script. Returning 0 while
    # printing "No detectors available" told every automated caller the install was healthy.
    print("\n! No detectors available — install: pip install untell[full]")
    return 1


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

    # First arg is NOT a known command → treat as humanize shortcut.
    #
    # That shortcut is documented and useful (`untell "some AI text"`), but it swallowed every
    # mistyped or unavailable subcommand: the name became the TEXT. MEASURED:
    #
    #     untell notacommand --json   ->   {"final": "notacommand", ...}   exit 0
    #
    # The word was humanized and returned as the answer, with no error and a success exit. Same for
    # `untell voice ...`, `untell server ...`, `untell mcp ...` — real entry points this project
    # ships as `untell-voice`, `untell-server`, `untell-mcp`, which are NOT subcommands here.
    #
    # Guessing is not safe in general — a single word really can be the text someone wants rewritten
    # — so this refuses only for names the PROJECT ITSELF ships as a console script. Those are words
    # a user typed because they read the docs, not prose they want humanized, and the message points
    # at the command that does exist.
    if cmd in _STANDALONE_ONLY:
        for line in (
            f"error: {cmd!r} is not an `untell` subcommand — it is a separate command, "
            f"`untell-{cmd}`.",
            f"       Run `untell-{cmd} --help`, or `untell --help` for the subcommands.",
            f"       (To humanize the literal word {cmd!r}, pass it after `untell humanize`.)",
        ):
            print(line, file=sys.stderr)
        return 2

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
