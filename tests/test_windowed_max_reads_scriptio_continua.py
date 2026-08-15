"""windowed_max must actually window scriptio-continua text (CJK, Thai).

``windowed_max`` exists because every supervised adapter truncates at 512 tokens and
silently scores only the document's opening. Its early-return gate is
``len(text.split()) <= window_words`` and its chunker splits on spaces — so text with no
spaces (CJK, Thai, Japanese without furigana) is ONE "word" and is handed to the adapter
whole, truncation and all. MEASURED before this existed, with a counting scorer:

    1200 x '这是第一句。' (7200 chars)  ->  ONE window of 7200 chars

The docstring's own promise — "if any part of the document reads as machine-written, the
document does" — silently fails for every such language.

The char budget: CJK is roughly one token per character, so a no-space piece is cut at
``window_words`` characters and packed by characters, keeping every window inside the
adapter's token cap.
"""

from untell.detectors.base import WINDOW_WORDS, windowed_max


def _cjk_doc(sentences: int) -> str:
    return "这是第一句。" * sentences


def test_long_cjk_document_is_scored_in_windows():
    seen: list[str] = []
    windowed_max(_cjk_doc(1200), lambda w: seen.append(w) or 0.5)
    assert len(seen) > 1, f"expected several windows, got one of {len(seen[0])} chars"
    for w in seen:
        assert len(w) <= WINDOW_WORDS, f"window of {len(w)} chars exceeds the {WINDOW_WORDS} cap"


def test_no_cjk_character_is_dropped_or_reordered():
    text = _cjk_doc(500)
    seen: list[str] = []
    windowed_max(text, lambda w: seen.append(w) or 0.5)
    # windows are packed with " ".join, so separators appear between pieces; the
    # characters themselves must be a byte-exact reordering.
    assert "".join(seen).replace(" ", "") == text, "windowing lost or reordered characters"


def test_short_cjk_text_is_still_one_call():
    text = _cjk_doc(30)  # 180 chars, fits one window by the char budget
    seen: list[str] = []
    windowed_max(text, lambda w: seen.append(w) or 0.5)
    assert seen == [text]


def test_no_space_ascii_blob_is_windowed_by_characters():
    # A 2000-char run of letters with no spaces is the same shape as CJK: one "word" to
    # split(), and the adapter would read only its start.
    text = "x" * 2000
    seen: list[str] = []
    windowed_max(text, lambda w: seen.append(w) or 0.5)
    assert len(seen) > 1
    for w in seen:
        assert len(w) <= WINDOW_WORDS


def test_mixed_cjk_with_spaces_still_windows():
    # CJK sentences with ASCII spaces between them must also be windowed, not packed into
    # one giant window by the word-count packing loop.
    text = "这是 第一句。 " * 400  # 400 spaced fragments
    seen: list[str] = []
    windowed_max(text, lambda w: seen.append(w) or 0.5)
    assert len(seen) > 1
    assert "".join(seen).replace(" ", "") == text.replace(" ", "")
