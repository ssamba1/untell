"""CJK and RTL sentence terminators must be sentence boundaries, not mid-text noise.

The splitter's terminator class was ``[.!?]`` — ASCII only. On CJK text that means a whole
document is ONE "sentence" to ``split_sentences``, which feeds the burstiness CV in
perplexity_burstiness (one sentence -> no CV -> 0.0), per-sentence targeting and the
rewriters' unit of work. Urdu's full stop (U+06D4) and Arabic's question mark (U+061F)
are missed the same way; Hebrew is fine because it uses the ASCII period.

MEASURED before this existed:

    split_sentences('这是第一句。这是第二句！这是第三句？')  -> ONE sentence
    split_sentences('یہ ایک جملہ ہے۔ یہ دوسرا جملہ ہے۔')    -> ONE sentence
    split_sentences('هل أنت متأكد؟ نعم. ثم غادر.')          -> '؟' not a boundary
"""

from untell.text_split import split_sentences


def test_cjk_terminators_are_sentence_boundaries():
    text = "这是第一句。这是第二句！这是第三句？"
    parts = split_sentences(text)
    assert len(parts) == 3, parts
    assert parts[0] == "这是第一句。"
    assert parts[1] == "这是第二句！"
    assert parts[2] == "这是第三句？"


def test_cjk_boundary_needs_no_whitespace_after_the_terminator():
    # CJK prose runs the next clause straight after 。— no space to split on.
    assert split_sentences("这是第一句。这是第二句。") == ["这是第一句。", "这是第二句。"]


def test_urdu_full_stop_is_a_boundary():
    parts = split_sentences("یہ ایک جملہ ہے۔ یہ دوسرا جملہ ہے۔")
    assert len(parts) == 2, parts
    assert parts[0] == "یہ ایک جملہ ہے۔"
    assert parts[1] == "یہ دوسرا جملہ ہے۔"


def test_arabic_question_mark_is_a_boundary():
    parts = split_sentences("هل أنت متأكد؟ نعم. ثم غادر.")
    assert len(parts) == 3, parts
    assert parts[0] == "هل أنت متأكد؟"
    assert parts[1] == "نعم."
    assert parts[2] == "ثم غادر."


def test_cjk_terminator_inside_curly_quotes_keeps_the_quote_attached():
    # 「」 are the CJK quotes; the closer must stay with the sentence that owns it.
    assert split_sentences("他说「好。」然后走了。") == ["他说「好。」", "然后走了。"]


def test_ascii_text_is_unchanged_by_the_new_terminators():
    # The new alternatives only fire on non-ASCII terminators; ASCII behaviour is pinned
    # by the existing battery and this spot-check.
    assert split_sentences("Dr. Smith arrived. He left.") == ["Dr. Smith arrived.", "He left."]
