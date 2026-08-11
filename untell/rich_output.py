"""Rich CLI output helpers — colored diffs, before/after tables, progress bars.

Optional dependency (``pip install untell[rich]``). Degrades gracefully to plain text
when ``rich`` is not installed.
"""

from __future__ import annotations

# Lazy import so the module is always importable.
_RICH: bool = False
try:
    from rich.console import Console as _Console
    from rich.panel import Panel as _Panel
    from rich.table import Table as _Table
    from rich.text import Text as _Text

    _CONSOLE = _Console()
    _RICH = True
except Exception:
    _CONSOLE = None


def _diff_words(a: str, b: str) -> str:
    """Word-level diff of two strings. Returns rich-markup string or plain.

    Uses `difflib` rather than comparing word *i* of one against word *i* of the other. The
    positional version was correct only when the rewrite preserved word count exactly, because a
    single insertion shifts every following word out of alignment and paints it as changed.
    MEASURED on a seven-word sentence:

        one word inserted at the front   7 of 8 words marked changed
        one word inserted mid-sentence   6 of 8
        one word deleted                 5 of 6
        one word substituted             1 of 7      <- the only shape it got right

    This is the report a user reads to see what the loop did, and the loop inserts openers, deletes
    transitions and splits sentences on almost every run — so the common case was the broken one,
    and the tool was claiming to have rewritten a paragraph it had barely touched. That is the
    opposite of what it exists to demonstrate.

    `SequenceMatcher` is stdlib, so this costs no dependency on the zero-dependency tier.
    """
    if not _RICH:
        return b
    import difflib

    a_words = a.split()
    b_words = b.split()
    result = _Text()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a_words, b_words).get_opcodes():
        if tag == "equal":
            result.append(" ".join(b_words[j1:j2]) + " ")
        elif tag in ("replace", "insert"):
            result.append(" ".join(b_words[j1:j2]) + " ", style="bold green")
        elif tag == "delete":
            # Show WHAT was removed, struck through, rather than a blank. The positional version
            # appended a bare space here, so a deleted clause left no trace in the report at all —
            # and "did the rewriter drop my content" is one of the questions this view exists to
            # answer.
            result.append(" ".join(a_words[i1:i2]) + " ", style="dim strike")
    return result


def print_humanize_result(
    original: str,
    final: str,
    pre_score: dict,
    post_score: dict,
    iterations: int,
    stopped: str,
    warning: str | None = None,
):
    """Print a professional before/after comparison to the terminal."""
    # An unchanged result is a real outcome — the loop returns the original when no candidate beat
    # it, deliberately, rather than forcing a rewrite that spends meaning for nothing. But the
    # header said "humanization complete", the delta column showed "—", and the two text panels
    # were identical: a run that did nothing was reported exactly like a successful one. Say it.
    no_change = final == original
    note = ""
    if no_change:
        still = post_score.get("max")
        still_txt = f" It still scores P(AI) {still:.2f}." if isinstance(still, (int, float)) else ""
        note = (
            "No change was made: no candidate rewrite scored better than the original, so the "
            f"original is returned unmodified.{still_txt} Try --best-of 3, a higher --intensity, "
            "or a different --rewriter."
        )

    if not _RICH:
        # Fallback: plain text
        print(f"Iterations: {iterations}  Stopped: {stopped}")
        print(f"Before: P(AI)={pre_score.get('max', 0):.2f}  After: P(AI)={post_score.get('max', 0):.2f}")
        if note:
            print(f"\n{note}")
        print(f"\n--- Original ---\n{original}")
        print(f"\n--- Humanized ---\n{final}")
        return

    # Header
    _CONSOLE.print()
    header = _Table.grid(padding=1)
    header.add_column(style="bold cyan")
    plural = "s" if iterations != 1 else ""
    header.add_row(
        f"untell — {'NO CHANGE MADE' if no_change else 'humanization complete'} "
        f"({iterations} iteration{plural})"
    )
    _CONSOLE.print(_Panel(header, style="yellow" if no_change else "cyan"))
    if note:
        _CONSOLE.print(f"[yellow]{note}[/]")

    # Score comparison
    table = _Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric")
    table.add_column("Before")
    table.add_column("After")
    table.add_column("Delta")

    before_max = pre_score.get("max", 0)
    after_max = post_score.get("max", 0)
    delta = after_max - before_max
    delta_str = f"{delta:+.2f}" if abs(delta) > 0.001 else "—"
    delta_style = "green" if delta < 0 else ("red" if delta > 0 else "white")

    from untell.humanness import classification

    # `classification()` takes a HUMANNESS score in 0-100 (higher = more human); `max` is P(AI) in
    # 0-1. Passing P(AI) straight in meant every value landed under the bottom band, so the Verdict
    # row printed "AI" -> "AI" for every input, including a run that took 0.86 down to 0.02. It was
    # not merely wrong, it was constant — the row carried no information at all.
    def _verdict(p_ai: float) -> str:
        return classification((1.0 - p_ai) * 100.0)

    table.add_row("P(AI) max", f"{before_max:.2f}", f"{after_max:.2f}", f"[{delta_style}]{delta_str}[/]")
    table.add_row("Verdict", _verdict(before_max), _verdict(after_max), "")

    if "tier" in pre_score:
        table.add_row("Tier", pre_score.get("tier", "?"), post_score.get("tier", "?"), "")
    table.add_row("Iterations", "", str(iterations), "")
    table.add_row("Stopped", "", stopped.replace("_", " ").title(), "")
    _CONSOLE.print(table)

    # Side-by-side diff — pointless when nothing moved, and printing the same text in two panels
    # labelled "Original" and "Humanized" actively suggests something happened.
    if not no_change:
        _CONSOLE.print("\n[bold]Before → After[/]")
        _CONSOLE.print(_diff_words(original, final))
        _CONSOLE.print()
        _CONSOLE.print(_Panel(original[:2000] + ("..." if len(original) > 2000 else ""), title="Original", border_style="yellow"))
        _CONSOLE.print(_Panel(final[:2000] + ("..." if len(final) > 2000 else ""), title="Humanized", border_style="green"))
    else:
        _CONSOLE.print()
        _CONSOLE.print(_Panel(
            original[:2000] + ("..." if len(original) > 2000 else ""),
            title="Text (unchanged)", border_style="yellow",
        ))
    # After the panels, not before: the output is what the reader came for. A payload the caller
    # asked to keep (`--no-scrub`) still travels in that output, and nothing else says so.
    if warning:
        _CONSOLE.print()
        _CONSOLE.print(_Panel(warning, title="Warning", border_style="red"))
    _CONSOLE.print()


def print_tells_result(tells: dict):
    """Print a formatted AI-tells breakdown."""
    if not _RICH:
        print(f"Tells: {tells.get('tells', 0)} ({tells.get('tells_per_100w', 0)}/100w)")
        # Burstiness was reported only when `rich` happened to be installed, so on a plain terminal
        # the single strongest stylometric tell — uniform sentence length, the one signal the tell
        # CATALOGUE cannot see — was simply absent from the output. Same `is not None` rule as the
        # rich path below: a CV of exactly 0.0 is the most extreme case, not a missing value.
        if tells.get("burstiness_cv") is not None:
            suffix = "  (uniform = tell)" if tells.get("low_burstiness") else ""
            print(f"Burstiness CV: {tells['burstiness_cv']}{suffix}")
        for cat, count in sorted(tells.get("by_category", {}).items(), key=lambda kv: -kv[1]):
            print(f"  {cat}: {count}")
        return

    _CONSOLE.print()
    header = _Text()
    header.append(f"AI Tells: {tells.get('tells', 0)}  ", style="bold")
    header.append(f"({tells.get('tells_per_100w', 0)}/100 words)", style="dim")
    _CONSOLE.print(header)

    # `is not None`, not truthiness: a CV of exactly 0.0 means perfectly uniform sentence lengths —
    # the single strongest burstiness tell there is — and falsy-zero hid that row precisely when it
    # mattered most. None still means "undefined" (fewer than two sentences).
    if tells.get("burstiness_cv") is not None:
        cv = tells["burstiness_cv"]
        bstyle = "red" if tells.get("low_burstiness") else "green"
        _CONSOLE.print(f"Burstiness CV: [{bstyle}]{cv}[/]" + (" [dim](uniform = tell)[/]" if tells.get("low_burstiness") else ""))

    if tells.get("by_category"):
        table = _Table(show_header=True, header_style="bold")
        table.add_column("Category")
        table.add_column("Count")
        for cat, count in sorted(tells["by_category"].items(), key=lambda kv: -kv[1]):
            style = "red" if count >= 3 else ("yellow" if count >= 2 else "white")
            table.add_row(f"[{style}]{cat}[/]", str(count))
        _CONSOLE.print(table)
    else:
        _CONSOLE.print("[green]No catalogued tells found.[/]")
    _CONSOLE.print()


def print_humanness(score: float, cls: str):
    """Print a formatted humanness score."""
    if not _RICH:
        print(f"Humanness: {score}/100 ({cls})")
        return

    bar_len = 30
    filled = int(score / 100 * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    if score >= 70:
        color = "green"
    elif score >= 40:
        color = "yellow"
    else:
        color = "red"
    _CONSOLE.print(f"\nHumanness: [bold {color}]{score:.1f}/100[/]  ({cls})")
    _CONSOLE.print(f"[{color}]{bar}[/]")
    _CONSOLE.print()


def progress_iteration(current: int, total: int, tier: str, score: float | None = None) -> str | None:
    """Print a progress line for a loop iteration. Returns status string."""
    if not _RICH:
        score_str = f" P(AI)={score:.2f}" if score is not None else ""
        print(f"[{current}/{total}] tier={tier}{score_str}")
        return None
    score_part = f"  P(AI)={score:.2f}" if score is not None else ""
    _CONSOLE.print(f"  [dim]→ Iteration {current}/{total}[/]  tier={tier}{score_part}")
    return None
