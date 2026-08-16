"""Scratch copy of slice-4's new layout tests for mutation runs (probe artifact, untracked).

test_layout.py cannot be used for mutation runs because its rewriter-preservation test
loads real models and times out every mutant. These are the slice-4 classes only.
"""

import pytest

from untell.layout import apply_per_block


class TestSetextHeadingsAndThematicBreaks:
    @pytest.mark.parametrize("underline", ["==========", "----------", "**********", "__________"])
    def test_a_setext_underline_is_never_passed_to_the_transform(self, underline):
        src = f"My Heading\n{underline}\nSome prose here. More prose."
        seen: list[str] = []
        apply_per_block(src, lambda b: seen.append(b) or b)
        assert seen == ["My Heading", "Some prose here. More prose."]
        out = apply_per_block(src, lambda b: "REWRITTEN")
        assert underline in out

    @pytest.mark.parametrize("hr", ["---", "***", "___", "- - -", "* * *"])
    def test_a_thematic_break_between_paragraphs_is_layout(self, hr):
        from untell.layout import blocks

        src = f"Para one.\n{hr}\nPara two."
        assert blocks(src) == ["Para one.", "Para two."]
        out = apply_per_block(src, lambda b: " ".join(b.split()))
        assert hr in out
        assert f"Para one.{hr}" not in out.replace("\n", " ")

    def test_a_setext_heading_survives_a_merge_transform(self):
        src = "My Heading\n==========\nSome prose here. More prose."
        out = apply_per_block(src, lambda b: " ".join(x.strip() for x in b.split("\n")))
        assert "==========" in out
        assert "My Heading ==========" not in out

    def test_the_heading_text_above_a_setext_underline_is_still_prose(self):
        seen: list[str] = []
        apply_per_block("My Heading\n==========", lambda b: seen.append(b) or b)
        assert seen == ["My Heading"]


class TestBlockquotedTablesAreLayout:
    def test_a_blockquoted_table_row_is_never_passed_to_the_transform(self):
        src = "> | Method | Score |\n> |--------|-------|\n> | A | 0.9 |"
        seen: list[str] = []
        out = apply_per_block(src, lambda b: seen.append(b) or b.replace("Method", "Technique"))
        assert seen == []
        assert out == src

    def test_a_nested_blockquoted_table_row_too(self):
        src = "> > | Method | Score |\n> > | A | 0.9 |"
        assert apply_per_block(src, lambda b: "REWRITTEN") == src

    def test_blockquote_prose_is_still_prose(self):
        seen: list[str] = []
        apply_per_block("> Some prose here. More prose.\n> And another line.", lambda b: seen.append(b) or b)
        assert seen == ["Some prose here. More prose.", "And another line."]
