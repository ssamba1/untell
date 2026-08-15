"""layout.py must keep paragraph boundaries that end in non-ASCII sentence punctuation.

``_SENTENCE_END_RE`` decides which line endings are author-chosen boundaries (paragraph
per line) vs soft wraps (gather into one block). Its terminator class was ``[.!?]`` —
ASCII only — so a paragraph-per-line CJK document was gathered into ONE block and its
paragraph breaks were destroyed when the block was rejoined with spaces. MEASURED:

    blocks('这是第一段。...\\n这是第二段。...')  ->  ONE block

A zero-width character between the full stop and the line end defeated the boundary the
same way (``\\s*$`` never sees it):

    blocks('First sentence here.\\u200b\\nSecond sentence here.')  ->  ONE block
"""

from untell.layout import apply_per_block, blocks


def test_cjk_paragraph_per_line_keeps_its_blocks():
    text = "这是第一段。这是第一段的第二句。\n这是第二段。这是第二段的第二句。"
    parts = blocks(text)
    assert len(parts) == 2, parts
    assert parts[0] == "这是第一段。这是第一段的第二句。"
    assert parts[1] == "这是第二段。这是第二段的第二句。"


def test_cjk_line_boundary_survives_apply_per_block():
    text = "这是第一段。\n这是第二段。"
    out = apply_per_block(text, lambda b: b.replace("第一", "甲"))
    assert out == "这是甲段。\n这是第二段。", out


def test_zero_width_char_before_line_end_is_not_a_boundary_blocker():
    text = "First sentence here.\u200b\nSecond sentence here."
    assert len(blocks(text)) == 2, blocks(text)


def test_ascii_sentence_end_behaviour_is_unchanged():
    text = "First paragraph here.\nSecond paragraph here."
    assert len(blocks(text)) == 2, blocks(text)
