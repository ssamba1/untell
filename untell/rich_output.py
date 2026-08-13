"""Rich CLI output helpers — colored diffs, before/after tables, progress bars.

Optional dependency (``pip install untell[rich]``). Degrades gracefully to plain text
when ``rich`` is not installed.
"""

from __future__ import annotations

# Lazy import so the module is always importable.
_RICH: bool = False

# How close to the verdict cut still reads as "borderline" rather than "clear". The loop's own
# noise band, so a run that lands just under the cut is not reported as comfortably clean.
_VERDICT_BAND = 0.10

# At or above this, the ensemble max cannot show an improvement, so a flat delta beside it is not
# evidence that nothing happened. MEASURED over 80 corpus texts: the max reaches >=0.999 on 100% of
# HC3 AI text and 30% of RAID's, against 0% of human text. Set at 0.99 rather than 0.999 so a
# detector pinned just below the rounding edge is caught too; the human side of both corpora is
# nowhere near it.
#
# The detector doing it is `hc3_roberta`, not `roberta_openai` as this comment used to say. Re-measured
# on 60 HC3 AI sentences and the 12 documents they came from:
#
#     detector           sentences >=0.99   sentence mean   documents >=0.99   document mean
#     hc3_roberta            58 / 60           0.9977          12 / 12            0.9992
#     roberta_openai          2 / 60           0.7405          11 / 12            0.9962
#     fast_detectgpt          0 / 60           0.6451           0 / 12            0.6183
#
# "0.9992 on nearly every sentence" was hc3_roberta's number attributed to its neighbour, and the
# distinction is not pedantic: under rewriting `roberta_openai` drops 0.9986 -> 0.6228 while
# hc3_roberta does not move at all, because it is fine-tuned ON HC3 and the corpus is in-distribution
# for it. A reader trusting the old attribution would go looking for the pin in the one detector that
# demonstrably yields.
#
# A LEVEL test rather than a movement test, and that is measured too. A detector stuck at, say, 0.85
# pins the delta just as effectively and sits below this bar, so the criterion could in principle
# miss one. Over 30 real composite rewrites of HC3 and RAID text: 16 fired this note, and **0** had a
# max that moved less than 0.01 while the mean moved more than 0.05. The simpler test loses nothing
# that has been observed.
_SATURATED_MAX = 0.99
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
    tells_before: int | None = None,
    tells_after: int | None = None,
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

    # A pinned max reports "no change" on text that did change. MEASURED through the pipeline at the
    # full tier: 4 documents rewritten, tells/100w 3.80 -> 2.98, and `max` sat at 0.9997 before and
    # after — so the Delta column below printed "—" on a 22% cut in tell density. The mean moves
    # where the max cannot, and it is already in both score dicts; withholding it here leaves the
    # reader with the one number that provably could not see what happened.
    saturated = (
        isinstance(pre_score.get("max"), (int, float))
        and isinstance(post_score.get("max"), (int, float))
        and pre_score["max"] >= _SATURATED_MAX
        and post_score["max"] >= _SATURATED_MAX
    )
    mean_note = ""
    if saturated:
        pre_mean, post_mean = pre_score.get("mean"), post_score.get("mean")
        if isinstance(pre_mean, (int, float)) and isinstance(post_mean, (int, float)):
            mean_note = (
                f"The hardest detector is pinned at {post_score['max']:.4f}, so the P(AI) delta "
                f"above cannot show an improvement either way. Ensemble mean: "
                f"{pre_mean:.4f} -> {post_mean:.4f}."
            )
        else:
            mean_note = (
                f"The hardest detector is pinned at {post_score['max']:.4f}, so the P(AI) delta "
                "above cannot show an improvement either way."
            )

    if not _RICH:
        # Fallback: plain text
        print(f"Iterations: {iterations}  Stopped: {stopped}")
        print(f"Before: P(AI)={pre_score.get('max', 0):.2f}  After: P(AI)={post_score.get('max', 0):.2f}")
        if mean_note:
            print(mean_note)
        if note:
            print(f"\n{note}")
        # The tell counts, which this branch also dropped. The rich table has an "AI tells" row and
        # this one printed nothing, so the before/after pair that is often the ONLY thing that moves
        # — on a corpus where the detectors saturate, `max` can gain 0.0000 while tells fall 4 -> 0
        # — was invisible to exactly the users who cannot see the table.
        if tells_before is not None and tells_after is not None:
            print(f"AI tells: {tells_before} -> {tells_after}")

        # The caveat, which this branch used to drop entirely.
        #
        # The rich branch prints it; this one returned first. That makes it the seventh surface in
        # this repo where a warning reached the RESULT and not the READER — and the worst placed of
        # them, because it is what a `pip install untell` user sees: the `rich` extra is optional,
        # and `run.py`'s `except ImportError` fallback to `_render` (which does print the caveat)
        # is unreachable, since importing this module always succeeds and merely sets `_RICH` False.
        #
        # So a caller without the extra ran the loop, got a number, and was never told the number
        # came from the path where 64% of human text scores above the threshold.
        if warning:
            print(f"\nNOTE: {warning}")
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
    if mean_note:
        _CONSOLE.print(f"[yellow]{mean_note}[/]")

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

    # This row glosses the P(AI) number directly above it, so it is labelled against the threshold
    # that decides `flagged` — the product's own calibrated cut — rather than by borrowing another
    # metric's bands.
    #
    # It used to call `classification((1 - p_ai) * 100)`. That function's boundaries are fitted to
    # `humanness()` scores specifically, and its docstring says so: "lowest HUMAN score 75.6,
    # highest AI score 72.0 ... a boundary at 75 misclassifies 0 of 80". `(1 - P(AI)) * 100` is a
    # different quantity on a different scale, and feeding it those bands made two surfaces label
    # the same text differently. MEASURED on 60 HC3 and RAID texts, comparing
    # `classification(humanness(t))` against `classification((1 - max) * 100)`:
    #
    #     labels agree on 18 of 60 — 30%
    #
    # So `untell humanize` and `untell humanness` disagreed about the same paragraph seven times in
    # ten, using the same labelling function. The earlier fix recorded here was real — passing
    # P(AI) in raw made the row constant — but rescaling it into the wrong calibration replaced a
    # constant with a mislabel.
    #
    # `verdict_threshold` is what `flagged` compares against, so this row and that field can no
    # longer disagree. The band around it is the loop's own noise width.
    cut = post_score.get("verdict_threshold", post_score.get("threshold", 0.30))

    def _verdict(p_ai: float) -> str:
        if p_ai >= cut:
            return "flagged"
        return "borderline" if p_ai >= cut - _VERDICT_BAND else "clear"

    table.add_row("P(AI) max", f"{before_max:.2f}", f"{after_max:.2f}", f"[{delta_style}]{delta_str}[/]")
    table.add_row("Verdict", _verdict(before_max), _verdict(after_max), "")

    # AI tells, when the caller has them. On a saturating corpus this is the only row that moves:
    # MEASURED on 4 HC3 documents at full tier, P(AI) max gained +0.0000 on 4 of 4 while tells fell
    # 4->0, 1->0 and 1->0. Without this row the table read "P(AI) 1.00 -> 1.00, delta 0" on text
    # whose machine-writing markers had been removed, and a user would reasonably conclude the run
    # had done nothing.
    #
    # Optional rather than computed here: this module renders, it does not measure, and making it
    # score would put a second tells implementation behind a different code path.
    if tells_before is not None and tells_after is not None:
        tells_delta = tells_after - tells_before
        table.add_row(
            "AI tells",
            str(tells_before),
            str(tells_after),
            f"[{'green' if tells_delta < 0 else 'dim'}]{tells_delta:+d}[/]",
        )

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
