"""restore_layout_lines must protect aligned-line documents (regression).

The guard `if len(mask) == len(src): return transformed` was inverted (should be
`!=`) — on the EXACT case where line-index alignment makes protection possible
and necessary, the transformed (possibly corrupted) text was returned untouched.
Surgical/composite/targeted then rewrote identifiers inside indented code blocks.
This pins the aligned case directly: a word substituted inside an indented code
block must be restored from the original.
"""
from untell.layout import restore_layout_lines

DOC = "Prose here.\n\n    def f():\n        return utilize(x)\n\nMore prose."


def test_aligned_document_restores_code_block():
    transformed = DOC.replace("utilize", "use")
    out = restore_layout_lines(DOC, transformed)
    assert "return utilize(x)" in out  # original identifier restored
    assert "return use(x)" not in out  # substitution inside code block reverted


def test_misaligned_document_returns_transformed():
    # A reflowing transform (line-count change) cannot align: the transformed text
    # must be returned untouched rather than guessed through.
    transformed = DOC + "\nExtra line"
    out = restore_layout_lines(DOC, transformed)
    assert out == transformed
