"""The trailing code pattern must not be quadratic on long unbroken runs.

MEASURED before the fix: the bare-filename branch of the trailing "code" pattern
was the only one of its six alternatives without a leading `\b`, so `[\\w-]+`
was attempted at EVERY character. On a 100k-char run of one letter it scanned
the rest of the run and backtracked through it per position — 25k chars 5.5s,
50k 21.9s, 100k ~88s — which froze `lock()` (and therefore `score_text`, whose
`_mostly_locked_warning` re-locks the text) on wide lines and long unbroken
runs. With the `\b` anchor the same scan is linear: 50k 0.08s, 100k 0.16s,
200k 0.33s, and real identifiers (main.py, parse_json(), UNTELL_ENABLE_RADAR)
still lock.
"""
from __future__ import annotations

import time

from untell.scripts.preserve import _PATTERNS, lock


def test_the_code_pattern_is_linear_on_unbroken_runs():
    pat = dict((label, p) for label, p in _PATTERNS)["code"]
    t0 = time.monotonic()
    pat.finditer("a" * 100_000)
    elapsed = time.monotonic() - t0
    # Linear scan of 100k chars is ~0.16s; the pre-fix engine took ~88s. The
    # bound is generous so a slow CI box cannot flake it, and far under the
    # quadratic blowup it exists to catch.
    assert elapsed < 5.0, f"code pattern took {elapsed:.1f}s on a 100k-char run"


def test_lock_completes_on_a_wide_line():
    """lock() on a 100k-char line with no spaces used to hang forever."""
    t0 = time.monotonic()
    masked, mapping = lock("x" * 100_000)
    elapsed = time.monotonic() - t0
    assert isinstance(masked, str)
    assert elapsed < 30.0, f"lock() took {elapsed:.1f}s on a 100k-char wide line"


def test_real_identifiers_still_lock():
    """The \b anchor must not stop the branch from locking what it is for."""
    text = (
        "Run src/main.py and tests/check.test.py then call parse_json() with "
        "UNTELL_ENABLE_RADAR and --tier full."
    )
    pat = dict((label, p) for label, p in _PATTERNS)["code"]
    locked = [text[m.start() : m.end()] for m in pat.finditer(text)]
    for needle in ("src/main.py", "tests/check.test.py", "parse_json()",
                   "UNTELL_ENABLE_RADAR", "--tier"):
        assert needle in locked, f"{needle!r} not locked; got {locked}"

def test_symbol_soup_skips_ner_without_loading_the_model(monkeypatch):
    """spaCy's tokenizer is O(n^2) on long punctuation runs and its model passes
    take ~36s on 10k symbol tokens, so lock() hung on pasted symbol blobs
    (MEASURED: lock('`'*48_000) and lock(('$'*60+' ')*5000) never returned).
    The NER pass must skip degenerate input before the spaCy model is even
    loaded; the linear regex locks still apply."""
    import untell.scripts.preserve as preserve

    class _Boom:
        def __call__(self, text):
            raise AssertionError("the NER model was invoked on degenerate input")

    monkeypatch.setattr(preserve._spacy_entity_spans, "_nlp", _Boom())
    preserve._spacy_entity_spans_cached.cache_clear()
    try:
        for blob in ("`" * 48_000, "$" * 48_000, ("$" * 60 + " ") * 5_000):
            assert preserve._spacy_entity_spans(blob) == []
    finally:
        preserve._spacy_entity_spans_cached.cache_clear()
        monkeypatch.undo()
    # normal prose still gets entities through the same entry point
    spans = preserve._spacy_entity_spans("Alice met Bob in Paris on Monday. " * 5)
    assert len(spans) > 0, "prose must still yield entities"


def test_lock_does_not_hang_on_symbol_blobs():
    """End-to-end: lock() on the inputs that used to hang must return quickly."""
    import time

    from untell.scripts.preserve import lock

    for blob in ("`" * 48_000, ("$" * 60 + " ") * 5_000):
        t0 = time.monotonic()
        masked, mapping = lock(blob)
        elapsed = time.monotonic() - t0
        assert isinstance(masked, str)
        assert elapsed < 30.0, f"lock() took {elapsed:.1f}s on a symbol blob"
