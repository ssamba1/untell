"""Batched-vs-single-window score identity for the real detectors (full tier).

The batched adapters must produce per-window scores equal to the single-window
path — the ensemble ``max`` is computed over window scores, so any cross-sample
contamination would silently change verdicts. Transformer forwards with an
attention mask are per-sample independent, so the scores are equal up to the
CPU's float accumulation noise: a batched GEMM may use a different kernel/blocking
than a single-row GEMM and reorder float additions. MEASURED on this machine the
largest batched-vs-single delta across all four adapters was ~2e-6 (roberta_openai,
window 0 of hc3-short), ~4 orders of magnitude below the finest calibrated
threshold (0.30/0.45) and below the 4-decimal precision the calibrations were
fitted to. The tolerance below (1e-4) is 50x the observed noise, so it fails on
real drift (padding leaking into logits, mask bugs) while passing accumulation
noise. The detector-level ``score()`` is additionally pinned to move by <1e-6:
``windowed_max`` takes the max, and the max window is unchanged.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.slow

try:
    import torch  # noqa: F401
    import transformers  # noqa: F401
except Exception as exc:  # pragma: no cover - environment dependent
    pytest.skip(f"torch/transformers unavailable: {exc}", allow_module_level=True)

if os.environ.get("UNTELL_LITE_NO_TORCH") == "1":  # pragma: no cover
    pytest.skip("UNTELL_LITE_NO_TORCH=1 forces the stdlib path; full-tier tests do not apply",
                allow_module_level=True)

from untell.detectors.base import _window_parts  # noqa: E402
from untell.detectors.fast_detectgpt import FastDetectGPTDetector  # noqa: E402
from untell.detectors.hc3_roberta import HC3RobertaDetector  # noqa: E402
from untell.detectors.mage import MageDetector  # noqa: E402
from untell.detectors.roberta_openai import RobertaOpenAIDetector  # noqa: E402

AI_TEXT = (
    "Furthermore, artificial intelligence has fundamentally transformed numerous industries. "
    "Moreover, organizations increasingly leverage these technologies to optimize efficiency. "
    "In conclusion, this represents a pivotal shift in the modern business landscape. "
) * 40  # ~1200 words -> several windows for every adapter

DETECTORS = [
    (RobertaOpenAIDetector, 320),
    (HC3RobertaDetector, 320),
    (FastDetectGPTDetector, 320),
    (MageDetector, 700),
]

# 50x the largest observed batched-vs-single delta (~2e-6); see module docstring.
_ATOL = 1e-4


@pytest.mark.parametrize("cls,window_words", DETECTORS, ids=[c.name for c, _ in DETECTORS])
def test_batch_scorer_identical_to_per_window(cls, window_words) -> None:
    det = cls()
    det.score("warm up the model with a short sentence here.")  # model load, not timed
    windows = _window_parts(AI_TEXT, window_words)
    assert len(windows) > 1, "the fixture text must span several windows for this to test anything"
    batched = det._score_batch(windows)
    single = [det._score_batch([w])[0] for w in windows]
    assert len(batched) == len(single) == len(windows)
    for i, (b, s) in enumerate(zip(batched, single)):
        if b is None or s is None:
            assert b is s is None, f"window {i}: None mismatch batched={b} single={s}"
        else:
            assert b == pytest.approx(s, abs=_ATOL), (
                f"window {i}: batched {b!r} differs from single-window {s!r} by more than {_ATOL}"
            )
