"""`ENABLE_CACHE=false` locked the name and left `=false` rewritable.

The flag and env-var rules matched the IDENTIFIER only, so an assignment came apart at the `=`.
MEASURED before the change:

    Set ENABLE_CACHE=false when debugging.   ->  Set ⟦HZ0000⟧=false when debugging.
    Set UNTELL_LITE_NO_TORCH=1 to force it.  ->  Set ⟦HZ0000⟧=1 to force it.
    Use LOG_LEVEL=warning in production.     ->  Use ⟦HZ0000⟧=warning in production.

A sentinel appears, so the span reads as protected, while the half that decides the behaviour
stays mutable — `=false` could become `=true` with every sentinel intact. This file already
documents the identical trade twice and calls it the worst case both times: "9:30 AM" locked only
"9:30" and left "AM" free, so a rewrite could move a meeting twelve hours; a comparison locked
"0.05" and left "<" free, so a rewrite could invert the assertion.

Numeric values were caught downstream by the numerals gate, which refuses a candidate that drops a
number the source states. Boolean and word values are caught by nothing.

HONEST ABOUT THE LEVERAGE: the free composite rewriter did not alter any of three assignments
across five seeds, so this closes a hole rather than repairing observed damage. That is the same
standing the AM/PM case had before it was fixed.

The value must end on an alphanumeric or a slash, so a sentence-final "DEBUG_MODE=true." leaves
its full stop outside the lock — a masked sentence without its terminator breaks the sentence
splitting downstream, which is the mistake the meridiem rule calls out by name.
"""

from __future__ import annotations

import pytest

from untell.scripts.preserve import lock, restore

# (label, text, the exact span that must end up inside one sentinel)
ASSIGNMENTS = [
    ("boolean false", "Set ENABLE_CACHE=false when debugging the pipeline.", "ENABLE_CACHE=false"),
    ("boolean true", "Export DEBUG_MODE=true before starting the service.", "DEBUG_MODE=true"),
    ("word value", "Use LOG_LEVEL=warning in production environments.", "LOG_LEVEL=warning"),
    ("digit value", "Set UNTELL_LITE_NO_TORCH=1 to force the stdlib path.", "UNTELL_LITE_NO_TORCH=1"),
    ("zero value", "Configure MAX_RETRIES=0 to disable retrying.", "MAX_RETRIES=0"),
    ("url value", "The variable HTTP_PROXY=http://proxy:8080 must be set.",
     "HTTP_PROXY=http://proxy:8080"),
    ("long flag", "Pass --tier=full to the CLI for the real ensemble.", "--tier=full"),
    ("dotted value", "Set VERSION_PIN=1.26.4 before the upgrade runs.", "VERSION_PIN=1.26.4"),
]

# Nothing here is an assignment; the pre-existing behaviour must not move.
BARE = [
    ("bare env var", "The UNTELL_ENABLE_RADAR switch is off by default.", "UNTELL_ENABLE_RADAR"),
    ("bare flag", "Pass --tier full to the CLI for the real ensemble.", "--tier"),
]


@pytest.mark.parametrize("name,text,span", ASSIGNMENTS, ids=[c[0] for c in ASSIGNMENTS])
def test_the_value_is_locked_with_the_name(name: str, text: str, span: str) -> None:
    masked, mapping = lock(text)
    assert span in mapping.values(), (
        f"{name}: expected {span!r} in one lock, got {list(mapping.values())} — masked {masked!r}"
    )
    assert restore(masked, mapping) == text


@pytest.mark.parametrize("name,text,span", BARE, ids=[c[0] for c in BARE])
def test_a_name_without_a_value_is_unchanged(name: str, text: str, span: str) -> None:
    """The `=VALUE` half is optional. A rule that started requiring it would stop locking every
    bare flag and env var in the corpus."""
    masked, mapping = lock(text)
    assert span in mapping.values(), f"{name}: {span!r} no longer locks — masked {masked!r}"
    assert restore(masked, mapping) == text


def test_a_sentence_final_value_leaves_its_full_stop_behind():
    """A greedy value would swallow the terminator, and the masked text would then be a sentence
    with no end — which is what breaks sentence splitting further down the pipeline."""
    text = "Export DEBUG_MODE=true."
    masked, mapping = lock(text)
    assert "DEBUG_MODE=true" in mapping.values()
    assert masked.endswith("."), f"the full stop went inside the lock: {masked!r}"
    assert restore(masked, mapping) == text


def test_a_comma_after_a_value_stays_outside():
    text = "With LOG_LEVEL=debug, the output is far noisier."
    masked, mapping = lock(text)
    assert "LOG_LEVEL=debug" in mapping.values(), list(mapping.values())
    assert ", the output" in masked, f"the comma went inside the lock: {masked!r}"


def test_the_rewriter_cannot_flip_a_boolean_through_the_mask():
    """The user-visible claim end to end: substitute into the masked text the way a rewriter would
    and the setting has to come back as written."""
    text = "Set ENABLE_CACHE=false when debugging the pipeline."
    masked, mapping = lock(text)

    flipped = masked.replace("false", "true").replace("=", " is ")
    assert restore(flipped, mapping) == text, "the rewriter reached the value"
