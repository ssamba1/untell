"""The TTR window is 100 words — word 101 never dilutes the ratio.

perplexity_burstiness.py:211/237: `words = [w.lower() for w in _WORD.findall(
text)][:_TTR_WINDOW]` — the type-token ratio is computed over the FIRST 100
words. The mutation 100 -> 101 includes word 101: a 101-word text whose first
100 words sit exactly at the 0.25 TTR floor gets a 25/101 = 0.2475 ratio under
the mutant, crossing below the floor and firing the repetition signal that the
original (25/100 = 0.25, at or above floor) suppresses. Pinned at the pure
function level.
"""
from untell.detectors.perplexity_burstiness import _repetition_signal

_TYPES = [
    "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
    "india", "juliet", "kilo", "lima", "mike", "november", "oscar", "papa",
    "quebec", "romeo", "sierra", "tango", "uniform", "victor", "whiskey",
    "xray", "yankee",
]

TEXT = " ".join([t for t in _TYPES for _ in range(4)] + ["alpha"])  # 101 words


def test_ttr_window_is_100_words():
    assert _repetition_signal(TEXT) == 0.0
