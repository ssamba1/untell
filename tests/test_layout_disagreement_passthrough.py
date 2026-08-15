"""Killing test: restore_layout_lines must merge on aligned lines, pass through on disagreement.

The guard comment says 'a classifier/line disagreement is not something to guess
through'. The check is `len(mask) != len(src)` — return transformed untouched ONLY
when the mask count disagrees with the source count. A flipped guard (`==`)
returns transformed on the ALIGNED normal case, skipping the merge entirely:
code fences and math blocks get rewritten instead of restored.

MEASURED: aligned 4-line doc with a code fence — `==` mutant returns the
rewritten fence (AAA/BBB/CCC), correct `!=` restores it (```/code line/```).
"""

from untell.layout import restore_layout_lines


def test_aligned_restores_code_fence() -> None:
    orig = "```\ncode line\n```\nplain"   # mask [F,F,F,T] == 4 slots == src 4
    out = "AAA\nBBB\nCCC\nDDD"            # aligned, 4 lines
    result = restore_layout_lines(orig, out)
    # The fence must be restored from the original, prose line takes the rewrite.
    assert result == "```\ncode line\n```\nDDD"


def test_disagreement_passes_through_unmerged() -> None:
    orig = "alpha\nbeta\ngamma"
    out = "ALPHA\nBETA"  # one line shorter: src(3) vs out(2)
    result = restore_layout_lines(orig, out)
    # Disagreement -> passthrough, NOT a truncated zip-merge.
    assert result == out
