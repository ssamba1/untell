"""Layout's sentence-end line test sees through bidi controls the same way text_split does.

``layout._SENTENCE_END_RE`` is built on the same ``_ZERO_WIDTH_CLASS`` single source
as the splitter, so the bidi-control addition propagates here: a line ending in
"sentence.\u200F" ends a sentence, so the newline after it is a boundary the author
chose rather than a soft wrap to be gathered into the surrounding block.

MEASURED before the class gained the bidi controls:

    blocks("First sentence.\u200F\nSecond paragraph here.\n")
        ->  ONE block ("First sentence.\u200F\nSecond paragraph here.")

...and after: two blocks, exactly like the plain "First sentence.\n" case.
"""

from __future__ import annotations

import pytest

from untell.layout import blocks

CARRIERS = [
    ("LRM", "\u200E"), ("RLM", "\u200F"), ("RLE", "\u202B"), ("RLI", "\u2067"),
    ("PDI", "\u2069"), ("ALM", "\u061C"),
]


@pytest.mark.parametrize("name,carrier", CARRIERS, ids=[c[0] for c in CARRIERS])
def test_a_line_ending_in_a_bidi_control_is_a_block_boundary(name, carrier):
    text = f"First sentence.{carrier}\nSecond paragraph here.\n"
    assert blocks(text) == [f"First sentence.{carrier}", "Second paragraph here."], name


def test_plain_sentence_line_is_still_one_block():
    text = "First sentence.\nSecond paragraph here.\n"
    assert blocks(text) == ["First sentence.", "Second paragraph here."]
