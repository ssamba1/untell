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
    """Simple word-level diff of two strings. Returns rich-markup string or plain."""
    if not _RICH:
        return b
    a_words = a.split()
    b_words = b.split()
    result = _Text()
    # Find added/changed words
    b_idx = 0
    for w in a_words:
        if b_idx < len(b_words) and w == b_words[b_idx]:
            result.append(w + " ")
            b_idx += 1
        else:
            # Word was removed or changed
            if b_idx < len(b_words):
                result.append(b_words[b_idx] + " ", style="bold green")
                b_idx += 1
            else:
                result.append(" ", style="dim")
    # Any remaining new words
    while b_idx < len(b_words):
        result.append(b_words[b_idx] + " ", style="bold green")
        b_idx += 1
    return result


def print_humanize_result(
    original: str,
    final: str,
    pre_score: dict,
    post_score: dict,
    iterations: int,
    stopped: str,
):
    """Print a professional before/after comparison to the terminal."""
    if not _RICH:
        # Fallback: plain text
        print(f"Iterations: {iterations}  Stopped: {stopped}")
        print(f"Before: P(AI)={pre_score.get('max', 0):.2f}  After: P(AI)={post_score.get('max', 0):.2f}")
        print(f"\n--- Original ---\n{original}")
        print(f"\n--- Humanized ---\n{final}")
        return

    # Header
    _CONSOLE.print()
    header = _Table.grid(padding=1)
    header.add_column(style="bold cyan")
    header.add_row(f"untell — humanization complete ({iterations} iteration{'s' if iterations != 1 else ''})")
    _CONSOLE.print(_Panel(header, style="cyan"))

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

    # Side-by-side diff
    _CONSOLE.print("\n[bold]Before → After[/]")
    _CONSOLE.print(_diff_words(original, final))

    # Full text panels
    _CONSOLE.print()
    _CONSOLE.print(_Panel(original[:2000] + ("..." if len(original) > 2000 else ""), title="Original", border_style="yellow"))
    _CONSOLE.print(_Panel(final[:2000] + ("..." if len(final) > 2000 else ""), title="Humanized", border_style="green"))
    _CONSOLE.print()


def print_tells_result(tells: dict):
    """Print a formatted AI-tells breakdown."""
    if not _RICH:
        print(f"Tells: {tells.get('tells', 0)} ({tells.get('tells_per_100w', 0)}/100w)")
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
