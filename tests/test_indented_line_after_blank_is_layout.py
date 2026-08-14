"""An indented line after a blank starts code, not prose.

layout.py:226: `if not buffer and (line.startswith("    ") or line.startswith(
"\t")):` — an indented line that BEGINS a block is layout (locked), per the
comment: "an indented line only starts code when it BEGINS a block, which after
a blank line it does." The mutation or -> and makes the condition impossible (a
line can't start with both 4 spaces and a tab), so the indented code line is
gathered into the surrounding prose block and handed to the transform.
"""
import untell.layout as layout


def test_indented_line_after_blank_is_layout():
    text = "Para one.\n\n    indented code\nMore prose."
    kinds = [k for k, _, _ in layout._segments(text)]
    assert "    indented code" not in " ".join(
        b for k, _, b in layout._segments(text) if k == "prose"
    ), "indented code leaked into prose"


def test_indented_line_after_blank_not_transformable():
    text = "Para one.\n\n    indented code\nMore prose."
    out = layout.apply_per_block(text, lambda s: s.replace("code", "XCODE"))
    assert "indented code" in out, "indented line was transformed"
