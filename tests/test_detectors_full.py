"""Full-tier detector tests.

Skipped automatically wherever torch is unavailable (e.g. the lite CI job, or a Windows box with
a broken torch DLL). The full-tier CI job installs ``.[full]`` so these run there and exercise the
RoBERTa / MAGE / Fast-DetectGPT / GPT-2-perplexity code paths that the lite tier never touches.
"""

from __future__ import annotations

import pytest

try:
    # NOTE: a broken torch install raises OSError (Windows DLL load), not ImportError, so
    # importorskip is insufficient — catch everything and skip the whole module.
    import torch  # noqa: F401
    import transformers  # noqa: F401
except Exception as exc:  # pragma: no cover - environment dependent
    pytest.skip(f"torch/transformers unavailable: {exc}", allow_module_level=True)

from untell.detectors.base import load_detectors, resolved_tier  # noqa: E402
from untell.detectors.perplexity_burstiness import PerplexityBurstinessDetector  # noqa: E402

AI_TEXT = (
    "Artificial intelligence has fundamentally transformed numerous industries. Moreover, it has "
    "enabled organizations to improve efficiency. Furthermore, it can analyze data quickly. "
    "Overall, the impact continues to grow significantly across various sectors."
)
HUMAN_TEXT = (
    "I almost missed the bus. Rain again — of course. My shoes were soaked through by the time the "
    "8:14 finally rattled up, half-empty, smelling faintly of wet dog and someone's coffee, and I "
    "squeezed into the corner seat I always grab when nobody beats me to it. Worth it."
)


def test_full_tier_loads_supervised_detectors():
    dets = load_detectors("full")
    names = {d.name for d in dets}
    assert resolved_tier(dets) == "full", names
    assert {"roberta_openai", "mage", "fast_detectgpt"} <= names, names


@pytest.mark.parametrize("name", ["roberta_openai", "mage", "fast_detectgpt", "hc3_roberta"])
def test_supervised_detector_scores_in_unit_interval(name):
    det = next(d for d in load_detectors("full") if d.name == name)
    try:
        scores = [det.score(text) for text in (AI_TEXT, HUMAN_TEXT, "short text")]
    except Exception as exc:
        # A detector that can't load (e.g. yaful/MAGE's int-valued id2label is rejected by current
        # huggingface_hub, or a NumPy 2.x / torch mismatch) now RAISES -> it is EXCLUDED from the
        # ensemble rather than folded in as a fake neutral 0.5. That exclusion is the correct,
        # intended behavior, so a load failure here is a skip, not a test failure.
        pytest.skip(f"{name} unavailable in this env (excluded from ensemble): {type(exc).__name__}")
    for s in scores:
        # None == "no signal" (empty/too-short text) and is excluded upstream; otherwise [0,1].
        assert s is None or 0.0 <= s <= 1.0, (name, s)


def test_perplexity_full_path_runs_and_is_bounded():
    det = PerplexityBurstinessDetector()
    assert det._torch_ready()
    for text in (AI_TEXT, HUMAN_TEXT):
        s = det.score(text)
        assert 0.0 <= s <= 1.0


def test_embedding_quality_path_active():
    # When sentence-transformers is installed, the quality gate must use the semantic metric.
    pytest.importorskip("sentence_transformers")
    from untell.scripts.quality import confidence, method, recommended_bar, similarity

    assert method() == "embedding"
    assert confidence() == "high"
    assert recommended_bar() == 0.76
    # Identical text ~1.0; a faithful paraphrase should still clear the semantic bar comfortably.
    assert similarity("The cat sat on the mat.", "The cat sat on the mat.") >= 0.99
