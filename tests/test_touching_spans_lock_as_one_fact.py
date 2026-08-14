"""Touching spans must merge into one locked fact.

A date immediately followed by a number ("2023-05-0542") produces two pattern
matches that exactly touch: the date rule matches 2023-05-05 (cols 0-7) and the
number rule matches 42 (cols 7-12). _merge's `start <= last_end` is what joins
touching spans into a single mask. The mutation <= -> < splits them into two
adjacent sentinels, which restores as "2023-05" + "-0542" — a different, broken
locking of the same text. This test pins the touching-span merge.
"""
from untell.scripts.preserve import lock


def test_touching_spans_lock_as_one_fact():
    masked, mapping = lock("2023-05-0542")
    # The whole touching pair is ONE locked fact, not two adjacent sentinels.
    assert len(mapping) == 1, f"expected one merged span, got {len(mapping)}: {mapping}"
    (sentinel, fact) = next(iter(mapping.items()))
    assert fact == "2023-05-0542"
    assert masked == sentinel


def test_touching_spans_roundtrip():
    masked, mapping = lock("report dated 2023-05-0542 was filed")
    restored = masked
    for sentinel, fact in mapping.items():
        restored = restored.replace(sentinel, fact)
    assert restored == "report dated 2023-05-0542 was filed"
