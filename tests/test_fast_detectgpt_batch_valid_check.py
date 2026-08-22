"""fast_detectgpt._score_batch valid-window filter uses padded shape, not real token count.

After ``tok(windows, ..., padding="longest")`` every row in the returned ``ids``
tensor has the SAME shape (the padded length = max tokens across the batch).
The original guard::

    valid = [i for i in range(ids.shape[0]) if ids[i].shape[0] >= 2]

checks ``ids[i].shape[0]`` — which is the padded length for row ``i``, identical for
all rows — rather than ``mask[i].sum()`` — the count of REAL (non-padding) tokens.

Consequence: in a mixed batch containing a window with only 1 real token alongside
a window with many, both pass the filter. The 1-real-token window produces:

    lm = mask[:, 1:] = all zeros (no real labels after position 0)
    disc = 0 * lm / clamp(lm.sum(), 1) = 0.0
    score = sigmoid((0.0 - CAL_MID) / CAL_SCALE) ≈ 0.076   (not None)

The Detector contract requires the window to ABSTAIN (return None) when there is
not enough material to score. 0.076 is not None — it enters batched_windowed_max's
``best`` accumulator and can inflate the document's ensemble max.

Fix: replace ``ids[i].shape[0] >= 2`` with ``mask[i].sum().item() >= 2``.
"""

from __future__ import annotations


def test_valid_check_uses_mask_not_padded_shape():
    """The _score_batch source must use mask.sum() to count real tokens, not shape[0].

    A structural guard: fails before the fix (``ids[i].shape[0]`` still present),
    passes after the fix (replaced by ``mask[i].sum().item()``).
    """
    from pathlib import Path

    src = (
        Path(__file__).resolve().parent.parent
        / "untell" / "detectors" / "fast_detectgpt.py"
    ).read_text(encoding="utf-8")

    assert "ids[i].shape[0] >= 2" not in src, (
        "fast_detectgpt._score_batch still uses ids[i].shape[0] >= 2 as the valid-window "
        "filter. After padding='longest', every row has the SAME shape[0] (the batch-max "
        "padded length), so the check never excludes individual short windows. "
        "Replace with mask[i].sum().item() >= 2 to count real (non-padding) tokens."
    )


def test_valid_check_logic_with_torch_tensors():
    """Show the gap between the old and new check on a concrete mixed batch.

    Batch: window 0 has 4 real tokens, window 1 has 1 real token.
    After padding='longest' both rows have shape [4]; old check includes both.
    The mask-based check correctly excludes window 1.
    """
    pytest = __import__("pytest")
    torch = pytest.importorskip("torch")

    # Batch of 2, padded to length 4.
    ids = torch.tensor([[10, 11, 12, 13],  # window 0: 4 real tokens
                        [10,  0,  0,  0]])  # window 1: 1 real token, 3 padding

    mask = torch.tensor([[1, 1, 1, 1],
                         [1, 0, 0, 0]])

    # Buggy check: ids[i].shape[0] is the PADDED length (4 for both rows).
    buggy_valid = [i for i in range(ids.shape[0]) if ids[i].shape[0] >= 2]
    assert buggy_valid == [0, 1], (
        "sanity: the buggy check includes the 1-real-token window — "
        "if this assertion fails, the bug was already fixed another way"
    )

    # Fixed check: mask[i].sum() counts REAL tokens.
    fixed_valid = [i for i in range(mask.shape[0]) if mask[i].sum().item() >= 2]
    assert fixed_valid == [0], (
        "fixed check must exclude window 1 (only 1 real token) from scoring"
    )
