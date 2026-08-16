"""Tests for `untell humanize --diff` — a unified-style diff of only the changed lines.

The humanize path already paints a word-level before/after (`_diff_words`), but a reader
checking "what did the loop actually change" at the sentence level gets a colour wash over
the whole paragraph. `--diff` is the line-level view: unified-diff-style, NO context
lines, deletions and additions only — exactly what `git diff` shows when the humanizer
rewrote a paragraph.

This file pins four properties:

1. **Faithfulness** — every `-` line is a line of the original, every `+` line a line of
   the final text, and applying the hunks to the original reconstructs the final text
   exactly. The diff IS the rewrite; a diff that lied would be the report arguing against
   the thing it exists to demonstrate (the same failure mode `_diff_words` had before the
   difflib fix, recorded in test_the_diff_report_is_a_diff.py).

2. **Minimality** — only changed lines appear. The `autojunk=False` matcher is load-bearing:
   `SequenceMatcher` junking repeats above 1% of a 200+ line sequence reports a block swap
   as one giant replace; the true minimal edit must survive.

3. **The lock tie-in** — the payload is built on the explain machinery (`explain_spans`,
   the same single source of truth `lock()` uses), and `locks_preserved` checks the restore
   contract: every frozen span must survive byte-for-byte in the final text.

4. **CLI contract** — `--diff` prints the human view, `--diff --json` emits the payload as
   parseable JSON, and both hold on the error paths (`--json` mode must stay parseable —
   the contract pinned by test_json_mode_holds_on_the_error_paths.py).
"""

from __future__ import annotations

import json

from untell import rich_output
from untell.rich_output import _hunk_header, _unified_range, humanize_diff, print_humanize_diff
from untell.scripts.run import main

AI = (
    "Furthermore, artificial intelligence has fundamentally transformed numerous industries. "
    "Moreover, organizations utilize it to significantly improve operational efficiency. Overall, "
    "the impact continues to grow across various sectors according to Smith (2020), rising 47%."
)


# ---------------------------------------------------------------------------
# humanize_diff — the payload
# ---------------------------------------------------------------------------


def test_only_changed_lines_are_reported() -> None:
    original = "\n".join(
        [
            "The first sentence remains exactly as it was written.",
            "The second sentence gets rewritten by the loop.",
            "The third sentence stays untouched as well.",
        ]
    )
    final = "\n".join(
        [
            "The first sentence remains exactly as it was written.",
            "The loop rewrote the second sentence entirely.",
            "The third sentence stays untouched as well.",
        ]
    )
    diff = humanize_diff(original, final)
    assert diff["changed"] is True
    assert len(diff["hunks"]) == 1
    hunk = diff["hunks"][0]
    assert hunk["lines"] == [
        {"kind": "-", "text": "The second sentence gets rewritten by the loop."},
        {"kind": "+", "text": "The loop rewrote the second sentence entirely."},
    ]
    # Only the changed lines: the unchanged neighbours must not appear in any hunk.
    flat = " ".join(line["text"] for h in diff["hunks"] for line in h["lines"])
    assert "first sentence" not in flat
    assert "third sentence" not in flat
    assert diff["added_lines"] == 1 and diff["removed_lines"] == 1


def test_the_diff_is_faithful_to_both_texts() -> None:
    original = "alpha\nbeta\ngamma\ndelta\n"
    final = "alpha\nbeta\nEPSILON\nzeta\n"
    diff = humanize_diff(original, final)
    orig_lines = set(original.splitlines())
    final_lines = set(final.splitlines())
    for hunk in diff["hunks"]:
        for line in hunk["lines"]:
            if line["kind"] == "-":
                assert line["text"] in orig_lines, f"- line not in original: {line['text']!r}"
            else:
                assert line["text"] in final_lines, f"+ line not in final: {line['text']!r}"
    # On duplicate-free text, no line appears on both sides of the diff.
    emitted = {line["text"] for hunk in diff["hunks"] for line in hunk["lines"]}
    assert not (emitted & orig_lines & final_lines)


def test_the_diff_is_the_rewrite() -> None:
    """Applying the hunks to the original reconstructs the final text exactly.

    The diff must not merely LOOK like the edit — it must BE the edit. Any hunk that
    duplicates, drops or misorders a line breaks this round-trip.
    """
    original = "One\nTwo\nThree\nFour\nFive\nSix\n"
    final = "One\nTwo, edited\nThree\nFive\nSix, appended\n"
    diff = humanize_diff(original, final)
    lines = original.splitlines()
    out: list[str] = []
    idx = 0
    for hunk in diff["hunks"]:
        out.extend(lines[idx : hunk["start_original"]])
        out.extend(line["text"] for line in hunk["lines"] if line["kind"] == "+")
        idx = hunk["start_original"] + hunk["count_original"]
    out.extend(lines[idx:])
    assert out == final.splitlines()


def test_multiple_hunks_keep_order_and_positions() -> None:
    original = "a\nb\nc\nd\ne\nf\ng\n"
    final = "a\nB\nc\nd\nE\nf\ng\n"
    diff = humanize_diff(original, final)
    assert len(diff["hunks"]) == 2
    first, second = diff["hunks"]
    assert first["start_original"] == 1 and first["count_original"] == 1
    assert second["start_original"] == 4 and second["count_original"] == 1
    assert first["start_final"] == 1 and second["start_final"] == 4
    assert first["lines"][0] == {"kind": "-", "text": "b"}
    assert first["lines"][1] == {"kind": "+", "text": "B"}
    assert diff["added_lines"] == 2 and diff["removed_lines"] == 2


def test_identical_text_is_not_a_diff() -> None:
    text = "Nothing here changed at all.\nNot even the second line.\n"
    diff = humanize_diff(text, text)
    assert diff["changed"] is False
    assert diff["hunks"] == []
    assert diff["added_lines"] == 0 and diff["removed_lines"] == 0


def test_empty_sides() -> None:
    added = humanize_diff("", "the whole text was inserted")
    assert added["changed"] is True
    assert added["added_lines"] == 1 and added["removed_lines"] == 0
    assert added["hunks"][0]["count_original"] == 0
    assert added["hunks"][0]["lines"] == [{"kind": "+", "text": "the whole text was inserted"}]

    removed = humanize_diff("the whole text was deleted", "")
    assert removed["changed"] is True
    assert removed["added_lines"] == 0 and removed["removed_lines"] == 1
    assert removed["hunks"][0]["count_final"] == 0


def test_repeated_lines_do_not_corrupt_the_diff() -> None:
    """autojunk regression: the default matcher junking repeats (200+ lines) reported a
    two-block order swap as ONE 200-line replace. The payload must report the minimal edit.

    Sentence reordering is a documented structural transform of this loop, so this shape is
    a real humanization, not a pathological corner.
    """
    original = ["X"] * 100 + ["L"] * 100 + ["Y"]
    final = ["L"] * 100 + ["X"] * 100 + ["Y"]
    diff = humanize_diff("\n".join(original), "\n".join(final))
    assert diff["added_lines"] == 100 and diff["removed_lines"] == 100
    assert not (len(diff["hunks"]) == 1 and diff["hunks"][0]["count_original"] == 200), (
        "the default autojunk heuristic collapsed the swap into one giant replace"
    )


def test_payload_is_json_serialisable() -> None:
    diff = humanize_diff("The cost rose to $500 in 2024.\n", "The cost climbed to $500 in 2024.\n")
    text = json.dumps(diff, ensure_ascii=True)
    parsed = json.loads(text)
    assert parsed["format"] == "untell-diff"
    assert parsed["version"] == 1
    assert parsed["hunks"] == diff["hunks"]


def test_hunk_headers_match_difflib_range_format() -> None:
    """The header must use difflib's own range rendering (single line -> bare number,
    empty range -> `start,0`), so the human view matches what `git diff` would print."""
    assert _unified_range(0, 1) == "1"
    assert _unified_range(3, 4) == "4"
    assert _unified_range(0, 3) == "1,3"
    assert _unified_range(2, 5) == "3,3"
    assert _unified_range(4, 4) == "4,0"
    # Pure insertion at the top of the file renders as `-0,0`, exactly like difflib.
    assert _hunk_header({"start_original": 0, "count_original": 0,
                         "start_final": 0, "count_final": 1}) == "@@ -0,0 +1 @@"
    assert _hunk_header({"start_original": 1, "count_original": 1,
                         "start_final": 1, "count_final": 1}) == "@@ -2 +2 @@"
    assert _hunk_header({"start_original": 0, "count_original": 3,
                         "start_final": 0, "count_final": 4}) == "@@ -1,3 +1,4 @@"


# ---------------------------------------------------------------------------
# the lock/explain tie-in
# ---------------------------------------------------------------------------


def test_locks_are_carried_and_counted() -> None:
    locks = [
        {"sentinel": "⟦HZ0000⟧", "span": "$500", "rules": ["number"]},
        {"sentinel": "⟦HZ0001⟧", "span": "Smith (2020)", "rules": ["citation"]},
        {"sentinel": "⟦HZ0002⟧", "span": "DROPPED SPAN", "rules": ["identifier"]},
    ]
    diff = humanize_diff(
        "The cost rose to $500 per Smith (2020).",
        "The cost climbed to $500 per Smith (2020).",
        locked_spans=locks,
    )
    assert diff["locked_spans"] == locks
    assert diff["locks_preserved"] == 2  # the third span does not survive in final


def test_locks_are_absent_when_not_asked_for() -> None:
    diff = humanize_diff("a\n", "b\n")
    assert "locked_spans" not in diff
    assert "locks_preserved" not in diff


# ---------------------------------------------------------------------------
# the renderers
# ---------------------------------------------------------------------------


def test_plain_renderer_shows_only_changed_lines(monkeypatch, capsys) -> None:
    monkeypatch.setattr(rich_output, "_RICH", False)
    diff = humanize_diff("One\nTwo\nThree\n", "One\nTwo, changed\nThree\n")
    print_humanize_diff(diff)
    out = capsys.readouterr().out
    assert "humanization diff" in out
    assert "@@ -2 +2 @@" in out
    assert "- Two" in out
    assert "+ Two, changed" in out
    # Unchanged lines must not render: the unchanged line "Two" appears only as a diff line.
    assert "\nTwo\n" not in out


def test_plain_renderer_reports_no_change(monkeypatch, capsys) -> None:
    monkeypatch.setattr(rich_output, "_RICH", False)
    diff = humanize_diff("Same.\n", "Same.\n")
    print_humanize_diff(diff)
    out = capsys.readouterr().out
    assert "No lines changed" in out
    assert "@@" not in out


def test_plain_renderer_reports_locked_spans(monkeypatch, capsys) -> None:
    monkeypatch.setattr(rich_output, "_RICH", False)
    locks = [{"sentinel": "⟦HZ0000⟧", "span": "47%", "rules": ["number"]}]
    diff = humanize_diff("Up 47%.\n", "Rose 47%.\n", locked_spans=locks)
    print_humanize_diff(diff)
    assert "1 locked span" in capsys.readouterr().out


def test_plain_renderer_warns_when_a_lock_did_not_survive(monkeypatch, capsys) -> None:
    monkeypatch.setattr(rich_output, "_RICH", False)
    locks = [{"sentinel": "⟦HZ0000⟧", "span": "vanished fact", "rules": ["identifier"]}]
    diff = humanize_diff("The vanished fact is gone.\n", "All gone.\n", locked_spans=locks)
    print_humanize_diff(diff)
    out = capsys.readouterr().out
    assert "did NOT survive" in out


def test_rich_renderer_escapes_markup_and_colours(monkeypatch) -> None:
    """Brackets in a user line must not be parsed as rich markup — the same `_Text` rule as
    print_humanize_result's panels (a user text like "See [1]" used to render as "See  .")."""
    from rich.text import Text

    printed: list[tuple] = []
    monkeypatch.setattr(rich_output, "_RICH", True)
    monkeypatch.setattr(rich_output, "_Text", Text)
    monkeypatch.setattr(
        rich_output, "_CONSOLE", type("C", (), {"print": lambda self, *a, **k: printed.append(a)})()
    )
    diff = humanize_diff("See [1] and [citation needed].\n", "See [1] and the citation.\n")
    print_humanize_diff(diff)
    rendered = "".join(
        str(arg.plain) if hasattr(arg, "plain") else str(arg) for args in printed for arg in args
    )
    assert "[1]" in rendered, "markup brackets were swallowed instead of printed verbatim"
    assert "[citation needed]" in rendered
    assert "@@ -1 +1 @@" in rendered


# ---------------------------------------------------------------------------
# the CLI contract
# ---------------------------------------------------------------------------

EDITED = AI.replace("fundamentally transformed", "deeply reshaped")


class _EditRW:
    """Rewriter that makes ONE light, similarity-preserving edit and keeps sentinels.

    A real rewrite a reader would accept: two words swapped in a 40-word paragraph, so the
    meaning gate and the similarity bar let it through while the text genuinely changes.
    """

    name = "edit"

    def available(self):
        return True

    def rewrite(self, text, score_result, threshold=0.30):
        return text.replace("fundamentally transformed", "deeply reshaped")


class _IdentityRW:
    """Rewriter that returns the input unchanged — the loop has nothing to adopt."""

    name = "identity"

    def available(self):
        return True

    def rewrite(self, text, score_result, threshold=0.30):
        return text


class _BrokenRW:
    """Rewriter that raises — untell_text must surface the failure as a result error."""

    name = "broken"

    def available(self):
        return True

    def rewrite(self, text, score_result, threshold=0.30):
        raise RuntimeError("simulated rewriter failure")


def _fixed_score(mapping: dict, default: float = 0.8):
    """score_text stand-in keyed on exact text — the same shape test_run.py uses.

    The loop scores the RESTORED text (score() restores before judging), so the keys are
    plain strings: the original and the one-edit candidate.
    """

    def _s(text, tier="full", threshold=0.3):
        mx = mapping.get(text.strip(), default)
        return {
            "tier": tier,
            "detectors": {"perplexity_burstiness": mx},
            "max": mx,
            "mean": mx,
            "threshold": threshold,
            "flagged": mx >= threshold,
            "scored": True,
        }

    return _s


def _patch_cli(monkeypatch, rewriter, scores: dict, default: float = 0.8) -> None:
    """Wire the CLI's rewriter and scorer to deterministic stand-ins.

    `main()` resolves its rewriter via a LOCAL `from untell.rewriter import get_rewriter`,
    so the attribute on the package module is the one to replace (patching the module-global
    in run.py only reaches direct `untell_text` calls). The loop's `score_text` is a plain
    module-global, patched as usual.
    """
    import untell.rewriter as rewriter_mod
    import untell.scripts.run as run_mod

    monkeypatch.setenv("UNTELL_LITE_NO_TORCH", "1")
    monkeypatch.setattr(rewriter_mod, "get_rewriter", lambda prefer=None: rewriter)
    monkeypatch.setattr(run_mod, "score_text", _fixed_score(scores, default))


def test_cli_diff_human_output(monkeypatch, capsys) -> None:
    _patch_cli(monkeypatch, _EditRW(), {AI: 0.80, EDITED: 0.20})
    rc = main(["--tier", "lite", "--diff", AI])
    assert rc == 0
    out = capsys.readouterr().out
    assert "humanization diff" in out
    assert "@@ -1 +1 @@" in out, "no unified-diff hunk header in output"
    assert "- Furthermore" in out, "no deletion line"
    assert "deeply reshaped" in out, "no addition line"
    assert "2 locked span" in out, "the explain/lock tie-in note is missing"
    # The standard render must not run: its markers are how you can tell.
    assert "--- Original ---" not in out
    assert "Before → After" not in out


def test_cli_diff_json_payload(monkeypatch, capsys) -> None:
    _patch_cli(monkeypatch, _EditRW(), {AI: 0.80, EDITED: 0.20})
    rc = main(["--tier", "lite", "--diff", "--json", AI])
    assert rc == 0
    out = capsys.readouterr().out
    out.encode("ascii")  # ensure_ascii -> portable
    parsed = json.loads(out)
    assert parsed["format"] == "untell-diff"
    assert parsed["changed"] is True
    assert len(parsed["hunks"]) == 1
    assert parsed["hunks"][0]["lines"] == [
        {"kind": "-", "text": AI},
        {"kind": "+", "text": EDITED},
    ]
    assert parsed["added_lines"] == 1 and parsed["removed_lines"] == 1
    # The loop restored the locked facts: both locked spans must survive byte-for-byte.
    spans = [row["span"] for row in parsed["locked_spans"]]
    assert "Smith (2020)" in spans and "47%" in spans
    assert parsed["locks_preserved"] == len(parsed["locked_spans"]) == 2


def test_cli_diff_json_reports_no_change(monkeypatch, capsys) -> None:
    _patch_cli(monkeypatch, _IdentityRW(), {}, default=0.8)
    rc = main(["--tier", "lite", "--diff", "--json", "--max-iters", "1", AI])
    assert rc == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["changed"] is False
    assert parsed["hunks"] == []


def test_cli_diff_json_error_path_holds(monkeypatch, capsys) -> None:
    """`--diff --json` with no input must answer JSON and exit 2, like `--json` alone."""
    _patch_cli(monkeypatch, _IdentityRW(), {})
    rc = main(["--tier", "lite", "--diff", "--json", "   "])
    assert rc == 2
    parsed = json.loads(capsys.readouterr().out)
    assert "error" in parsed


def test_cli_diff_reports_rewriter_failure(monkeypatch, capsys) -> None:
    _patch_cli(monkeypatch, _BrokenRW(), {}, default=0.9)
    rc = main(["--tier", "lite", "--diff", AI])
    assert rc == 1
    out = capsys.readouterr().out
    assert "ERROR" in out
    assert "rewriter failed" in out
