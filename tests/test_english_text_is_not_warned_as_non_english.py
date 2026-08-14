"""English text must not be warned as non-English.

sentences.py:265: `if text.strip() and looks_non_english(text)` — the language
caveat fires only for non-empty text that actually reads non-English. The
mutation and -> or fires it for ANY non-empty text (including plain English),
declaring "this text reads as a Latin-script language other than English" about
an English sentence — a false caveat on the headline warning slot.
"""
from untell.scripts.sentences import _warning_for


def test_english_text_is_not_warned_as_non_english():
    out = _warning_for(
        "This is a perfectly normal English sentence.", "lite", [], []
    )
    assert "not verdicts" not in out, f"English text flagged non-English: {out}"


def test_non_english_text_gets_the_language_warning():
    out = _warning_for(
        "C'est une phrase française avec beaucoup de mots et de structure.",
        "lite", [], [],
    )
    assert "Latin-script language other than English" in out
